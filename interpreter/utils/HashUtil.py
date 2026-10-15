"""
    哈希和加密工具库
    使用: md5, sha256, base64Encode 等
"""
import hashlib
import base64
import hmac


class HashUtils:

    @staticmethod
    def f_md5(text):
        """计算 MD5 哈希"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    @staticmethod
    def sha1(text):
        """计算 SHA1 哈希"""
        return hashlib.sha1(text.encode('utf-8')).hexdigest()

    @staticmethod
    def sha256(text):
        """计算 SHA256 哈希"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    @staticmethod
    def sha512(text):
        """计算 SHA512 哈希"""
        return hashlib.sha512(text.encode('utf-8')).hexdigest()

    @staticmethod
    def base64Encode(text):
        """Base64 编码"""
        return base64.b64encode(text.encode('utf-8')).decode('utf-8')

    @staticmethod
    def base64Decode(encoded):
        """Base64 解码"""
        try:
            return base64.b64decode(encoded).decode('utf-8')
        except Exception:
            return None

    @staticmethod
    def hmacSha256(key, message):
        """HMAC-SHA256 签名"""
        return hmac.new(
            key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def hashFile(file_path, algorithm="md5"):
        """计算文件哈希"""
        try:
            hash_func = getattr(hashlib, algorithm)()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            return f"Error: {str(e)}"


if __name__ == '__main__':
    print(HashUtils.md5("hello"))
    print(HashUtils.base64Encode("Hello World"))