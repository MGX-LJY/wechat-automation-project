# src/itchat_module/itchat_handler.py

import logging
import os
import re
import threading
import time
from collections import deque
from io import BytesIO
from typing import Optional, List, Tuple
from urllib.parse import urlparse, urlunparse
from PIL import Image
from lib import itchat
from lib.itchat.content import TEXT, SHARING
from src.config.config_manager import ConfigManager  # 新增导入


class ItChatHandler:
    def __init__(self, error_handler, notifier, browser_controller, point_manager):
        self.config = ConfigManager.load_config()
        self.monitor_groups: List[str] = self.config.get('wechat', {}).get('monitor_groups', [])
        self.target_individuals: List[str] = self.config.get('wechat', {}).get('target_individuals', [])
        self.admins: List[str] = self.config.get('wechat', {}).get('admins', [])
        self.error_handler = error_handler
        self.point_manager = point_manager
        self.qr_path = self.config.get('wechat', {}).get('login_qr_path', 'qr.png')
        self.max_retries = self.config.get('wechat', {}).get('itchat', {}).get('qr_check', {}).get('max_retries', 5)
        self.retry_interval = self.config.get('wechat', {}).get('itchat', {}).get('qr_check', {}).get('retry_interval', 2)
        self.login_event = threading.Event()
        self.point_manager = point_manager

        self.message_handler = MessageHandler(
            error_handler=error_handler,
            monitor_groups=self.monitor_groups,
            target_individuals=self.target_individuals,
            admins=self.admins,
            notifier=notifier,
            browser_controller=browser_controller,
            point_manager=self.point_manager,
        )

        self.uploader = None
        self.message_handler.set_uploader(self.uploader)

        logging.info("消息处理器初始化完成，但尚未绑定 Uploader")

    def set_uploader(self, uploader):
        """绑定 Uploader 实例到消息处理器"""
        self.uploader = uploader
        self.message_handler.set_uploader(uploader)
        logging.info("Uploader 已绑定到消息处理器")

    def set_auto_clicker(self, auto_clicker):
        """
        设置 MessageHandler 的 AutoClicker 实例
        """
        self.message_handler.set_auto_clicker(auto_clicker)
        logging.info("AutoClicker 已设置到消息处理器")

    def login(self):
        """执行微信登录过程，处理二维码显示和会话管理"""
        for attempt in range(1, self.max_retries + 1):
            try:
                session_file = 'itchat.pkl'
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logging.info(f"已删除旧的会话文件: {session_file}")

                itchat.auto_login(
                    hotReload=False,
                    enableCmdQR=False,
                    qrCallback=self.qr_callback
                )
                logging.info("微信登录成功")

                itchat.get_friends(update=True)
                itchat.get_chatrooms(update=True)
                logging.info("好友和群组信息已加载")

                self.login_event.set()
                return
            except Exception as e:
                logging.error(f"登录失败，第 {attempt} 次尝试。错误: {e}")
                self.error_handler.handle_exception(e)
                time.sleep(self.retry_interval)

        logging.critical("多次登录失败，应用启动失败。")
        raise Exception("多次登录失败，应用启动失败。")

    def run(self):
        """注册消息处理函数并启动 ItChat 客户端监听消息"""
        @itchat.msg_register([TEXT, SHARING], isGroupChat=True)
        def handle_group(msg):
            self.message_handler.handle_group_message(msg)

        @itchat.msg_register([TEXT, SHARING], isGroupChat=False)
        def handle_individual(msg):
            self.message_handler.handle_individual_message(msg)

        try:
            itchat.run()
        except Exception as e:
            logging.critical(f"ItChat 运行时发生致命错误: {e}")
            self.error_handler.handle_exception(e)

    def qr_callback(self, uuid, status, qrcode):
        """处理二维码回调，保存并显示二维码图像"""
        logging.info(f"QR callback - UUID: {uuid}, Status: {status}")
        try:
            if status == '0':
                with open(self.qr_path, 'wb') as f:
                    f.write(qrcode)
                logging.info(f"二维码已保存到 {self.qr_path}")

                Image.open(BytesIO(qrcode)).show(title="微信登录二维码")
            elif status == '201':
                logging.info("二维码已扫描，请在手机上确认登录。")
            elif status == '200':
                logging.info("登录成功")
            else:
                logging.warning(f"未知的QR回调状态: {status}")
        except Exception as e:
            logging.error(f"处理QR码时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def logout(self):
        """登出微信账号，结束当前会话"""
        try:
            itchat.logout()
            logging.info("微信已退出")
        except Exception as e:
            logging.error(f"退出微信时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)


class MessageHandler:
    """
    消息处理器，用于处理微信消息，提取URL并调用 AutoClicker
    """

    def __init__(self, error_handler, monitor_groups, target_individuals, admins, notifier=None, browser_controller=None, point_manager=None):
        self.config = ConfigManager.load_config()
        self.regex = re.compile(self.config.get('url', {}).get('regex', r'https?://[^\s"」]+'))
        self.validation = self.config.get('url', {}).get('validation', True)
        self.auto_clicker = None
        self.uploader = None
        self.error_handler = error_handler
        self.monitor_groups = monitor_groups
        self.target_individuals = target_individuals
        self.admins = admins
        self.notifier = notifier
        self.browser_controller = browser_controller
        self.log_dir = self.config.get('logging', {}).get('directory', 'logs')
        self.point_manager = point_manager
        self.group_types = self.config.get('group_types', {})

    def set_auto_clicker(self, auto_clicker):
        """设置 AutoClicker 实例用于自动处理任务"""
        self.auto_clicker = auto_clicker

    def set_uploader(self, uploader):
        """设置 Uploader 实例用于上传相关信息"""
        self.uploader = uploader

    def get_message_content(self, msg) -> str:
        """获取消息的完整文本内容"""
        try:
            msg_type = msg.get('Type', getattr(msg, 'type', ''))
            if msg_type not in ['Text', 'Sharing']:
                return ''

            return msg.get('Text', msg.get('text', '')) if msg_type == 'Text' else msg.get('Url', msg.get('url', ''))
        except Exception as e:
            logging.error(f"获取消息内容时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return ''

    def handle_group_message(self, msg):
        """处理来自群组的消息，提取并处理URL"""
        group_name = msg['User']['NickName']
        if group_name not in self.monitor_groups:
            logging.debug(f"忽略来自非监控群组的消息: {group_name}")
            return

        # 获取群组类型
        if group_name in self.group_types.get('whole_groups', []):
            group_type = 'whole'
        elif group_name in self.group_types.get('non_whole_groups', []):
            group_type = 'non-whole'
        else:
            # 默认设为非整体群组
            group_type = 'non-whole'

        sender_nickname = msg['ActualNickName']  # 获取发送者昵称

        # 提取URL
        urls = self.extract_urls(msg)
        if not urls:
            return

        # 检查积分
        if group_type == 'whole':
            if not self.point_manager.has_group_points(group_name):
                logging.info(f"群组 '{group_name}' 的积分不足，忽略消息。")
                return
        elif group_type == 'non-whole':
            if not self.point_manager.has_member_points(sender_nickname):
                logging.info(f"成员 '{sender_nickname}' 的积分不足，忽略消息。")
                return

        # 处理URL
        processed_urls = self.process_urls(urls, is_group=True, recipient_name=group_name)
        if not processed_urls:
            return

        # 通过积分检查后，调用上传和添加任务函数
        for url, soft_id in processed_urls:
            if self.uploader and soft_id:
                self.uploader.upload_group_id(
                    recipient_name=group_name,
                    soft_id=soft_id,
                    sender_nickname=sender_nickname if group_type == 'non-whole' else None,
                    recipient_type='group',
                    group_type=group_type
                )
                logging.info(f"上传信息到 Uploader: {group_name}, {soft_id}, 发送者: {sender_nickname}")
            else:
                logging.warning("Uploader 未设置，或无法上传接收者和 soft_id 信息。")

            if self.auto_clicker:
                self.auto_clicker.add_task(url)
                logging.info(f"已添加任务到下载队列: {url}")
            else:
                logging.warning("AutoClicker 未设置，无法添加任务。")

    def handle_individual_message(self, msg):
        """处理来自个人的消息，提取URL或执行管理员命令"""
        sender = msg['User']['NickName']
        if sender not in self.target_individuals and sender not in self.admins:
            logging.debug(f"忽略来自非监控个人的消息: {sender}")
            return

        if sender in self.admins:
            content = self.get_message_content(msg)  # 获取完整消息内容
            response = self.handle_admin_command(content)
            if response and self.notifier:
                self.notifier.notify(response)
            return

        # 提取URL
        urls = self.extract_urls(msg)
        if not urls:
            return

        # 检查发送者是否有足够的积分
        if not self.point_manager.has_recipient_points(sender):
            logging.info(f"发送者 '{sender}' 积分不足，无法添加任务到下载队列。")
            if self.notifier:
                self.notifier.notify(f"抱歉，您当前的积分不足，无法添加下载任务。请联系管理员获取更多信息。")
            return

        # 处理URL
        processed_urls = self.process_urls(urls)
        if not processed_urls:
            return

        # 通过积分检查后，调用上传和添加任务函数
        for url, soft_id in processed_urls:
            if self.uploader and soft_id:
                self.uploader.upload_group_id(
                    recipient_name=sender,
                    soft_id=soft_id,
                    recipient_type='individual'
                )
                logging.info(f"上传信息到 Uploader: {sender}, {soft_id}")
            else:
                logging.warning("Uploader 未设置，或无法上传接收者和 soft_id 信息。")

            if self.auto_clicker:
                self.auto_clicker.add_task(url)
                logging.info(f"已添加任务到下载队列: {url}")
            else:
                logging.warning("AutoClicker 未设置，无法添加任务。")

    def handle_admin_command(self, message: str) -> Optional[str]:
        """处理管理员发送的命令并执行相应操作"""
        commands = {
            'add_recipient': r'^添加接收者\s+(\S+)\s+(\d+)$',
            'delete_recipient': r'^删除接收者\s+(\S+)$',
            'update_remaining': r'^更新剩余积分\s+(\S+)\s+([+-]?\d+)$',
            'query_recipient': r'^查询接收者\s+(\S+)$',
            'get_all_recipients': r'^获取所有接收者$',
            'help': r'^帮助$|^help$',
            'restart_browser': r'^重启浏览器$|^restart browser$',
            'query_logs': r'^查询日志$|^query logs$',
            'query_browser': r'^查询浏览器$|^query browser$',
            'add_monitor_group': r'^添加监听群组\s+(.+)$',
            'remove_monitor_group': r'^删除监听群组\s+(.+)$',
            'add_monitor_individual': r'^添加监听个人\s+(.+)$',
            'remove_monitor_individual': r'^删除监听个人\s+(.+)$',
            'add_whole_group': r'^添加整体群组\s+(.+)$',
            'remove_whole_group': r'^删除整体群组\s+(.+)$',
            'add_non_whole_group': r'^添加非整体群组\s+(.+)$',
            'remove_non_whole_group': r'^删除非整体群组\s+(.+)$',
        }

        for cmd, pattern in commands.items():
            match = re.match(pattern, message)
            if match:
                if cmd == 'add_recipient':
                    name, count = match.groups()
                    result = self.point_manager.add_recipient(name, initial_points=int(count))
                    return result
                elif cmd == 'delete_recipient':
                    name = match.group(1)
                    success = self.point_manager.delete_recipient(name)
                    if success:
                        return f"接收者 '{name}' 已删除。"
                    else:
                        return f"接收者 '{name}' 删除失败或不存在。"
                elif cmd == 'update_remaining':
                    name, delta = match.groups()
                    delta = int(delta)
                    success = self.point_manager.update_recipient_points(name, delta)
                    if success:
                        return f"接收者 '{name}' 的剩余积分已更新，变化量为 {delta}。"
                    else:
                        return f"接收者 '{name}' 的积分更新失败。"
                elif cmd == 'query_recipient':
                    name = match.group(1)
                    info = self.point_manager.get_recipient_info(name)
                    if info:
                        return f"接收者 '{info['name']}' 的剩余积分为 {info['remaining_points']}。"
                    return f"接收者 '{name}' 不存在。"
                elif cmd == 'get_all_recipients':
                    recipients = self.point_manager.get_all_recipients()
                    return f"所有接收者列表：{', '.join(recipients)}" if recipients else "当前没有任何接收者。"
                elif cmd == 'help':
                    return self.get_help_message()
                elif cmd == 'restart_browser':
                    if self.browser_controller:
                        self.browser_controller.restart_browser()
                        return "浏览器已成功重启。"
                    return "浏览器控制器未设置，无法重启浏览器。"
                elif cmd == 'query_logs':
                    if self.notifier:
                        logs = self.get_last_n_logs(20)
                        if logs:
                            send_long_message(self.notifier, f"最近 20 行日志:\n{logs}")
                        else:
                            self.notifier.notify("无法读取日志文件或日志文件为空。")
                    else:
                        logging.error("Notifier 未设置，无法发送日志。")
                    return None
                elif cmd == 'query_browser':
                    if not self.browser_controller:
                        logging.error("浏览器控制器未设置，无法处理查询浏览器命令。")
                        if self.notifier:
                            self.notifier.notify("无法处理查询浏览器命令，因为浏览器控制器未设置。", is_error=True)
                        return "浏览器控制器未设置，无法查询浏览器。"

                    try:
                        screenshots = self.browser_controller.capture_all_tabs_screenshots()
                        if screenshots:
                            self.notifier.notify_images(screenshots)
                            for path in screenshots:
                                os.remove(path)
                                logging.debug(f"已删除临时截图文件: {path}")
                        else:
                            self.notifier.notify("无法捕获浏览器标签页的截图。", is_error=True)
                    except Exception as e:
                        logging.error(f"处理查询浏览器命令时发生错误: {e}", exc_info=True)
                        if self.notifier:
                            self.notifier.notify(f"处理查询浏览器命令时发生错误: {e}", is_error=True)
                    return None
                elif cmd == 'add_monitor_group':
                    group_names = match.group(1)
                    return self.modify_monitor_groups(group_names, action='add')
                elif cmd == 'remove_monitor_group':
                    group_names = match.group(1)
                    return self.modify_monitor_groups(group_names, action='remove')
                elif cmd == 'add_monitor_individual':
                    individual_names = match.group(1)
                    return self.modify_monitor_individuals(individual_names, action='add')
                elif cmd == 'remove_monitor_individual':
                    individual_names = match.group(1)
                    return self.modify_monitor_individuals(individual_names, action='remove')
                elif cmd == 'add_whole_group':
                    group_names = match.group(1)
                    return self.modify_group_type(group_names, group_type='whole', action='add')
                elif cmd == 'remove_whole_group':
                    group_names = match.group(1)
                    return self.modify_group_type(group_names, group_type='whole', action='remove')
                elif cmd == 'add_non_whole_group':
                    group_names = match.group(1)
                    return self.modify_group_type(group_names, group_type='non_whole', action='add')
                elif cmd == 'remove_non_whole_group':
                    group_names = match.group(1)
                    return self.modify_group_type(group_names, group_type='non_whole', action='remove')
        logging.warning(f"未知的管理员命令：{message}")
        return "未知的命令，请检查命令格式。"

    def modify_monitor_groups(self, group_names: str, action: str) -> str:
        """添加或删除监听群组"""
        try:
            groups = [name.strip() for name in group_names.split(',')]
            if action == 'add':
                for group in groups:
                    if group not in self.monitor_groups:
                        self.monitor_groups.append(group)
            elif action == 'remove':
                for group in groups:
                    if group in self.monitor_groups:
                        self.monitor_groups.remove(group)
            else:
                return "未知的操作类型。"

            # 更新配置并保存
            self.config['group_types'] = self.group_types
            ConfigManager.save_config(self.config)

            # 同步更新上传目标
            self.sync_upload_targets()

            message = f"已{ '添加' if action == 'add' else '删除' }监听群组：{', '.join(groups)}"
            logging.info(message)
            return message
        except Exception as e:
            logging.error(f"修改监听群组时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return f"修改监听群组时发生错误: {e}"

    def modify_monitor_individuals(self, individual_names: str, action: str) -> str:
        """添加或删除监听个人"""
        try:
            individuals = [name.strip() for name in individual_names.split(',')]
            if action == 'add':
                for individual in individuals:
                    if individual not in self.target_individuals:
                        self.target_individuals.append(individual)
            elif action == 'remove':
                for individual in individuals:
                    if individual in self.target_individuals:
                        self.target_individuals.remove(individual)
            else:
                return "未知的操作类型。"

            if action == 'add':
                message = f"已添加监听个人：{', '.join(individuals)}"
            else:
                message = f"已删除监听个人：{', '.join(individuals)}"

            # 更新配置并保存
            self.config['wechat']['target_individuals'] = self.target_individuals
            ConfigManager.save_config(self.config)

            # 同步更新上传目标
            self.sync_upload_targets()

            logging.info(message)
            return message
        except Exception as e:
            logging.error(f"修改监听个人时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return f"修改监听个人时发生错误: {e}"

    def modify_group_type(self, group_names: str, group_type: str, action: str) -> str:
        """添加或删除整体群组或非整体群组"""
        try:
            groups = [name.strip() for name in group_names.split(',')]
            group_key = 'whole_groups' if group_type == 'whole' else 'non_whole_groups'

            if action == 'add':
                for group in groups:
                    if group not in self.group_types.get(group_key, []):
                        self.group_types.setdefault(group_key, []).append(group)
                    # 从另一类型的群组中移除
                    other_key = 'non_whole_groups' if group_key == 'whole_groups' else 'whole_groups'
                    if group in self.group_types.get(other_key, []):
                        self.group_types[other_key].remove(group)
                message = f"已添加{group_type}群组：{', '.join(groups)}"
            elif action == 'remove':
                for group in groups:
                    if group in self.group_types.get(group_key, []):
                        self.group_types[group_key].remove(group)
                message = f"已删除{group_type}群组：{', '.join(groups)}"
            else:
                return "未知的操作类型。"

            # 更新配置并保存
            self.config['group_types'] = self.group_types
            ConfigManager.save_config(self.config)

            # 更新数据库中群组的类型
            for group in groups:
                is_whole = (group_type == 'whole' and action == 'add')
                self.point_manager.ensure_group(group, is_whole=is_whole)

            logging.info(message)
            return message
        except Exception as e:
            logging.error(f"修改群组类型时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return f"修改群组类型时发生错误: {e}"

    def sync_upload_targets(self):
        """同步上传目标和监听目标"""
        if self.uploader:
            self.uploader.target_groups = self.monitor_groups.copy()
            self.uploader.target_individuals = self.target_individuals.copy()
            # 更新配置并保存
            self.config['upload']['target_groups'] = self.uploader.target_groups
            self.config['upload']['target_individuals'] = self.uploader.target_individuals
            ConfigManager.save_config(self.config)
            logging.info("上传目标已同步更新")
        else:
            logging.warning("Uploader 未设置，无法同步上传目标")

    def set_config_value(self, key_path: str, value: str) -> str:
        """设置配置文件中的值"""
        try:
            keys = key_path.split('.')
            config_section = self.config
            for key in keys[:-1]:
                if key in config_section:
                    config_section = config_section[key]
                else:
                    return f"配置项不存在: {key_path}"

            last_key = keys[-1]
            if last_key in config_section:
                # 尝试将字符串转换为合适的类型（如整数、布尔值等）
                old_value = config_section[last_key]
                new_value = self._convert_value_type(value, old_value)
                config_section[last_key] = new_value

                # 保存配置
                ConfigManager.save_config(self.config)

                # 通知相关模块（如需要）
                self._notify_config_change()

                return f"配置项 '{key_path}' 已更新为 {new_value}"
            else:
                return f"配置项不存在: {key_path}"
        except Exception as e:
            logging.error(f"设置配置项时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return f"设置配置项时发生错误: {e}"

    def _convert_value_type(self, value: str, old_value):
        """根据原值的类型，将字符串转换为合适的类型"""
        if isinstance(old_value, bool):
            return value.lower() in ['true', '1', 'yes', 'on']
        elif isinstance(old_value, int):
            return int(value)
        elif isinstance(old_value, float):
            return float(value)
        elif isinstance(old_value, list):
            # 假设列表项为字符串，以逗号分隔
            return [item.strip() for item in value.strip().split(',')]
        else:
            return value

    def _notify_config_change(self):
        """通知相关模块配置已更新"""
        # 更新正则表达式
        self.regex = re.compile(self.config.get('url', {}).get('regex', r'https?://[^\s"」]+'))
        # 更新验证开关
        self.validation = self.config.get('url', {}).get('validation', True)
        logging.info("MessageHandler 已更新配置")

    def get_help_message(self) -> str:
        """返回可用命令的帮助信息"""
        return (
            "可用命令如下：\n\n"
            "1. 添加接收者 <接收者名称> <初始剩余积分>\n"
            "   示例：添加接收者 User1 500\n\n"
            "2. 删除接收者 <接收者名称>\n"
            "   示例：删除接收者 User1\n\n"
            "3. 更新剩余积分 <接收者名称> <变化量>\n"
            "   示例：更新剩余积分 User1 -10\n\n"
            "4. 查询接收者 <接收者名称>\n"
            "   示例：查询接收者 User1\n\n"
            "5. 获取所有接收者\n"
            "   示例：获取所有接收者\n\n"
            "6. 帮助\n"
            "   示例：帮助\n\n"
            "7. 重启浏览器\n"
            "   示例：重启浏览器\n\n"
            "8. 查询日志\n"
            "   示例：查询日志\n\n"
            "9. 查询浏览器\n"
            "   示例：查询浏览器\n\n"
            "10. 添加监听群组 <群组名称1>,<群组名称2>\n"
            "    示例：添加监听群组 群组A,群组B\n\n"
            "11. 删除监听群组 <群组名称1>,<群组名称2>\n"
            "    示例：删除监听群组 群组A,群组B\n\n"
            "12. 添加监听个人 <个人名称1>,<个人名称2>\n"
            "    示例：添加监听个人 个人1,个人2\n\n"
            "13. 删除监听个人 <个人名称1>,<个人名称2>\n"
            "    示例：删除监听个人 个人1,个人2\n\n"
            "14. 添加整体群组 <群组名称1>,<群组名称2>\n"
            "    示例：添加整体群组 群组A,群组B\n\n"
            "15. 删除整体群组 <群组名称1>,<群组名称2>\n"
            "    示例：删除整体群组 群组A,群组B\n\n"
            "16. 添加非整体群组 <群组名称1>,<群组名称2>\n"
            "    示例：添加非整体群组 群组A,群组B\n\n"
            "17. 删除非整体群组 <群组名称1>,<群组名称2>\n"
            "    示例：删除非整体群组 群组A,群组B\n"
        )

    def extract_urls(self, msg) -> List[str]:
        """从消息中提取URL列表"""
        try:
            msg_type = msg.get('Type', getattr(msg, 'type', ''))
            if msg_type not in ['Text', 'Sharing']:
                logging.debug(f"忽略非文本或分享类型的消息: {msg_type}")
                return []

            content = msg.get('Text', msg.get('text', '')) if msg_type == 'Text' else msg.get('Url', msg.get('url', ''))
            return self.regex.findall(content)
        except Exception as e:
            logging.error(f"提取消息内容时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return []

    def process_urls(self, urls: List[str]) -> List[Tuple[str, Optional[str]]]:
        """清理、验证并处理URL，返回有效的URL列表和 soft_id"""
        processed_urls = []
        for url in urls:
            clean_url = self.clean_url(url)
            if self.validation and not self.validate_url(clean_url):
                logging.warning(f"URL 验证失败: {clean_url}")
                continue

            soft_id_match = re.search(r'/soft/(\d+)\.html', clean_url)
            soft_id = soft_id_match.group(1) if soft_id_match else None
            if not soft_id:
                logging.warning(f"无法从 URL 中提取 soft_id: {clean_url}")

            processed_urls.append((clean_url, soft_id))
        return processed_urls

    def clean_url(self, url: str) -> str:
        """清理URL，移除锚点和不必要的字符"""
        try:
            parsed = urlparse(url)
            clean = parsed._replace(fragment='')
            cleaned_url = urlunparse(clean).rstrip('」””"\'')
            return cleaned_url
        except Exception as e:
            logging.error(f"清理 URL 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return url

    def validate_url(self, url: str) -> bool:
        """验证URL是否以http://或https://开头"""
        return url.startswith(('http://', 'https://'))

    def get_last_n_logs(self, n: int) -> Optional[str]:
        """获取日志目录下最新日志文件的最后n行内容"""
        try:
            log_files = [f for f in os.listdir(self.log_dir) if f.endswith('.log')]
            if not log_files:
                logging.warning("日志目录下没有日志文件。")
                return None

            latest_log_file = max(log_files)
            log_path = os.path.join(self.log_dir, latest_log_file)

            with open(log_path, 'r', encoding='utf-8') as f:
                return ''.join(deque(f, n))
        except Exception as e:
            logging.error(f"读取日志文件时出错: {e}", exc_info=True)
            return None

def send_long_message(notifier, message: str, max_length: int = 2000):
    """将长消息分割为多个部分并逐段发送"""
    try:
        for i in range(0, len(message), max_length):
            notifier.notify(message[i:i + max_length])
    except Exception as e:
        logging.error(f"发送长消息时出错: {e}", exc_info=True)
