"""
    系统工具库
"""
import os
import sys
import platform
import subprocess


class SystemUtils:

    @staticmethod
    def f_osName():
        """操作系统名称"""
        return platform.system()

    @staticmethod
    def f_osVersion():
        """操作系统版本"""
        return platform.version()

    @staticmethod
    def f_pythonVersion():
        """Python版本"""
        return platform.python_version()

    @staticmethod
    def f_cpuCount()->int:
        """CPU核心数"""
        return os.cpu_count()

    @staticmethod
    def f_homeDir():
        """用户主目录"""
        return os.path.expanduser('~')

    @staticmethod
    def f_currentDir():
        """当前工作目录"""
        return os.getcwd()

    @staticmethod
    def f_getEnv(name, default=""):
        """获取环境变量"""
        return os.environ.get(name, default)

    @staticmethod
    def f_setEnv(name, value):
        """设置环境变量"""
        os.environ[name] = value
        return True

    @staticmethod
    def f_execute(command):
        """执行系统命令"""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "code": result.returncode
            }
        except Exception as e:
            return {"error": str(e), "code": -1}

    @staticmethod
    def f_exit(code=0):
        """退出程序"""
        sys.exit(code)