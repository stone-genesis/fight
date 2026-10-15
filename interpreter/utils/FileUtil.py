import os

class FileUtils:
    @staticmethod
    def f_open_read(path):
        """读取全文"""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def f_write(path, content):
        """覆盖写入"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(str(content))
            return True

    @staticmethod
    def f_append(path, content):
        """追加写入"""
        with open(path, 'a', encoding='utf-8') as f:
            f.write(str(content))
            return True

    @staticmethod
    def f_exists(path):
        """判断是否存在"""
        return os.path.exists(path)

    @staticmethod
    def f_delete(path):
        """删除文件"""
        if os.path.exists(path):
            os.remove(path)
            return True
        print(f"文件{path}不存在")
        return False

    @staticmethod
    def f_size(path):
        """获取字节大小"""
        if os.path.exists(path):
            return os.path.getsize(path)
        return -1

    @staticmethod
    def f_list_dir(path):
        """列出目录下的文件"""
        if os.path.isdir(path):
            return os.listdir(path)
        return []
    @staticmethod
    def f_read_text(path):
        """读取文本文件"""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()