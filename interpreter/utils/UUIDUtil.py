"""
    UUID 工具库
"""
import uuid
import time
import random
import string

class UUIDUtils:

    @staticmethod
    def f_uuid1():
        """生成 UUID1（基于时间戳）"""
        return str(uuid.uuid1())

    @staticmethod
    def f_uuid4():
        """生成 UUID4（随机）"""
        return str(uuid.uuid4())

    @staticmethod
    def f_shortId(length=8):
        """生成短 ID"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    @staticmethod
    def f_snowflakeId():
        """生成雪花 ID（简化版）"""
        timestamp = int(time.time() * 1000)
        random_part = random.randint(0, 4095)
        return (timestamp << 12) | random_part

    @staticmethod
    def f_nanoid(length=21):
        """生成 NanoID 风格的 ID"""
        alphabet = '_-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        return ''.join(random.choice(alphabet) for _ in range(length))

    @staticmethod
    def f_timestampId():
        """生成时间戳 ID"""
        return str(int(time.time() * 1000000))


if __name__ == '__main__':
    print(UUIDUtils.uuid4())
    print(UUIDUtils.shortId())
    print(UUIDUtils.snowflakeId())