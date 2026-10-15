"""
    网络请求工具库
    使用: httpGet, httpPost, downloadFile 等
"""
import urllib.request
import urllib.parse
import json

class NetworkUtils:

    @staticmethod
    def httpGet(url):
        """发送 GET 请求，返回响应内容"""
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def httpGetJson(url):
        """发送 GET 请求，返回 JSON 对象"""
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                content = response.read().decode('utf-8')
                return json.loads(content)
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def httpPost(url, data):
        """发送 POST 请求
        data: dict 类型的数据
        """
        try:
            post_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=post_data, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def httpPostJson(url, data):
        """发送 POST 请求（JSON 格式）"""
        try:
            json_data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=json_data, method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def downloadFile(url, save_path):
        """下载文件到指定路径"""
        try:
            urllib.request.urlretrieve(url, save_path)
            return True
        except Exception as e:
            return False

    @staticmethod
    def urlEncode(text):
        """URL 编码"""
        return urllib.parse.quote(text)

    @staticmethod
    def urlDecode(text):
        """URL 解码"""
        return urllib.parse.unquote(text)

    @staticmethod
    def parseUrl(url):
        """解析 URL，返回各部分"""
        parsed = urllib.parse.urlparse(url)
        return {
            "scheme": parsed.scheme,
            "host": parsed.netloc,
            "path": parsed.path,
            "query": parsed.query,
            "fragment": parsed.fragment
        }

    @staticmethod
    def buildUrl(base_url, params):
        """构建带参数的 URL"""
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"


if __name__ == '__main__':
    # 测试
    result = NetworkUtils.httpGet("https://pub.dev/")
    print(result)