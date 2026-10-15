"""
    压缩解压工具库
"""
import zipfile
import gzip
import shutil
import os


class CompressUtils:

    @staticmethod
    def zipFiles(file_list, zip_path):
        """压缩多个文件"""
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in file_list:
                    zf.write(file, os.path.basename(file))
            return True
        except:
            return False

    @staticmethod
    def zipFolder(folder_path, zip_path):
        """压缩文件夹"""
        try:
            shutil.make_archive(zip_path.replace('.zip', ''), 'zip', folder_path)
            return True
        except:
            return False

    @staticmethod
    def unzip(zip_path, extract_to):
        """解压ZIP"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_to)
            return True
        except:
            return False

    @staticmethod
    def listZip(zip_path):
        """列出ZIP内容"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                return zf.namelist()
        except:
            return []

    @staticmethod
    def gzipFile(file_path, gz_path):
        """GZIP压缩"""
        try:
            with open(file_path, 'rb') as f_in:
                with gzip.open(gz_path, 'wb') as f_out:
                    f_out.write(f_in.read())
            return True
        except:
            return False

    @staticmethod
    def gunzipFile(gz_path, file_path):
        """GZIP解压"""
        try:
            with gzip.open(gz_path, 'rb') as f_in:
                with open(file_path, 'wb') as f_out:
                    f_out.write(f_in.read())
            return True
        except:
            return False