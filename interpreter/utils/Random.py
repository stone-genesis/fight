import random

class RandomUtils:
    @staticmethod
    def f_setSeed(seed: int) -> None:
        """设置随机数种子"""
        random.seed(seed)

    @staticmethod
    def f_getInt(a: int, b: int) -> int:
        """生成指定范围内的随机整数"""
        return random.randint(a, b)

    @staticmethod
    def f_getFloat01() -> float:
        """生成0到1之间的随机浮点数"""
        return random.random()

    @staticmethod
    def f_getFloatRange(a: float, b: float) -> float:
        """生成指定范围内的随机浮点数"""
        return random.uniform(a, b)

    @staticmethod
    def f_getChoice(sequence:list):
        """从序列中随机选择一个元素"""
        return random.choice(sequence)

    @staticmethod
    def f_shuffled(lst: list) -> list:
        """随机打乱列表顺序"""
        random.shuffle(lst)
        return lst

    @staticmethod
    def f_getBool() -> bool:
        """生成随机布尔值"""
        return random.choice([True, False])

    @staticmethod
    def f_getSystemFloat() -> float:
        """使用操作系统的随机源生成0到1之间的随机浮点数"""
        return random.SystemRandom().random()
