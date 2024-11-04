# src/point_manager.py

import sqlite3
import threading
import logging
from typing import List, Optional, Dict

class PointManager:
    def __init__(self, db_path='points.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.lock = threading.RLock()
        self.initialize_database()
        logging.info("PointManager 数据库已初始化")

    def initialize_database(self):
        """
        创建 groups、users 和 recipients 表
        """
        try:
            # 创建 groups 表，增加 is_whole 字段
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    name TEXT PRIMARY KEY,
                    remaining_points INTEGER DEFAULT 1000,
                    is_whole BOOLEAN DEFAULT 0  -- 0 表示非整体性群组，1 表示整体性群组
                )
            ''')

            # 创建 users 表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    group_name TEXT,
                    nickname TEXT,
                    remaining_points INTEGER DEFAULT 100,
                    PRIMARY KEY (group_name, nickname),
                    FOREIGN KEY (group_name) REFERENCES groups(name) ON DELETE CASCADE
                )
            ''')

            # 创建 recipients 表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS recipients (
                    name TEXT PRIMARY KEY,
                    remaining_points INTEGER DEFAULT 100
                )
            ''')

            self.conn.commit()
            logging.info("PointManager 数据库表已创建或已存在")
        except Exception as e:
            logging.error(f"初始化 PointManager 数据库时出错：{e}", exc_info=True)

    # 确保接收者存在（个人）
    def ensure_recipient(self, recipient_name: str, initial_points: int = 100):
        with self.lock:
            self.cursor.execute('''
                INSERT OR IGNORE INTO recipients (name, remaining_points)
                VALUES (?, ?)
            ''', (recipient_name, initial_points))
            self.conn.commit()

    # 添加接收者（新方法）
    def add_recipient(self, recipient_name: str, initial_points: int = 100) -> str:
        """
        添加一个新的接收者（个人）。如果接收者已存在，则返回提示信息。
        """
        with self.lock:
            try:
                self.cursor.execute('''
                    INSERT INTO recipients (name, remaining_points)
                    VALUES (?, ?)
                ''', (recipient_name, initial_points))
                self.conn.commit()
                logging.info(f"接收者 '{recipient_name}' 已添加，初始剩余积分为 {initial_points}。")
                return f"接收者 '{recipient_name}' 已添加，初始剩余积分为 {initial_points}。"
            except sqlite3.IntegrityError:
                logging.warning(f"接收者 '{recipient_name}' 已存在。")
                return f"接收者 '{recipient_name}' 已存在。"
            except Exception as e:
                logging.error(f"添加接收者 '{recipient_name}' 时出错：{e}", exc_info=True)
                return f"添加接收者时发生错误：{e}"

    # 确保群组存在
    def ensure_group(self, group_name: str, is_whole: Optional[bool] = None, initial_points: int = 1000):
        try:
            with self.lock:
                self.cursor.execute('SELECT is_whole FROM groups WHERE name = ?', (group_name,))
                result = self.cursor.fetchone()
                if result is None:
                    # 群组不存在，插入新记录
                    if is_whole is not None:
                        self.cursor.execute('''
                            INSERT INTO groups (name, remaining_points, is_whole)
                            VALUES (?, ?, ?)
                        ''', (group_name, initial_points, int(is_whole)))
                    else:
                        self.cursor.execute('''
                            INSERT INTO groups (name, remaining_points)
                            VALUES (?, ?)
                        ''', (group_name, initial_points))
                    self.conn.commit()
                    logging.debug(f"群组 '{group_name}' 已添加，is_whole={is_whole}")
                else:
                    # 群组已存在，不修改 is_whole 值
                    logging.debug(f"群组 '{group_name}' 已存在，is_whole={bool(result[0])}")
        except Exception as e:
            logging.error(f"在 ensure_group 中发生错误: {e}", exc_info=True)

    # 设置群组的 is_whole 值
    def set_group_is_whole(self, group_name: str, is_whole: bool):
        with self.lock:
            self.cursor.execute('''
                UPDATE groups SET is_whole = ? WHERE name = ?
            ''', (int(is_whole), group_name))
            self.conn.commit()
            logging.debug(f"群组 '{group_name}' 的 is_whole 已更新为 {is_whole}")

    # 确保用户存在于群组中
    def ensure_user(self, group_name: str, nickname: str, initial_points: int = 100):
        with self.lock:
            self.ensure_group(group_name)  # 确保群组存在
            self.cursor.execute('''
                INSERT OR IGNORE INTO users (group_name, nickname, remaining_points)
                VALUES (?, ?, ?)
            ''', (group_name, nickname, initial_points))
            self.conn.commit()
            logging.debug(f"用户 '{nickname}' 已确保存在于群组 '{group_name}' 中")

    # 检查整体性群组是否有足够的积分
    def has_group_points(self, group_name: str, required_points: int = 1) -> bool:
        try:
            with self.lock:
                self.ensure_group(group_name)
                self.cursor.execute('''
                    SELECT remaining_points FROM groups WHERE name = ?
                ''', (group_name,))
                result = self.cursor.fetchone()
                logging.debug(f"查询群组 '{group_name}' 的积分结果: {result}")
                if result and result[0] >= required_points:
                    return True
                return False
        except Exception as e:
            logging.error(f"在 has_group_points 中发生错误: {e}", exc_info=True)
            return False

    # 检查非整体性群组成员是否有足够的积分
    def has_group_members_points(self, group_name: str, required_points: int = 1) -> bool:
        with self.lock:
            self.cursor.execute('''
                SELECT nickname, remaining_points FROM users WHERE group_name = ?
            ''', (group_name,))
            members = self.cursor.fetchall()
            for member in members:
                if member[1] < required_points:
                    return False
            return True

    # 检查个人接收者是否有足够的积分
    def has_recipient_points(self, recipient_name: str, required_points: int = 1) -> bool:
        with self.lock:
            self.ensure_recipient(recipient_name)
            self.cursor.execute('''
                SELECT remaining_points FROM recipients WHERE name = ?
            ''', (recipient_name,))
            result = self.cursor.fetchone()
            if result and result[0] >= required_points:
                return True
            return False

    # 检查个人用户是否有足够的积分
    def has_user_points(self, group_name: str, nickname: str, required_points: int = 1) -> bool:
        with self.lock:
            self.ensure_user(group_name, nickname)
            self.cursor.execute('''
                SELECT remaining_points FROM users WHERE group_name = ? AND nickname = ?
            ''', (group_name, nickname))
            result = self.cursor.fetchone()
            logging.debug(f"查询用户 '{nickname}' 在群组 '{group_name}' 中的积分结果: {result}")
            if result and result[0] >= required_points:
                return True
            return False

    # 扣除整体性群组的积分
    def deduct_whole_group_points(self, group_name: str, points: int = 1) -> bool:
        with self.lock:
            # 检查群组是否是整体性群组
            self.cursor.execute('''
                SELECT is_whole, remaining_points FROM groups WHERE name = ?
            ''', (group_name,))
            result = self.cursor.fetchone()
            if not result:
                logging.error(f"群组 '{group_name}' 不存在")
                return False

            is_whole = bool(result[0])
            if not is_whole:
                logging.error(f"群组 '{group_name}' 不是整体性群组")
                return False

            # 扣除群组的积分
            self.cursor.execute('''
                UPDATE groups
                SET remaining_points = remaining_points - ?
                WHERE name = ? AND remaining_points >= ?
            ''', (points, group_name, points))
            if self.cursor.rowcount == 0:
                return False  # 群组积分不足

            self.conn.commit()
            return True

    # 扣除非整体性群组成员的积分
    def deduct_non_whole_group_members_points(self, group_name: str, points: int = 1) -> bool:
        with self.lock:
            # 检查群组是否存在
            self.cursor.execute('''
                SELECT is_whole FROM groups WHERE name = ?
            ''', (group_name,))
            result = self.cursor.fetchone()
            if not result:
                logging.error(f"群组 '{group_name}' 不存在")
                return False

            is_whole = bool(result[0])
            if is_whole:
                logging.error(f"群组 '{group_name}' 是整体性群组，不适用于非整体性群组成员扣分")
                return False

            # 检查所有成员是否有足够的积分
            self.cursor.execute('''
                SELECT nickname, remaining_points FROM users WHERE group_name = ?
            ''', (group_name,))
            members = self.cursor.fetchall()
            for member in members:
                if member[1] < points:
                    logging.warning(f"用户 '{member[0]}' 在群组 '{group_name}' 中积分不足")
                    return False

            # 扣除每个成员的积分
            self.cursor.execute('''
                UPDATE users
                SET remaining_points = remaining_points - ?
                WHERE group_name = ? AND remaining_points >= ?
            ''', (points, group_name, points))

            self.conn.commit()
            return True

    # 扣除个人接收者的积分
    def deduct_recipient_points(self, recipient_name: str, points: int = 1) -> bool:
        with self.lock:
            self.cursor.execute('''
                UPDATE recipients
                SET remaining_points = remaining_points - ?
                WHERE name = ? AND remaining_points >= ?
            ''', (points, recipient_name, points))
            if self.cursor.rowcount == 0:
                return False
            self.conn.commit()
            return True

    # 扣除个人用户的积分
    def deduct_user_points(self, group_name: str, nickname: str, points: int = 1) -> bool:
        logging.debug(f"尝试从用户 '{nickname}' 在群组 '{group_name}' 中扣除 {points} 个积分")
        with self.lock:
            self.cursor.execute('''
                UPDATE users
                SET remaining_points = remaining_points - ?
                WHERE group_name = ? AND nickname = ? AND remaining_points >= ?
            ''', (points, group_name, nickname, points))
            if self.cursor.rowcount == 0:
                logging.warning(f"用户 '{nickname}' 的积分不足，无法扣除")
                return False  # 用户积分不足
            self.conn.commit()
            logging.debug(f"扣除积分成功")
            return True

    # 获取接收者信息
    def get_recipient_info(self, recipient_name: str) -> Optional[Dict]:
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT name, remaining_points FROM recipients WHERE name = ?
                ''', (recipient_name,))
                row = self.cursor.fetchone()
                if row:
                    return {'name': row[0], 'remaining_points': row[1]}
                else:
                    return None
        except Exception as e:
            logging.error(f"获取接收者信息时出错: {e}", exc_info=True)
            return None

    # 获取群组信息
    def get_group_info(self, group_name: str) -> Optional[Dict]:
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT name, remaining_points, is_whole FROM groups WHERE name = ?
                ''', (group_name,))
                row = self.cursor.fetchone()
                if row:
                    return {'name': row[0], 'remaining_points': row[1], 'is_whole': bool(row[2])}
                else:
                    return None
        except Exception as e:
            logging.error(f"获取群组信息时出错: {e}", exc_info=True)
            return None

    # 获取用户信息
    def get_user_info(self, group_name: str, nickname: str) -> Optional[Dict]:
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT group_name, nickname, remaining_points FROM users WHERE group_name = ? AND nickname = ?
                ''', (group_name, nickname))
                row = self.cursor.fetchone()
                if row:
                    return {'group_name': row[0], 'nickname': row[1], 'remaining_points': row[2]}
                else:
                    return None
        except Exception as e:
            logging.error(f"获取用户信息时出错: {e}", exc_info=True)
            return None

    # 获取所有接收者列表
    def get_all_recipients(self) -> List[str]:
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT name FROM recipients
                ''')
                rows = self.cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logging.error(f"获取所有接收者时出错: {e}", exc_info=True)
            return []

    # 更新接收者积分
    def update_recipient_points(self, recipient_name: str, delta: int) -> bool:
        with self.lock:
            self.ensure_recipient(recipient_name)
            self.cursor.execute('''
                UPDATE recipients
                SET remaining_points = remaining_points + ?
                WHERE name = ?
            ''', (delta, recipient_name))
            if self.cursor.rowcount == 0:
                return False
            self.conn.commit()
            return True

    # 更新群组积分
    def update_group_points(self, group_name: str, delta: int) -> bool:
        with self.lock:
            self.ensure_group(group_name)
            self.cursor.execute('''
                UPDATE groups
                SET remaining_points = remaining_points + ?
                WHERE name = ?
            ''', (delta, group_name))
            if self.cursor.rowcount == 0:
                return False
            self.conn.commit()
            return True

    # 更新用户积分
    def update_user_points(self, group_name: str, nickname: str, delta: int) -> bool:
        with self.lock:
            self.ensure_user(group_name, nickname)
            self.cursor.execute('''
                UPDATE users
                SET remaining_points = remaining_points + ?
                WHERE group_name = ? AND nickname = ?
            ''', (delta, group_name, nickname))
            if self.cursor.rowcount == 0:
                return False
            self.conn.commit()
            return True

    # 删除接收者
    def delete_recipient(self, recipient_name: str) -> bool:
        with self.lock:
            self.cursor.execute('''
                DELETE FROM recipients WHERE name = ?
            ''', (recipient_name,))
            if self.cursor.rowcount == 0:
                return False  # 接收者不存在
            self.conn.commit()
            return True

    # 删除群组
    def delete_group(self, group_name: str) -> bool:
        with self.lock:
            self.cursor.execute('''
                DELETE FROM groups WHERE name = ?
            ''', (group_name,))
            if self.cursor.rowcount == 0:
                return False  # 群组不存在
            self.conn.commit()
            return True

    # 删除用户
    def delete_user(self, group_name: str, nickname: str) -> bool:
        with self.lock:
            self.cursor.execute('''
                DELETE FROM users WHERE group_name = ? AND nickname = ?
            ''', (group_name, nickname))
            if self.cursor.rowcount == 0:
                return False  # 用户不存在
            self.conn.commit()
            return True

    # 获取所有群组列表
    def get_all_groups(self) -> List[str]:
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT name FROM groups
                ''')
                rows = self.cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logging.error(f"获取所有群组时出错: {e}", exc_info=True)
            return []

    # 获取群组中的所有用户
    def get_all_users_in_group(self, group_name: str) -> List[str]:
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT nickname FROM users WHERE group_name = ?
                ''', (group_name,))
                rows = self.cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logging.error(f"获取群组 '{group_name}' 中的用户时出错: {e}", exc_info=True)
            return []

    # 获取所有用户列表
    def get_all_users(self) -> List[Dict]:
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT group_name, nickname FROM users
                ''')
                rows = self.cursor.fetchall()
                return [{'group_name': row[0], 'nickname': row[1]} for row in rows]
        except Exception as e:
            logging.error(f"获取所有用户时出错: {e}", exc_info=True)
            return []

    # 关闭数据库连接
    def close(self):
        with self.lock:
            self.conn.close()
            logging.info("PointManager 数据库连接已关闭")
