import re
import logging
import os
from typing import Optional, List
from datetime import datetime, timezone
from src.config.config_manager import ConfigManager


class AdminCommandsHandler:
    def __init__(self, config, point_manager, notifier=None, browser_controller=None, error_handler=None):
        self.config = config
        self.point_manager = point_manager
        self.notifier = notifier
        self.browser_controller = browser_controller
        self.error_handler = error_handler
        self.help_templates = {
            # 【数据库命令】
            '1': "更新个人积分 <个人名称> <变化量>",
            '2': "更新群组积分 <群组名称> <变化量>",
            '3': "更新用户积分 群组名: <群组名称> 昵称: <用户昵称> 积分: [更新积分]",
            '4': "查询个人积分 <个人名称>",
            '5': "查询群组积分 <群组名称>",
            '6': "查询用户积分 群组名: <群组名称> 昵称: <用户昵称>",

            # 【配置文件命令】
            '7': "添加监听群组 <群组名称1>,<群组名称2>",
            '8': "删除监听群组 <群组名称1>,<群组名称2>",
            '9': "添加监听个人 <个人名称1>,<个人名称2>",
            '10': "删除监听个人 <个人名称1>,<个人名称2>",
            '11': "添加整体群组 <群组名称1>,<群组名称2>",
            '12': "删除整体群组 <群组名称1>,<群组名称2>",
            '13': "添加非整体群组 <群组名称1>,<群组名称2>",
            '14': "删除非整体群组 <群组名称1>,<群组名称2>",
            '15': "帮助",

            # 【实例管理命令】
            '16': "禁用全部实例",
            '17': "查询群组下载份数 <群组名称> <时间段>",
            '18': "查询个人下载份数 <个人名称> <时间段>",
            '19': "查询所有群组今天下载量",
            '20': "查询所有群组这周下载量",
            '21': "查询当前账号使用情况",
            '22': "查询所有实例状态",
            '23': "检查所有实例状态",
            '24': "设置实例需要管理员介入 <实例ID> <True/False>",
        }
        self.commands = {
            # 数据库命令
            'update_individual_points': r'^更新个人积分\s+(\S+)\s+([+-]?\d+)$',
            'update_non_whole_group_points': r'^更新群组积分\s+(\S+)\s+([+-]?\d+)$',
            'update_user_points': r'^更新用户积分\s+群组名:\s*(\S+)\s+昵称:\s*(\S+)\s*积分:\s*([+-]?\d+)$',

            # 新增查询积分命令
            'query_individual_points': r'^查询个人积分\s+(\S+)$',
            'query_whole_group_points': r'^查询群组积分\s+(\S+)$',
            'query_user_points': r'^查询用户积分\s+群组名:\s*(\S+)\s+昵称:\s*(\S+)$',

            # 配置文件命令
            'add_monitor_group': r'^添加监听群组\s+(.+)$',
            'remove_monitor_group': r'^删除监听群组\s+(.+)$',
            'add_monitor_individual': r'^添加监听个人\s+(.+)$',
            'remove_monitor_individual': r'^删除监听个人\s+(.+)$',
            'add_whole_group': r'^添加整体群组\s+(.+)$',
            'remove_whole_group': r'^删除整体群组\s+(.+)$',
            'add_non_whole_group': r'^添加非整体群组\s+(.+)$',
            'remove_non_whole_group': r'^删除非整体群组\s+(.+)$',

            # 其他命令
            'help': r'^帮助$|^help$',
            'query_logs': r'^查询日志$|^query logs$',
            'disable_all_instances': r'^禁用全部实例$|^disable all instances$',

            # 新增下载份数查询命令
            'query_group_today_downloads': r'^查询群组\s+(\S+)\s+今天\s+下载份数$',
            'query_group_this_week_downloads': r'^查询群组\s+(\S+)\s+这周\s+下载份数$',
            'query_group_last_week_downloads': r'^查询群组\s+(\S+)\s+上周\s+下载份数$',
            'query_group_this_month_downloads': r'^查询群组\s+(\S+)\s+这个月\s+下载份数$',
            'query_group_last_month_downloads': r'^查询群组\s+(\S+)\s+上个月\s+下载份数$',

            'query_individual_today_downloads': r'^查询个人\s+(\S+)\s+今天\s+下载份数$',
            'query_individual_this_week_downloads': r'^查询个人\s+(\S+)\s+这周\s+下载份数$',
            'query_individual_last_week_downloads': r'^查询个人\s+(\S+)\s+上周\s+下载份数$',
            'query_all_groups_today_downloads': r'^查询所有群组今天下载量$',
            'query_all_groups_this_week_downloads': r'^查询所有群组这周下载量$',
            'query_current_account_usage': r'^查询当前账号使用情况$',
            'check_all_instances_status': r'^检查所有实例状态$|^check all instances status$',
            'query_all_instances_status': r'^查询所有实例状态$|^query all instances status$',
            'set_instance_admin_intervention': r'^设置实例需要管理员介入\s+(\S+)\s+(\S+)$',
        }

    def handle_command(self, message: str) -> Optional[str]:
        """处理管理员发送的命令并执行相应操作"""
        message = message.strip()  # 去除前后空格
        # 首先检测消息是否包含链接
        links = self.extract_urls(message)
        if links:
            for link in links:
                logging.info(f"检测到链接: {link}")
                soft_id = self.extract_soft_id_from_url(link)
                if soft_id:
                    try:
                        logs = self.get_soft_id_logs(soft_id)
                    except Exception as e:
                        logging.error(f"获取 soft_id '{soft_id}' 的日志时出错: {e}")
                        return "获取日志时发生错误，请稍后再试。"

                    if logs.strip():
                        MAX_LOG_LENGTH = 4000  # 根据实际平台调整
                        if len(logs) > MAX_LOG_LENGTH and self.notifier:
                            self.send_long_message(logs)
                            return "已分段发送与该 soft_id 相关的日志。"
                        else:
                            return logs
                    else:
                        return f"未找到与 soft_id '{soft_id}' 相关的日志。"
                else:
                    return "无法从提供的链接中提取 soft_id，请检查链接格式。"

        if message.isdigit():
            template = self.help_templates.get(message)
            if template:
                return f"{template}"
            else:
                return "无效的命令序号，请输入帮助命令查看可用命令列表。"

        for cmd, pattern in self.commands.items():
            match = re.match(pattern, message)
            if match:
                logging.debug(f"匹配到命令: {cmd}，参数: {match.groups()}")
                try:
                    if cmd == 'update_individual_points':
                        # 处理逻辑
                        name, delta = match.groups()
                        delta = int(delta)
                        success = self.point_manager.update_recipient_points(name, delta)
                        if success:
                            return f"个人 '{name}' 的剩余积分已更新，变化量为 {delta}。"
                        else:
                            return f"个人 '{name}' 的积分更新失败。"

                    elif cmd == 'update_non_whole_group_points':
                        # 处理逻辑
                        group_name, delta = match.groups()
                        delta = int(delta)
                        success = self.point_manager.update_group_points(group_name, delta)
                        if success:
                            return f"整体群组 '{group_name}' 的剩余积分已更新，变化量为 {delta}。"
                        else:
                            return f"整体群组 '{group_name}' 的积分更新失败。"

                    elif cmd == 'update_user_points':
                        # 处理逻辑
                        group_name, nickname, points = match.groups()
                        points = int(points) if points else 0
                        group_exists = self.point_manager.get_group_info(group_name)
                        if not group_exists:
                            return f"群组 '{group_name}' 不存在，无法更新用户积分。请先添加群组。"
                        success = self.point_manager.update_user_points(group_name, nickname, points)
                        if success:
                            return f"用户 '{nickname}' 在群组 '{group_name}' 的积分已更新，变化量为 {points}。"
                        else:
                            return f"用户 '{nickname}' 的积分更新失败。"

                    # 查询积分命令
                    elif cmd == 'query_individual_points':
                        (name,) = match.groups()
                        points = self.point_manager.get_individual_points(name)
                        if points is not None:
                            return f"个人 '{name}' 当前的积分为 {points}。"
                        else:
                            return f"未找到个人 '{name}' 的积分信息。"

                    elif cmd == 'query_whole_group_points':
                        (group_name,) = match.groups()
                        points = self.point_manager.get_group_points(group_name)
                        if points is not None:
                            return f"整体群组 '{group_name}' 当前的积分为 {points}。"
                        else:
                            return f"未找到整体群组 '{group_name}' 的积分信息。"

                    elif cmd == 'query_user_points':
                        group_name, nickname = match.groups()
                        points = self.point_manager.get_user_points(group_name, nickname)
                        if points is not None:
                            return f"用户 '{nickname}' 在群组 '{group_name}' 当前的积分为 {points}。"
                        else:
                            return f"未找到用户 '{nickname}' 在群组 '{group_name}' 的积分信息。"

                    elif cmd == 'disable_all_instances':
                        # 禁用全部实例
                        response = self.browser_controller.disable_all_instances()
                        return response

                    elif cmd == 'query_current_account_usage':
                        # 查询当前账号使用情况
                        usage_info = self.browser_controller.get_current_account_usage()
                        return usage_info

                    # 下载份数查询命令处理逻辑
                    elif cmd.startswith('query_group') and cmd.endswith('_downloads'):
                        group_name = match.group(1)
                        recipient_type = 'whole_group'  # 假设群组都是整体性群组
                        if cmd == 'query_group_today_downloads':
                            count = self.point_manager.get_today_download_count(recipient_type, group_name)
                            return f"群组 '{group_name}' 今天的下载份数为 {count}。"
                        elif cmd == 'query_group_this_week_downloads':
                            count = self.point_manager.get_week_download_count(recipient_type, group_name)
                            return f"群组 '{group_name}' 这周的下载份数为 {count}。"
                        elif cmd == 'query_group_last_week_downloads':
                            count = self.point_manager.get_last_week_download_count(recipient_type, group_name)
                            return f"群组 '{group_name}' 上周的下载份数为 {count}。"
                        elif cmd == 'query_group_this_month_downloads':
                            count = self.point_manager.get_month_download_count(recipient_type, group_name)
                            return f"群组 '{group_name}' 这个月的下载份数为 {count}。"
                        elif cmd == 'query_group_last_month_downloads':
                            count = self.point_manager.get_last_month_download_count(recipient_type, group_name)
                            return f"群组 '{group_name}' 上个月的下载份数为 {count}。"

                    elif cmd.startswith('query_individual') and cmd.endswith('_downloads'):
                        individual_name = match.group(1)
                        recipient_type = 'individual'
                        if cmd == 'query_individual_today_downloads':
                            count = self.point_manager.get_today_download_count(recipient_type, individual_name)
                            return f"个人 '{individual_name}' 今天的下载份数为 {count}。"
                        elif cmd == 'query_individual_this_week_downloads':
                            count = self.point_manager.get_week_download_count(recipient_type, individual_name)
                            return f"个人 '{individual_name}' 这周的下载份数为 {count}。"
                        elif cmd == 'query_individual_last_week_downloads':
                            count = self.point_manager.get_last_week_download_count(recipient_type, individual_name)
                            return f"个人 '{individual_name}' 上周的下载份数为 {count}。"
                        elif cmd == 'query_individual_this_month_downloads':
                            count = self.point_manager.get_month_download_count(recipient_type, individual_name)
                            return f"个人 '{individual_name}' 这个月的下载份数为 {count}。"
                        elif cmd == 'query_individual_last_month_downloads':
                            count = self.point_manager.get_last_month_download_count(recipient_type, individual_name)
                            return f"个人 '{individual_name}' 上个月的下载份数为 {count}。"

                    elif cmd == 'query_all_groups_today_downloads':
                        counts = self.point_manager.get_all_groups_today_download_counts()
                        if counts:
                            message_lines = ["所有群组今天的下载量："]
                            for item in counts:
                                message_lines.append(f"群组 '{item['group_name']}': {item['download_count']} 次")
                            return '\n'.join(message_lines)
                        else:
                            return "没有群组的下载记录。"

                    elif cmd == 'query_all_groups_this_week_downloads':
                        counts = self.point_manager.get_all_groups_week_download_counts()
                        if counts:
                            message_lines = ["所有群组这周的下载量："]
                            for item in counts:
                                message_lines.append(f"群组 '{item['group_name']}': {item['download_count']} 次")
                            return '\n'.join(message_lines)
                        else:
                            return "没有群组的下载记录。"

                    # 处理非配置文件相关的管理员命令
                    elif cmd == 'query_all_instances_status':
                        status = self.browser_controller.query_all_instances_status()
                        logging.info("查询所有实例状态成功")
                        return status

                    elif cmd == 'check_all_instances_status':
                        self.browser_controller.check_instances_status()
                        return "已执行所有实例的状态检查。"

                    elif cmd == 'set_instance_admin_intervention':
                        instance_id, status_str = match.groups()
                        status = True if status_str.lower() == 'true' else False
                        response = self.browser_controller.set_instance_admin_intervention(instance_id, status)
                        return response

                    # 配置文件命令处理逻辑
                    elif cmd in ['add_monitor_group', 'remove_monitor_group',
                                 'add_monitor_individual', 'remove_monitor_individual',
                                 'add_whole_group', 'remove_whole_group',
                                 'add_non_whole_group', 'remove_non_whole_group']:
                        if cmd.startswith('add_monitor_group') or cmd.startswith('remove_monitor_group'):
                            group_names = match.group(1)
                            action = 'add' if 'add' in cmd else 'remove'
                            return self.modify_monitor_groups(group_names, action)

                        elif cmd.startswith('add_monitor_individual') or cmd.startswith('remove_monitor_individual'):
                            individual_names = match.group(1)
                            action = 'add' if 'add' in cmd else 'remove'
                            return self.modify_monitor_individuals(individual_names, action)

                        elif cmd.startswith('add_whole_group') or cmd.startswith('remove_whole_group'):
                            group_names = match.group(1)
                            group_type = 'whole'
                            action = 'add' if 'add' in cmd else 'remove'
                            return self.modify_group_type(group_names, group_type, action)

                        elif cmd.startswith('add_non_whole_group') or cmd.startswith('remove_non_whole_group'):
                            group_names = match.group(1)
                            group_type = 'non_whole'
                            action = 'add' if 'add' in cmd else 'remove'
                            return self.modify_group_type(group_names, group_type, action)

                    # 其他命令处理逻辑
                    elif cmd == 'help':
                        return self.get_help_message()

                    elif cmd == 'query_logs':
                        if self.notifier:
                            logs = self.get_last_n_logs(20)
                            if logs:
                                self.send_long_message(logs)
                            else:
                                self.notifier.notify("无法读取日志文件或日志文件为空。")
                        else:
                            logging.error("Notifier 未设置，无法发送日志。")
                        return None

                except Exception as e:
                    logging.error(f"执行命令 '{cmd}' 时发生错误: {e}", exc_info=True)
                    if self.error_handler:
                        self.error_handler.handle_exception(e)
                    return f"执行命令时发生错误: {e}"

        logging.warning(f"未知的管理员命令：{message}")
        return "未知的命令，请检查命令格式。"

    def modify_monitor_groups(self, group_names: str, action: str) -> str:
        """添加或删除监听群组"""
        try:
            groups = [name.strip() for name in group_names.split(',') if name.strip()]
            wechat_config = self.config.get('wechat', {})
            monitor_groups = wechat_config.get('monitor_groups', [])

            if action == 'add':
                for group in groups:
                    if group not in monitor_groups:
                        monitor_groups.append(group)
            elif action == 'remove':
                for group in groups:
                    if group in monitor_groups:
                        monitor_groups.remove(group)
            else:
                return "未知的操作类型。"

            # 更新配置
            wechat_config['monitor_groups'] = monitor_groups
            self.config['wechat'] = wechat_config
            ConfigManager.save_config(self.config)

            # 同步更新上传目标
            self.sync_upload_targets()

            message = f"已{'添加' if action == 'add' else '删除'}监听群组：{', '.join(groups)}"
            logging.info(message)
            return message
        except Exception as e:
            logging.error(f"修改监听群组时发生错误: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_exception(e)
            return f"修改监听群组时发生错误: {e}"

    def modify_monitor_individuals(self, individual_names: str, action: str) -> str:
        """添加或删除监听个人"""
        try:
            individuals = [name.strip() for name in individual_names.split(',') if name.strip()]
            wechat_config = self.config.get('wechat', {})
            target_individuals = wechat_config.get('target_individuals', [])

            if action == 'add':
                for individual in individuals:
                    if individual not in target_individuals:
                        target_individuals.append(individual)
            elif action == 'remove':
                for individual in individuals:
                    if individual in target_individuals:
                        target_individuals.remove(individual)
            else:
                return "未知的操作类型。"

            # 更新配置
            wechat_config['target_individuals'] = target_individuals
            self.config['wechat'] = wechat_config
            ConfigManager.save_config(self.config)

            # 同步更新上传目标
            self.sync_upload_targets()

            message = f"已{'添加' if action == 'add' else '删除'}监听个人：{', '.join(individuals)}"
            logging.info(message)
            return message
        except Exception as e:
            logging.error(f"修改监听个人时发生错误: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_exception(e)
            return f"修改监听个人时发生错误: {e}"

    def modify_group_type(self, group_names: str, group_type: str, action: str) -> str:
        """添加或删除整体群组或非整体群组"""
        try:
            groups = [name.strip() for name in group_names.split(',') if name.strip()]
            group_key = 'whole_groups' if group_type == 'whole' else 'non_whole_groups'
            wechat_config = self.config.get('wechat', {})
            group_types = wechat_config.get('group_types', {})

            if action == 'add':
                for group in groups:
                    if group not in group_types.get(group_key, []):
                        group_types.setdefault(group_key, []).append(group)
                    # 从另一类型的群组中移除
                    other_key = 'non_whole_groups' if group_key == 'whole_groups' else 'whole_groups'
                    if group in group_types.get(other_key, []):
                        group_types[other_key].remove(group)
                message = f"已添加{group_type}群组：{', '.join(groups)}"
            elif action == 'remove':
                for group in groups:
                    if group in group_types.get(group_key, []):
                        group_types[group_key].remove(group)
                message = f"已删除{group_type}群组：{', '.join(groups)}"
            else:
                return "未知的操作类型。"

            # 更新配置
            wechat_config['group_types'] = group_types
            self.config['wechat'] = wechat_config
            ConfigManager.save_config(self.config)

            # 更新数据库中群组的类型
            for group in groups:
                is_whole = (group_type == 'whole' and action == 'add')
                self.point_manager.ensure_group(group, is_whole=is_whole)

            logging.info(message)
            return message
        except Exception as e:
            logging.error(f"修改群组类型时发生错误: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_exception(e)
            return f"修改群组类型时发生错误: {e}"

    def sync_upload_targets(self):
        """同步上传目标和监听目标"""
        try:
            upload_config = self.config.get('upload', {})
            upload_config['target_groups'] = self.config.get('wechat', {}).get('monitor_groups', []).copy()
            upload_config['target_individuals'] = self.config.get('wechat', {}).get('target_individuals', []).copy()
            self.config['upload'] = upload_config
            ConfigManager.save_config(self.config)
            logging.info("上传目标已同步更新")
        except Exception as e:
            logging.error(f"同步上传目标时发生错误: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_exception(e)
            logging.warning("Uploader 未设置，无法同步上传目标")

    def get_help_message(self) -> str:
        """返回可用命令的帮助信息，按照分类整理"""
        help_message = (
            "📚 可用命令如下：\n\n"

            "=== 数据库命令 ===\n"
            "1. 更新个人积分 <个人名称> <变化量>\n"
            "   示例：更新个人积分 User1 -10\n\n"

            "2. 更新群组积分 <群组名称> <变化量>\n"
            "   示例：更新群组积分 群组B -20\n\n"

            "3. 更新用户积分 群组名: <群组名称> 昵称: <用户昵称> 积分: [更新积分]\n"
            "   示例：更新用户积分 群组名: 群组A 昵称: 用户1 积分: 50\n\n"

            "4. 查询个人积分 <个人名称>\n"
            "   示例：查询个人积分 User1\n\n"

            "5. 查询群组积分 <群组名称>\n"
            "   示例：查询群组积分 群组B\n\n"

            "6. 查询用户积分 群组名: <群组名称> 昵称: <用户昵称>\n"
            "   示例：查询用户积分 群组名: 群组A 昵称: 用户1\n\n"

            "=== 配置文件命令 ===\n"
            "7. 添加监听群组 <群组名称1>,<群组名称2>\n"
            "   示例：添加监听群组 群组A,群组B\n\n"

            "8. 删除监听群组 <群组名称1>,<群组名称2>\n"
            "   示例：删除监听群组 群组A,群组B\n\n"

            "9. 添加监听个人 <个人名称1>,<个人名称2>\n"
            "   示例：添加监听个人 个人1,个人2\n\n"

            "10. 删除监听个人 <个人名称1>,<个人名称2>\n"
            "    示例：删除监听个人 个人1,个人2\n\n"

            "11. 添加整体群组 <群组名称1>,<群组名称2>\n"
            "    示例：添加整体群组 群组A,群组B\n\n"

            "12. 删除整体群组 <群组名称1>,<群组名称2>\n"
            "    示例：删除整体群组 群组A,群组B\n\n"

            "13. 添加非整体群组 <群组名称1>,<群组名称2>\n"
            "    示例：添加非整体群组 群组A,群组B\n\n"

            "14. 删除非整体群组 <群组名称1>,<群组名称2>\n"
            "    示例：删除非整体群组 群组A,群组B\n\n"

            "15. 帮助\n"
            "    示例：帮助\n\n"

            "=== 实例管理命令 ===\n"
            "18. 禁用全部实例\n"
            "    示例：禁用全部实例\n\n"

            "19. 查询群组下载份数 <群组名称> <时间段>\n"
            "    示例：查询群组下载份数 群组A 今天\n"
            "    示例：查询群组下载份数 群组A 这周\n"
            "    示例：查询群组下载份数 群组A 上周\n\n"

            "20. 查询个人下载份数 <个人名称> <时间段>\n"
            "    示例：查询个人下载份数 用户1 今天\n"
            "    示例：查询个人下载份数 用户1 这周\n"
            "    示例：查询个人下载份数 用户1 上周\n\n"

            "21. 查询当前账号使用情况\n"
            "    示例：查询当前账号使用情况\n\n"

            "22. 查询所有实例状态\n"
            "    示例：查询所有实例状态\n\n"

            "23. 检查所有实例状态\n"
            "    示例：检查所有实例状态\n\n"

            "24. 设置实例需要管理员介入 <实例ID> <True/False>\n"
            "    示例：设置实例需要管理员介入 xkw1 True\n\n"

            "📄 【命令模板】\n"
            "发送序号以获取对应的命令模板。\n"
            "例如，发送 '1' 获取命令模板。"
        )
        return help_message

    def send_long_message(self, message: str, max_length: int = 2000):
        """将长消息分割为多个部分并逐段发送"""
        try:
            for i in range(0, len(message), max_length):
                if self.notifier:
                    self.notifier.notify(message[i:i + max_length])
        except Exception as e:
            logging.error(f"发送长消息时出错: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_exception(e)

    def get_last_n_logs(self, n: int) -> str:
        """获取最后 n 条日志"""
        try:
            # 加载配置
            config = ConfigManager.load_config()
            log_dir = config.get('logging', {}).get('directory', 'logs')

            # 确保日志目录是绝对路径
            log_dir = os.path.abspath(log_dir)

            # 获取当前日期的日志文件名
            current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            log_file_path = os.path.join(log_dir, f"{current_date}.log")

            if not os.path.exists(log_file_path):
                logging.error(f"日志文件未找到: {log_file_path}")
                return "日志文件未找到。"

            with open(log_file_path, 'r', encoding='utf-8') as log_file:
                lines = log_file.readlines()
                return ''.join(lines[-n:])
        except Exception as e:
            logging.error(f"读取日志文件时发生错误: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_exception(e)
            return ""

    def extract_urls(self, message: str) -> List[str]:
        """
        从消息中提取所有有效的URL。

        参数:
        - message: 管理员发送的消息。

        返回:
        - URL字符串列表，若未找到则返回空列表。
        """
        url_pattern = r'https?://(?:www\.|m\.)?zxxk\.com/soft/\d+\.html(?:[?#]\S+)?'
        return re.findall(url_pattern, message)

    def extract_soft_id_from_url(self, url: str) -> Optional[str]:
        """
        从给定的下载链接中提取 soft_id。

        参数:
        - url: 包含 soft_id 的下载链接。

        返回:
        - 提取到的 soft_id，若未找到则返回 None。
        """
        pattern = r'/soft/(\d+)\.html'
        match = re.search(pattern, url)
        if match:
            soft_id = match.group(1)
            logging.info(f"从链接中提取到 soft_id: {soft_id}")
            return soft_id
        else:
            logging.error(f"无法从链接中提取 soft_id: {url}")
            return None

    def get_soft_id_logs(self, soft_id: str) -> str:
        """获取当天日志中与指定soft_id相关的日志行。"""
        try:
            config = ConfigManager.load_config()
            log_dir = config.get('logging', {}).get('directory', 'logs')

            # 确保日志目录是绝对路径
            log_dir = os.path.abspath(log_dir)

            # 获取当前日期的日志文件名
            current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            log_file_path = os.path.join(log_dir, f"{current_date}.log")

            if not os.path.exists(log_file_path):
                logging.error(f"日志文件未找到: {log_file_path}")
                return "日志文件未找到。"

            filtered_lines = []
            with open(log_file_path, 'r', encoding='utf-8') as log_file:
                for line in log_file:
                    if f"soft_id:{soft_id}" in line:
                        filtered_lines.append(line)

            if filtered_lines:
                return "".join(filtered_lines)
            else:
                return ""
        except Exception as e:
            logging.error(f"读取日志文件时发生错误: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_exception(e)
            return ""
