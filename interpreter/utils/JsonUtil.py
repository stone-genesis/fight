"""
    JSON 工具库
    使用: jsonParse, jsonStringify, jsonGet 等
"""
import json


class JsonUtils:

    @staticmethod
    def jsonParse(json_string):
        """JSON 字符串转对象"""
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            return {"error": f"JSON 解析错误: {str(e)}"}

    @staticmethod
    def jsonStringify(obj, pretty=False):
        """对象转 JSON 字符串"""
        try:
            if pretty:
                return json.dumps(obj, ensure_ascii=False, indent=2)
            return json.dumps(obj, ensure_ascii=False)
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def jsonGet(obj, path):
        """通过路径获取 JSON 值
        path: "user.name" 或 "users.0.name"
        """
        try:
            keys = path.split('.')
            result = obj
            for key in keys:
                if isinstance(result, list):
                    result = result[int(key)]
                else:
                    result = result[key]
            return result
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def jsonSet(obj, path, value):
        """通过路径设置 JSON 值"""
        try:
            keys = path.split('.')
            current = obj
            for key in keys[:-1]:
                if isinstance(current, list):
                    current = current[int(key)]
                else:
                    current = current[key]

            last_key = keys[-1]
            if isinstance(current, list):
                current[int(last_key)] = value
            else:
                current[last_key] = value
            return obj
        except Exception:
            return obj

    @staticmethod
    def jsonHas(obj, path):
        """检查路径是否存在"""
        try:
            keys = path.split('.')
            result = obj
            for key in keys:
                if isinstance(result, list):
                    result = result[int(key)]
                else:
                    result = result[key]
            return True
        except (KeyError, IndexError, TypeError):
            return False

    @staticmethod
    def jsonKeys(obj):
        """获取所有键"""
        if isinstance(obj, dict):
            return list(obj.keys())
        return []

    @staticmethod
    def jsonValues(obj):
        """获取所有值"""
        if isinstance(obj, dict):
            return list(obj.values())
        return []

if __name__ == '__main__':
    data = '{"name": "Tom", "age": 20}'
    obj = JsonUtils.jsonParse(data)
    print(obj)
    print(JsonUtils.jsonGet(obj, "name"))