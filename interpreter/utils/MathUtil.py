import math

class MathUtils:
    @staticmethod
    def f_sqrt(x: float) -> float:
        """计算平方根"""
        return math.sqrt(x)

    @staticmethod
    def f_factorial(n: int) -> int:
        """计算阶乘"""
        return math.factorial(n)

    @staticmethod
    def f_pow(base: float, exp: float) -> float:
        """计算幂"""
        return math.pow(base, exp)

    @staticmethod
    def f_sin(x: float) -> float:
        """计算正弦值"""
        return math.sin(x)

    @staticmethod
    def f_cos(x: float) -> float:
        """计算余弦值"""
        return math.cos(x)

    @staticmethod
    def f_tan(x: float) -> float:
        """计算正切值"""
        return math.tan(x)

    @staticmethod
    def f_asin(x: float) -> float:
        """计算反正弦值"""
        return math.asin(x)

    @staticmethod
    def f_acos(x: float) -> float:
        """计算反余弦值"""
        return math.acos(x)

    @staticmethod
    def f_atan(x: float) -> float:
        """计算反正切值"""
        return math.atan(x)

    @staticmethod
    def f_atan2(y: float, x: float) -> float:
        """计算反正切值，返回弧度"""
        return math.atan2(y, x)

    @staticmethod
    def f_exp(x: float) -> float:
        """计算e的x次方"""
        return math.exp(x)

    @staticmethod
    def f_log(x: float, base: float = math.e) -> float:
        """计算以base为底x的对数"""
        return math.log(x, base)

    @staticmethod
    def f_log10(x: float) -> float:
        """计算以10为底x的对数"""
        return math.log10(x)

    @staticmethod
    def f_ceil(x: float) -> int:
        """向上取整"""
        return math.ceil(x)

    @staticmethod
    def f_floor(x: float) -> int:
        """向下取整"""
        return math.floor(x)

    @staticmethod
    def f_round(x: float, n: int = 0) -> float:
        """四舍五入"""
        return round(x, n)

    @staticmethod
    def f_pi() -> float:
        """返回圆周率"""
        return math.pi

    @staticmethod
    def f_toDegrees(radians: float) -> float:
        """将弧度转换为角度"""
        return math.degrees(radians)

    @staticmethod
    def f_toRadians(degrees: float) -> float:
        """将角度转换为弧度"""
        return math.radians(degrees)

    @staticmethod
    def f_hypot(x: float, y: float) -> float:
        """计算欧几里得范数，即 sqrt(x*x + y*y)"""
        return math.hypot(x, y)

    @staticmethod
    def f_comb(n: int, k: int) -> int:
        """计算组合数 C(n, k)"""
        return math.comb(n, k)

    @staticmethod
    def f_perm(n: int, k: int) -> int:
        """计算排列数 P(n, k)"""
        return math.perm(n, k)

    @staticmethod
    def f_gcd(a: int, b: int) -> int:
        """计算最大公约数"""
        return math.gcd(a, b)

    @staticmethod
    def f_lcm(a: int, b: int) -> int:
        """计算最小公倍数"""
        return abs(a * b) // math.gcd(a, b) if a and b else 0
