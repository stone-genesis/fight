"""
    日期处理工具库（比Time更专注日期）
"""
from datetime import datetime, timedelta
import calendar

class DateUtils:

    @staticmethod
    def today():
        """今天日期 YYYY-MM-DD"""
        return datetime.now().strftime('%Y-%m-%d')

    @staticmethod
    def now():
        """当前时间 YYYY-MM-DD HH:MM:SS"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def format(date_str, from_fmt, to_fmt):
        """日期格式转换"""
        dt = datetime.strptime(date_str, from_fmt)
        return dt.strftime(to_fmt)

    @staticmethod
    def addDays(date_str, days):
        """加减天数"""
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        result = dt + timedelta(days=days)
        return result.strftime('%Y-%m-%d')

    @staticmethod
    def addMonths(date_str, months):
        """加减月数"""
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        month = dt.month + months
        year = dt.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return datetime(year, month, day).strftime('%Y-%m-%d')

    @staticmethod
    def diffDays(date1, date2):
        """计算天数差"""
        d1 = datetime.strptime(date1, '%Y-%m-%d')
        d2 = datetime.strptime(date2, '%Y-%m-%d')
        return (d2 - d1).days

    @staticmethod
    def dayOfWeek(date_str):
        """星期几 (0=周一, 6=周日)"""
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.weekday()

    @staticmethod
    def dayOfWeekName(date_str):
        """星期几（中文）"""
        names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        return names[DateUtils.dayOfWeek(date_str)]

    @staticmethod
    def isLeapYear(year):
        """是否闰年"""
        return calendar.isleap(year)

    @staticmethod
    def daysInMonth(year, month):
        """某月有多少天"""
        return calendar.monthrange(year, month)[1]

    @staticmethod
    def isBefore(date1, date2):
        """date1 是否在 date2 之前"""
        d1 = datetime.strptime(date1, '%Y-%m-%d')
        d2 = datetime.strptime(date2, '%Y-%m-%d')
        return d1 < d2

    @staticmethod
    def isAfter(date1, date2):
        """date1 是否在 date2 之后"""
        d1 = datetime.strptime(date1, '%Y-%m-%d')
        d2 = datetime.strptime(date2, '%Y-%m-%d')
        return d1 > d2

    @staticmethod
    def age(birth_date):
        """根据生日计算年龄"""
        birth = datetime.strptime(birth_date, '%Y-%m-%d')
        today = datetime.now()
        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1
        return age