from interpreter.Node import Node

# 导入第三方类
class ImportThirdPartyClassNode(Node):
    def __init__(self, class_name, file_path):
        self.class_name = class_name
        self.file_path = file_path
    def __repr__(self):
        return f"ImportThirdPartyClassNode(class_name = {self.class_name},file_path = {self.file_path})"

# import <类名>
class ImportBuiltinClassNode(Node):
    def __init__(self, class_name):
        self.class_name = class_name

    def __repr__(self):
        return f"ImportBuiltinClassNode(class_name = {self.class_name})"

# exports = ["x","y"]
class ExportsNode(Node):
    def __init__(self, exports_list: list,module_name: str = None):
        self.exports_list = exports_list
        self.module_name = module_name

    def __repr__(self):
        return f"ExportsNode(exports_list = {self.exports_list}),module_name = {self.module_name})"


class ImportModuleNode:
    def __init__(self, module_name, import_elements=None, import_whole_module=False, alias=None,is_builtin_module=True):
        self.module_name = module_name
        self.import_elements = import_elements if import_elements else []
        self.import_whole_module = import_whole_module
        self.alias = alias
        self.is_builtin = is_builtin_module

    def __repr__(self):
        if self.import_whole_module:
            if self.alias:
                return f"ImportModuleNode(module_name={self.module_name} as {self.alias},import_whole = {self.import_whole_module},is_builtin = {self.is_builtin})"
            return f"ImportModuleNode(module_name={self.module_name},import_whole = {self.import_whole_module},is_builtin = {self.is_builtin})"
        else:
            return f"ImportModuleNode(module_name={self.module_name}, elements={self.import_elements},import_whole = {self.import_whole_module},is_builtin_module={self.is_builtin})"
        
# import {模块名称} from "文件路径"
class ImportThirdPartyModuleNode(Node):
    def __init__(self, file_path, package_name, import_elements: list = [],import_whole_module=True, alias=None,):
        self.package_name = package_name
        self.file_path = file_path
        self.elements = []
        self.alias = alias
        # 引入的元素，比如 import {a,b} from "module"  这里的a,b就是import_elements
        self.import_elements = import_elements
        # 是否引入整个模块，比如 import "module"  这里的module就是import_whole_module
        self.import_whole_module = import_whole_module

    def __repr__(self):
        return f"ImportThirdPartyModuleNode(package_name={self.package_name}, file_path={self.file_path}, import_elements={self.import_elements}, import_whole_module={self.import_whole_module}, alias={self.alias})"


# 声明模块  比如 package module{ let x = 10;  }
class PackageDeclarationNode(Node):
    def __init__(self, package_name, package_body):
        self.package_name = package_name
        self.package_body = package_body

    def __repr__(self):
        return f"PackageDeclarationNode(package_name={self.package_name}, package_body={self.package_body})"

