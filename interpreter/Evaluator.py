import os
import re
from pathlib import Path
from interpreter.ClassNodes import ClassDeclarationNode, NewObjectNode, MethodCallNode, GetMemberNode, \
    CallClassInnerMethod, ThisNode, InterfaceNode, GetMemberNodeByThis, SuperMethodCallNode, SuperCallNode, SetMemberNode
from interpreter.ModuleNodes import ImportModuleNode, ExportsNode
from interpreter.MacroNodes import MacroDefinitionNode, MacroCallNode, BlockMacroNode
from interpreter.utils.FileDir import FileSystemUtils
from interpreter.utils.JsonUtil import JsonUtils
from interpreter.utils.Random import RandomUtils
from interpreter.utils.SystemUtil import SystemUtils
from interpreter.utils.Time import TimeUtils
from interpreter.utils.Type import CommonUtils
from interpreter.utils.DictUtil import DictUtils
from interpreter.utils.ListUtil import ListUtils
from interpreter.utils.NetworkUtil import NetworkUtils
from interpreter.utils.FileUtil import FileUtils
from interpreter.Nodes import AssignmentNode, NumberNode, BinaryOpNode, VariableNode, FunctionCallNode, StringNode, \
    ListNode, ObjectNode, FunctionDeclarationNode, IfStatementNode, BooleanNode, LoopNode, BreakNode, ReturnNode, \
    ListIndexNode, ObjectIndexNode, ForInNode, CommentNode, IfExprNode, \
    MatchExprNode, SwitchNode, DecontructAssignNode, ListDeconstructAssignNode, ForRangeNumberNode, TryCatchFinallyNode, \
    IncrementNode, DecrementNode, SetNode, CombineNode, MultiListIndexNode, StructDeclarationNode, StructAssignNode, \
    ModuleStructAssignNode, StructAccessNode, StructAccessAssignNode, EnumDeclarationNode, EnumAccessNode, ModuleEnumAccessNode, \
    ModuleClassInstantiationNode, ChainNode, DoWhileNode, ListGeneratorNode, AbsNode, \
    SerialCall, PlusAssignNode, MinusAssignNode, MultiplyAssignNode, DivideAssignNode, ObjectAssignNode, ListAssignNode, \
    UnaryOpNode, FunctionCombinationNode, PyExecNode, PyFnNode
from interpreter.Parser import Parser
from interpreter.utils.StringUtil import StringUtils
from interpreter.Tokenizer import Tokenizer
from interpreter.utils.MathUtil import MathUtils
from interpreter.utils.UUIDUtil import UUIDUtils


class BreakException(Exception):
    """自定义异常，用于处理循环中的 break 语句"""
    pass


class Environment:
    """带 parent 链的环境，实现词法作用域。

    parent 可以是另一个 Environment，也可以是普通 dict（兼容模块环境等旧代码）。
    变量查找沿链向上；赋值沿链找到"拥有该变量"的那一层写回，找不到才写本层。
    """
    def __init__(self, parent=None):
        self.parent = parent
        self._values = {}

    @staticmethod
    def _values_of(env):
        return env._values if isinstance(env, Environment) else env

    def _find(self, name):
        env = self
        while env is not None:
            values = self._values_of(env)
            if name in values:
                return values
            env = env.parent if isinstance(env, Environment) else None
        return None

    def get(self, name, default=None):
        values = self._find(name)
        return values[name] if values is not None else default

    def __getitem__(self, name):
        values = self._find(name)
        if values is None:
            raise KeyError(name)
        return values[name]

    def __contains__(self, name):
        return self._find(name) is not None

    def __setitem__(self, name, value):
        values = self._find(name)
        if values is None:
            values = self._values
        values[name] = value

    def define(self, name, value):
        self._values[name] = value

    def copy(self):
        new = Environment(self.parent)
        new._values = dict(self._values)
        return new

    def update(self, mapping):
        for k, v in mapping.items():
            self._values[k] = v

    def keys(self):
        return self._values.keys()

    def values(self):
        return self._values.values()

    def items(self):
        return self._values.items()

    def pop(self, name, default=None):
        if name in self._values:
            return self._values.pop(name)
        return default

    def __delitem__(self, name):
        if name in self._values:
            del self._values[name]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"Environment({self._values})"


class Evaluator:
    def __init__(self):
        # 环境变量
        self.environment = Environment()
        self.environment.define("arg_to_instance", {})  # 建立传入参数和实例的映射，用于多态的实现
        self.environment.define("instances", {})  # 记录创建的类的实例
        self.environment.define("constants", [])  # 记录声明的常量
        self.environment.define("objects", {})  # 导入的类exports和创建的对象
        self.environment.define("interfaces", {})  # 记录接口
        self.environment.define("structs", {})  # 记录结构体
        self.environment.define("enums", {})  # 记录枚举类型
        self.environment.define("macros", {})  # 记录宏定义
        # 保存一份内建环境快照
        self._builtin_env = self.environment
        self.current_object = None  # 当前this指向的对象
        self.current_class = None
        self.current_parent_class = None
        self._saved_objects = {}
        # 方法调用上下文
        self._static_context = False  # 当前是否在静态方法中
        self._internal_method_call = False  # 是否为类内部方法调用（允许访问私有方法）
        # 当前正在初始化的实例（用于super()调用时更新字段）
        self._current_instance = None

        # 内置模块
        self.builtin_modules = {}
        self.packages = {}  # 导入的模块
        # 模块缓存：{模块唯一ID(内置名或绝对路径): 模块环境字典}
        self.modules = {}
        # 模块别名映射：{别名/公开名称: 模块环境字典}
        self.module_aliases = {}
        #  循环导入检测栈
        self._loading_stack = []
        #exports的结构： {"math":["xx","yy"]}
        self.exports = {}  # 记录被导出的内容，用于辅助  {模块名称:[被导出的内容]}

        # ===== 预加载内置模块 =====
        for name in []:
            node = ImportModuleNode(
                module_name=name,
                import_whole_module=True,
                is_builtin_module=True
            )
            module_env = self.load_module(name, node)
            # 以模块ID缓存
            self.modules[name] = module_env
            # 作为内置模块暴露
            self.builtin_modules[name] = module_env
            # 作为公开名称暴露（支持 math.add 这种调用）
            self.module_aliases[name] = module_env

        # Python 执行环境（用于 py{...}）
        self._py_globals = {"__builtins__": __builtins__}

    def evaluate(self, node, env=None):
        """
            解析器的入口函数，根据不同的节点类型，调用相应的解析函数
            用于解析AST，得到具体的结果
            比如，对于NumberNode，调用evaluate_number()函数，返回数字的值
        """
        if env is not None:
            self.environment = env

        # 数据类型解析
        if isinstance(node, (int, float, bool, str, list, dict, tuple)):
            return node

        if isinstance(node, NumberNode):
            return self.evaluate_number(node)

        elif isinstance(node, StringNode):  # ""
            return self.evaluate_string(node)

        elif isinstance(node, ListNode):  # []
            return [self.evaluate(n) for n in node.elements]

        elif isinstance(node, ObjectNode):  # {}
            return self.evaluate_object(node)

        elif isinstance(node, VariableNode):
            # 检查是否是宏调用
            macro_result = self.check_and_expand_macro(node.value)
            if macro_result is not None:
                return macro_result
            return self.evaluate_variable(node)

        elif isinstance(node, BooleanNode):
            if node.value == "True":
                return True
            elif node.value == "False":
                return False
        # 语句解析
        elif isinstance(node, IfStatementNode):
            """
                  self.condition = condition
                  self.if_body = if_body
                  self.elif_ = elif_
                 self.else_ = else_
            """
            return self.evaluate_if_statement(node)
        # 表达式解析
        elif isinstance(node, BinaryOpNode):
            return self.evaluate_binary_op(node)

        # UnaryOpNode
        elif isinstance(node, UnaryOpNode):
            return self.evaluate_unary_op(node)
        elif isinstance(node, AssignmentNode):
            return self.evaluate_assignment(node)
        # 函数组合表达式节点（在赋值右侧创建组合函数）
        elif isinstance(node, CombineNode):
            # 这是函数组合表达式，例如 f & g & h
            # 需要返回一个组合函数对象
            return self.evaluate_combine_expr(node)
        # 循环解析
        elif isinstance(node, BreakNode):
            # 遇到break语句，抛出BreakException异常，
            # 然后在循环体外捕获这个异常，跳出循环
            raise BreakException()
        elif isinstance(node, LoopNode):
            return self.evaluate_loop(node)
        # for in 循环解析
        elif isinstance(node, ForInNode):
            return self.evaluate_for_in(node)

        # for(idx: 1..10){}
        elif isinstance(node, ForRangeNumberNode):
            return self.evaluate_for_range_number(node)

            # 函数方面
        elif isinstance(node, FunctionDeclarationNode):
            # 函数声明，不做任何事情
            return self.evaluate_function_declaration(node)

        elif isinstance(node, FunctionCallNode):
            return self.evaluate_function_call(node)

        elif isinstance(node, ReturnNode):
            # return self.evaluate(node.value) # 原来的代码
            return self.evaluate(node.value)  # 返回结果

        # 列表索引解析
        elif isinstance(node, ListIndexNode):
            return self.evaluate_list_index(node)

        # 多维索引节点
        elif isinstance(node, MultiListIndexNode):
            return self.evaluate_multi_list_index(node)

        elif isinstance(node, ObjectIndexNode):
            return self.evaluate_object_index(node)

        # 类声明解析
        elif isinstance(node, ClassDeclarationNode):
            return self.evaluate_class_declaration(node)

        elif isinstance(node, NewObjectNode):
            return self.evaluate_new_object_expr(node)

        # 方法调用解析  p->show();
        elif isinstance(node, MethodCallNode):
            try:
                return self.evaluate_method_call(node)
            except NameError as e:
                return self.execute_by_instance_type(node)

        # 类内部方法调用解析 this.xxx();
        elif isinstance(node, CallClassInnerMethod):
            return self.evaluate_call_class_inner_method(node)

            # SuperCallNode - 调用父类构造函数
        elif isinstance(node, SuperCallNode):
            return self.evaluate_super_call(node)

            # SuperMethodCallNode - 调用父类方法
        elif isinstance(node, SuperMethodCallNode):
            return self.evaluate_super_method_call(node)

        elif isinstance(node, GetMemberNode):
            return self.evaluate_get_instance_member(node)
        elif isinstance(node, GetMemberNodeByThis):
            return self.evaluate_get_member_by_this(node)
        # p->X = 10; 这样的实例属性赋值
        elif isinstance(node, SetMemberNode):
            return self.evaluate_set_member(node)
        # 模块机制
        elif isinstance(node, ImportModuleNode):
            return self.evaluate_import_module(node)
        elif isinstance(node,ExportsNode):
            return self.evaluate_exports_node(node)
        # 注释
        elif isinstance(node, CommentNode):
            # 注释不做任何事情
            pass

        # 解析  this.xxx();
        elif isinstance(node, CallClassInnerMethod):
            return self.evaluate_call_class_inner_method(node)

        # let z = if(true) x : y; 这样的表达式（注意不是语句）
        elif isinstance(node, IfExprNode):
            return self.evaluate_if_expr(node)


        # match表达式解析
        # let z = match(x) {
        #     case 1: 'One',
        #     case 2: 'Two',
        #     case 3: 'Three'
        # };
        elif isinstance(node, MatchExprNode):
            return self.evaluate_match_expr(node)

        # switch语句
        elif isinstance(node, SwitchNode):
            self.evaluate_switch_statement(node)

        # 解构赋值节点
        elif isinstance(node, DecontructAssignNode):
            return self.evaluate_decontruct_assign(node)

        # 列表解构赋值 解构列表赋值, 比如 let [a, _,b] = [1, 2,3];
        elif isinstance(node, ListDeconstructAssignNode):
            return self.evaluate_list_deconstruct_assign(node)

        # 接口定义
        elif isinstance(node, InterfaceNode):
            self.evaluate_interface_declaration(node)

        # try catch finally
        elif isinstance(node, TryCatchFinallyNode):
            return self.evaluate_try_catch_finally(node)

        # inc  id++;
        elif isinstance(node, IncrementNode):
            return self.evaluate_increment(node)

        # dec id--;
        elif isinstance(node, DecrementNode):
            return self.evaluate_decrement(node)
        # setNode
        elif isinstance(node, SetNode):
            return self.evaluate_set_node(node)

        # StructDeclarationNode
        elif isinstance(node, StructDeclarationNode):
            return self.evaluate_struct_declaration(node)

        # let z= Point{x:1,y:2};
        elif isinstance(node, StructAssignNode):
            return self.evaluate_struct_assign(node)
        
        # let z = bigJ.Book{title: "Fight", price: 99};
        elif isinstance(node, ModuleStructAssignNode):
            return self.evaluate_module_struct_assign(node)

        # StructAccessNode 访问结构体的属性  比如: p::x
        elif isinstance(node, StructAccessNode):
            return self.evaluate_struct_access(node)
        # StructAccessAssignNode  p::x = value
        elif isinstance(node, StructAccessAssignNode):
            return self.evaluate_struct_access_assign(node)
        # EnumDeclarationNode
        elif isinstance(node, EnumDeclarationNode):
            return self.evaluate_enum_declaration(node)

        # EnumAccessNode
        elif isinstance(node, EnumAccessNode):
            return self.evaluate_enum_access(node)
        
        # ModuleEnumAccessNode
        elif isinstance(node, ModuleEnumAccessNode):
            return self.evaluate_module_enum_access(node)
        
        # ModuleClassInstantiationNode
        elif isinstance(node, ModuleClassInstantiationNode):
            return self.evaluate_module_class_instantiation(node)

        # 宏定义处理
        elif isinstance(node, MacroDefinitionNode):
            return self.evaluate_macro_definition(node)
        
        elif isinstance(node, BlockMacroNode):
            return self.evaluate_block_macro(node)
        
        # do while
        elif isinstance(node, DoWhileNode):
            return self.evaluate_do_while(node)

        # ListGeneratorNode
        elif isinstance(node, ListGeneratorNode):
            return self.evaluate_list_generator(node)

        # abs
        elif isinstance(node, AbsNode):
            val = self.evaluate(node.expr)
            return abs(val)

        # SerialCall
        elif isinstance(node, SerialCall):
            return self.evaluate_serial_call(node)


        # += -=系列
        elif isinstance(node, PlusAssignNode):
            return self.evaluate_plus_assign(node)
        # -=
        elif isinstance(node, MinusAssignNode):
            return self.evaluate_minus_assign(node)

        # *=
        elif isinstance(node, MultiplyAssignNode):
            return self.evaluate_multiply_assign(node)

        # /=
        elif isinstance(node, DivideAssignNode):
            return self.evaluate_divide_assign(node)

        # d{"key"} = val
        elif isinstance(node, ObjectAssignNode):
            return self.evaluate_object_assign(node)

        # d[index] = val
        elif isinstance(node, ListAssignNode):
            return self.evaluate_list_assign(node)
        # 函数组合节点
        elif isinstance(node,FunctionCombinationNode):
            return self.evalFnCombineNode(node)
        # py{...} Python 代码执行
        elif isinstance(node, PyExecNode):
            return self.evaluate_py_exec(node)
        # pyFn{...} Python 函数值
        elif isinstance(node, PyFnNode):
            return self.evaluate_py_fn(node)
        else:
            raise TypeError(f"Unexpected node type: {type(node)}")

    def evaluate_py_exec(self, node: PyExecNode):
        """执行 py{...} 表达式，对接 Python 运行时。

        语义：
        - 先在本语言中对花括号内部的表达式求值，得到一个值 `code_val`
        - 将其转成字符串，视为一段 Python 源代码
        - 在一个长期存在的 Python 全局环境中执行这段代码
        - 返回这段代码最后一行表达式的值

        示例：
            let z = py{"import os\nos.path.exists('xxx')"};
        """
        # 1. 先在当前 DSL 环境里求值，允许 py{变量} / py{"..."} / py{"..." + other}
        code_val = self.evaluate(node.code_expr)
        if code_val is None:
            return None

        code_str = str(code_val)

        # 2. 清理首尾空行，方便包装成函数体
        lines = code_str.splitlines()
        # 去掉前后空行
        while lines and lines[0].strip() == "":
            lines.pop(0)
        while lines and lines[-1].strip() == "":
            lines.pop()

        if not lines:
            return None

        # 3. 自动给最后一行加上 return（如果用户没写）
        last_idx = len(lines) - 1
        if not lines[last_idx].lstrip().startswith("return"):
            lines[last_idx] = "return " + lines[last_idx]

        indented_body = "\n".join("    " + line for line in lines)

        func_src = "def __fight_py_block__():\n" + indented_body + "\n\n" \
                   "__fight_py_result__ = __fight_py_block__()\n"

        # 4. 每次执行前，把当前 DSL 环境暴露给 Python 代码，方便互操作
        self._py_globals["env"] = self.environment

        local_env = {}
        exec(func_src, self._py_globals, local_env)
        return local_env.get("__fight_py_result__")

    def evaluate_py_fn(self, node: PyFnNode):
        """创建一个 Python 函数值：pyFn{...}

        语义：
        - 先在本语言中对花括号内部的表达式求值，得到一个值 `code_val`
        - 将其转成字符串，视为一段 Python 函数体代码
        - 定义一个 Python 函数 `__fight_py_fn__(*args, **kwargs)`，并返回这个可调用对象

        在函数内部可以使用：
        - args / kwargs：来自 DSL 的实参（按值求过一次）
        - env：当前 DSL 环境（通过 self._py_globals['env'] 暴露）
        """
        code_val = self.evaluate(node.code_expr)
        if code_val is None:
            return None

        code_str = str(code_val)

        lines = code_str.splitlines()
        while lines and lines[0].strip() == "":
            lines.pop(0)
        while lines and lines[-1].strip() == "":
            lines.pop()

        if not lines:
            # 空函数，返回一个什么都不做的函数
            def _empty(*args, **kwargs):
                return None
            return _empty

        last_idx = len(lines) - 1
        if not lines[last_idx].lstrip().startswith("return"):
            lines[last_idx] = "return " + lines[last_idx]

        indented_body = "\n".join("    " + line for line in lines)

        func_src = "def __fight_py_fn__(*args, **kwargs):\n" + indented_body + "\n"

        # 暴露当前环境给 Python 侧
        self._py_globals["env"] = self.environment

        local_env = {}
        exec(func_src, self._py_globals, local_env)
        return local_env.get("__fight_py_fn__")

    def evaluate_super_call(self, node):
        """
        调用父类构造函数 super(args)
        支持多层继承的递归调用
        """
        parent_name = self.current_parent_class

        if not parent_name:
            raise RuntimeError(f"Class '{self.current_class}' has no parent class")

        parent_class_def = self._saved_objects.get(parent_name)
        if parent_class_def is None:
            raise NameError(f"Parent class '{parent_name}' not found")

        parent_init = parent_class_def.get("init")
        if not parent_init:
            return

        # 处理多个构造函数重载
        if isinstance(parent_init, list):
            arg_len = len(node.arguments)
            matching_init = None
            for init in parent_init:
                if len(init['args']) == arg_len:
                    matching_init = init
                    break
            if matching_init is None:
                raise ValueError(f"No matching parent constructor for {arg_len} arguments")
            parent_init = matching_init

        # 评估参数
        args_values = [self.evaluate(arg) for arg in node.arguments]

        # 绑定参数到当前环境
        init_args = parent_init['args']
        for arg_name, arg_value in zip(init_args, args_values):
            self.environment[arg_name] = arg_value

        # 🔥 关键修复：保存并更新父类链
        old_parent = self.current_parent_class
        self.current_parent_class = parent_class_def.get("parent_name", "")

        # 执行父类构造函数体（允许递归 super 调用）
        for statement in parent_init['body']:
            if isinstance(statement, AssignmentNode) and self._current_instance and statement.name in \
                    self._current_instance["fields"]:
                value = self.evaluate(statement.value)
                self.environment[statement.name] = value
                self._current_instance["fields"][statement.name] = value
            else:
                # 🔥 不再跳过 SuperCallNode，允许递归调用
                self.evaluate(statement)

        # 恢复父类指针
        self.current_parent_class = old_parent

    def evaluate_super_method_call(self, node: SuperMethodCallNode):
        """
        调用父类方法 super->method(args)
        """
        if self.current_class is None:
            raise RuntimeError("super->method() can only be used inside a class")

        # 获取父类名称
        parent_name = self.get_parent_class_name(self.current_class)
        if not parent_name:
            raise RuntimeError(f"Class '{self.current_class}' has no parent class")

        # 获取父类定义
        parent_class_def = self.environment["objects"].get(parent_name)
        if parent_class_def is None:
            raise NameError(f"Parent class '{parent_name}' not found")

        # 获取父类方法
        method_name = node.method_name
        if method_name not in parent_class_def["methods"]:
            raise NameError(f"Method '{method_name}' not found in parent class '{parent_name}'")

        method_candidate = parent_class_def["methods"][method_name]

        # 评估参数
        args_values = [self.evaluate(arg) for arg in node.arguments]
        
        # 处理方法重载：根据参数数量选择匹配的方法
        if isinstance(method_candidate, list):
            arg_count = len(args_values)
            method_dict = None
            for candidate in method_candidate:
                # 考虑默认参数：实际参数数量应该在 [必须参数数量, 总参数数量] 范围内
                total_params = len(candidate['args'])
                default_count = len(candidate.get('default_values', {}))
                required_params = total_params - default_count
                
                if required_params <= arg_count <= total_params:
                    method_dict = candidate
                    break
            if method_dict is None:
                raise ValueError(f"No matching method '{method_name}' found for {arg_count} arguments")
        else:
            method_dict = method_candidate

        # 保存旧环境
        old_env = self.environment.copy()
        
        # 处理默认参数：先绑定默认值
        default_values = method_dict.get('default_values', {})
        for param, default in default_values.items():
            self.environment[param] = self.evaluate(default)

        # 绑定实际传入的参数（会覆盖默认值）
        for arg_name, arg_value in zip(method_dict['args'], args_values):
            self.environment[arg_name] = arg_value

        # 执行方法体
        result = None
        for statement in method_dict['body']:
            result = self.evaluate(statement)
            if isinstance(statement, ReturnNode):
                break

        # 恢复环境
        self.environment = old_env

        return result

    def get_parent_class_name(self, class_name):
        """
        获取类的父类名称
        需要在类声明时保存这个信息
        """
        class_def = self.environment["objects"].get(class_name)
        if class_def and "parent_name" in class_def:
            return class_def["parent_name"]
        return None

    def check_is_from_module(self, access_name):
        """
            access_name一般是各种阶段的name属性，或者xx_name属性

            查看要访问的函数、变量是不是来自某个模块，
            主要是通过全局的self.exports进行检查
                self.exports的格式是：
                {
                    "module_name": [
                        "export_name1",
                        "export_name2",
                       ...
                    ]
                }
           这里的module_name是模块的名称，export_name是要导出的函数、变量的名称
        """
        print("self.exports: ", self.exports)

        for module_name in self.exports:
            # print("module_name: ", module_name, )
            if access_name in self.exports[module_name]:
                return module_name  # 返回模块名称，字符串类型
        return False

    #  模块导出
    def evaluate_exports_node(self,node:ExportsNode):
        # 此时self.environment是当前正在加载的module_env
        module_id = self.environment.get("__module_id__") or self.environment.get("__name__")
        if module_id:
            self.exports[module_id] = node.exports_list
        return None

    def evaluate_import_module(self, node: ImportModuleNode):
        """
        处理三种形式：
        1) import module
        2) import module as alias
        3) import { a, b, c } from module
        """

        # ===============================
        # 计算模块唯一ID与默认公开名称
        # ===============================
        if node.is_builtin:
            module_id = node.module_name  # 内置模块使用名称作为唯一ID
            default_public_name = node.module_name
        else:
            # 第三方模块使用绝对路径作为唯一ID，避免同名文件冲突
            module_id = os.path.abspath(node.module_name)
            default_public_name = Path(node.module_name).stem

        # ===============================
        # 确保模块已加载（只加载一次）
        # ===============================
        if module_id not in self.modules:
            self.modules[module_id] = self.load_module(module_id, node)
        module_env = self.modules[module_id]

        # ==================================================
        # CASE 3: import { a, b, c } from module
        # ==================================================
        if node.import_elements:
            allowed_exports = self.exports.get(module_id)
            for name in node.import_elements:
                # 从多个位置查找元素：直接在 module_env 或在 objects/structs/enums 中
                value = None
                if name in module_env:
                    value = module_env[name]
                elif name in module_env.get('objects', {}):
                    value = module_env['objects'][name]
                elif name in module_env.get('structs', {}):
                    value = module_env['structs'][name]
                elif name in module_env.get('enums', {}):
                    value = module_env['enums'][name]
                
                if value is None:
                    print("module_env",module_env)
                    raise ImportError(f"{name} not found in module {default_public_name}")

                # 严格检查是否导出
                if not allowed_exports or name not in allowed_exports:
                    raise ImportError(
                        f"Variable '{name}' is not exported by module '{default_public_name}'. (Did you forget to add it to 'exports'?)")

                # 核心：给导入对象绑定其模块环境
                if isinstance(value, dict) and "body" in value:
                    value["__module_env__"] = module_env
                self.environment[name] = value
            return  # 必须 return，避免继续执行下面逻辑

        # ==================================================
        # CASE 1 / CASE 2: import module / import module as alias
        # ==================================================
        alias = node.alias if node.alias else default_public_name
        # 整模块导入时，在环境中暴露模块对象，并记录别名映射
        self.environment[alias] = module_env
        self.module_aliases[alias] = module_env

    def load_module(self, module_id: str, node):
        """
        加载模块并返回 module_env
        - 不污染 global_env
        - 不执行在 global_env
        - 支持循环导入检测
        module_id: 模块唯一ID（内置模块名或第三方模块绝对路径）
        """
        # ========= 循环导入检测 =========
        if module_id in self._loading_stack:
            cycle = " -> ".join(self._loading_stack + [module_id])
            raise ImportError(f"循环导入检测到: {cycle}")

        self._loading_stack.append(module_id)

        # ========= 确定模块文件路径 =========
        if node.is_builtin:
            path = self.find_builtin_module_file(module_id)
        else:
            path = self.find_third_party_module(node)

        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Module file not found: {module_id}")

        # ========= 读取模块代码 =========
        with open(path, "r", encoding="utf-8") as f:
            module_code = f.read()

        # ========= 解析 AST =========
        tokenizer = Tokenizer(module_code)
        tokens = tokenizer.tokenize()
        parser = Parser(tokens)
        ast_nodes = parser.parse()

        # ========= 创建 module_env（关键隔离点） =========
        module_env = {
            "_is_module_env": True,
            "__module_id__": module_id,
            "__name__": module_id,
            "__file__": path,
            "arg_to_instance": {},
            "instances": {},
            "constants": [],
            "objects": {},
            "interfaces": {},
            "structs": {},
            "enums": {},
        }
        # 注入内置模块
        for builtin_name, builtin_env in self.builtin_modules.items():
            module_env[builtin_name] = builtin_env
        # ========= 在 module_env 中执行模块 =========
        old_env = self.environment
        self.environment = module_env

        for ast_node in ast_nodes:
            self.evaluate(ast_node)

        for value in module_env.values():
            if isinstance(value, dict) and "body" in value:
                value["__module_env__"] = module_env

        # ========= 恢复主环境 =========
        self.environment = old_env
        self._loading_stack.pop()

        return module_env

    def find_third_party_module(self,node:ImportModuleNode):
        if os.path.exists(node.module_name):
            return node.module_name
        raise  FileNotFoundError(f"Third-party module '{node.module_name}' not found")
    def find_builtin_module_file(self, module_name:str):
        """查找模块文件"""
        extensions = ['.fight']
        # 内置模块目录跟随解释器文件定位，避免硬编码某台开发机的绝对路径
        search_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "builtin")
        ]
        for path in search_paths:
            for ext in extensions:
                if module_name.endswith("fight"):
                    full_path = os.path.join(path, module_name)
                else:
                    full_path = os.path.join(path, module_name + ext)
                if os.path.exists(full_path):
                    return full_path
        raise FileNotFoundError(f"Builtin Module '{module_name}' not found")

    def create_closure(self, func_dict, module_env, func_name):
        def closure(*args, **kwargs):
            # 保存当前环境
            old_env = self.environment
            # 创建一个新的环境，包含模块环境和当前环境的某些关键部分
            new_env = module_env.copy()
            # 动态获取当前环境的 objects、instances 等，而不是创建闭包时的
            new_env.update({
                'arg_to_instance': old_env.get('arg_to_instance', {}),
                'instances': old_env.get('instances', {}),
                'objects': old_env.get('objects', {}),  # 动态获取调用时的 objects
                'interfaces': old_env.get('interfaces', {}),
                'structs': old_env.get('structs', {}),
                'enums': old_env.get('enums', {})
            })
            self.environment = new_env

            # 创建一个模拟的 FunctionCallNode
            mock_node = type('MockFunctionCallNode', (), {
                'name': func_name,  # 使用传入的函数名
                'args': args,
                'named_arg_values': kwargs
            })()

            # 使用现有的 evaluate_function_call 方法
            result = self.evaluate_function_call(mock_node)

            # 恢复环境
            self.environment = old_env
            return result

        # 创建新的函数字典，包含闭包
        new_func_dict = func_dict.copy()
        new_func_dict['closure'] = closure
        return new_func_dict

    def evaluate_function_call(self, node):
        name = node.name

        # 检查是否是宏调用
        if 'macros' in self.environment and name in self.environment['macros']:
            macro_info = self.environment['macros'][name]
            # 有参数的宏
            # if len(macro_info['params']) > 0:
            #     # 获取参数值
            #     args = [self.evaluate(arg) for arg in node.args]
            #     return self.expand_macro(name, args)
            # else:
            #     # 无参数的宏，按变量处理
            #     return self.expand_macro(name)
            if len(macro_info['params']) > 0:
                if macro_info['type'] == 'block':
                    # 代码块宏：传递 AST 节点（不求值）
                    return self.expand_macro(name, node.args)
                else:
                    # 表达式宏：正常求值
                    args = [self.evaluate(arg) for arg in node.args]
                    return self.expand_macro(name, args)
            else:
                return self.expand_macro(name)

        # 检查一个实例对象是不是另一个类的实例（已废弃，请使用 IsInstanceOf）
        if node.name == "IsInstance":
            args = [self.evaluate(arg) for arg in node.args]
            instance = args[0]  # instance被解析为一个ditc对象，包含fiels和methods等
            classname = args[1]
            if instance["parent_name"] == classname:
                return True
            else:
                return False
        
        # IsInstanceOf(instance, className) - 增强的类型检查，支持继承链
        if node.name == "IsInstanceOf":
            args = [self.evaluate(arg) for arg in node.args]
            if len(args) != 2:
                raise ValueError(f"IsInstanceOf expects 2 arguments but got {len(args)}")
            
            instance = args[0]
            target_class_name = args[1]
            
            # 检查是否是类实例
            if not isinstance(instance, dict) or "parent_name" not in instance:
                return False
            
            # 检查实例的类型及其所有父类
            current_class_name = instance["parent_name"]
            while current_class_name:
                if current_class_name == target_class_name:
                    return True
                # 查找父类
                if current_class_name in self.environment.get("objects", {}):
                    class_def = self.environment["objects"][current_class_name]
                    current_class_name = class_def.get("parent_name", "")
                else:
                    break
            return False
        
        # GetClassType(instance) - 获取实例的当前视图类型
        if node.name == "GetClassType":
            args = [self.evaluate(arg) for arg in node.args]
            if len(args) != 1:
                raise ValueError(f"GetClassType expects 1 argument but got {len(args)}")
            
            instance = args[0]
            if isinstance(instance, dict) and "parent_name" in instance:
                return instance["parent_name"]  # 返回当前视图的类型
            else:
                raise TypeError("Argument must be a class instance")
        
        # GetRealType(instance) - 获取实例的真实类型（未转型前的类型）
        if node.name == "GetRealType":
            args = [self.evaluate(arg) for arg in node.args]
            if len(args) != 1:
                raise ValueError(f"GetRealType expects 1 argument but got {len(args)}")
            
            instance = args[0]
            if isinstance(instance, dict) and "parent_name" in instance:
                # 如果实例被转型过，返回原始类型，否则返回当前类型
                return instance.get("__original_type__", instance["parent_name"])
            else:
                raise TypeError("Argument must be a class instance")
        
        # CastTo(instance, className) - 显式类型转换
        if node.name == "CastTo":
            args = [self.evaluate(arg) for arg in node.args]
            if len(args) != 2:
                raise ValueError(f"CastTo expects 2 arguments but got {len(args)}")
            
            instance = args[0]
            target_class_name = args[1]
            
            # 检查是否是类实例
            if not isinstance(instance, dict) or "parent_name" not in instance:
                raise TypeError("First argument must be a class instance")
            
            # 构建继承链
            def build_inheritance_chain(class_name):
                """构建从当前类到根类的继承链"""
                chain = []
                current = class_name
                while current:
                    chain.append(current)
                    if current in self.environment.get("objects", {}):
                        class_def = self.environment["objects"][current]
                        current = class_def.get("parent_name", "")
                    else:
                        break
                return chain
            
            # 获取实例的真实类型（如果被转型过，使用原始类型）
            real_type = instance.get("__original_type__", instance["parent_name"])
            # 获取当前视图的类型
            view_type = instance["parent_name"]
            
            # 基于真实类型构建继承链
            real_chain = build_inheritance_chain(real_type)
            
            # 检查目标类型是否在继承链中
            if target_class_name not in real_chain:
                raise TypeError(f"Cannot cast {real_type} to {target_class_name}: not in inheritance hierarchy")
            
            # 获取目标类的定义
            if target_class_name not in self.environment.get("objects", {}):
                raise NameError(f"Class '{target_class_name}' not found")
            
            target_class_def = self.environment["objects"][target_class_name]
            
            # 判断转换方向（基于真实类型的继承链）
            real_type_index = real_chain.index(real_type)
            target_index = real_chain.index(target_class_name)
            # 获取当前视图在继承链中的位置
            view_index = real_chain.index(view_type) if view_type in real_chain else real_type_index
            
            if target_index > view_index:
                # 向上转型（子类 -> 父类）：限制访问
                # 获取原始实例（如果已经是转型后的视图，获取其原始实例）
                original_instance = instance.get("__original_instance__", instance)
                
                # 创建一个新的视图，只包含父类定义的成员
                casted_instance = {
                    "fields": {},
                    "methods": {},
                    "parent_name": target_class_name,  # 当前视图类型
                    "fields_annotations": {},
                    "__original_instance__": original_instance,  # 保存原始实例的引用
                    "__is_casted__": True,
                    "__original_type__": real_type  # 保存真实类型
                }
                
                # 只复制父类定义的字段（从原始实例中获取）
                for field_name in target_class_def.get("fields", {}):
                    if field_name in original_instance["fields"]:
                        casted_instance["fields"][field_name] = original_instance["fields"][field_name]
                
                # 只复制父类定义的方法（从原始实例中获取）
                for method_name in target_class_def.get("methods", {}):
                    if method_name in original_instance["methods"]:
                        casted_instance["methods"][method_name] = original_instance["methods"][method_name]
                
                return casted_instance
            
            elif target_index < view_index:
                # 向下转型（父类 -> 子类）：运行时检查
                # 检查目标类型是否在真实类型的继承链中（已在前面检查过）
                
                # 如果是被向上转型过的实例，需要恢复或创建部分视图
                if instance.get("__is_casted__") and "__original_instance__" in instance:
                    original = instance["__original_instance__"]
                    
                    # 如果目标类型就是原始类型，直接返回原始实例
                    if target_class_name == real_type:
                        return original
                    
                    # 如果目标类型是原始类型和当前视图之间的中间类型
                    # 创建一个新的视图，限制访问到目标类型
                    if target_class_name not in self.environment.get("objects", {}):
                        raise NameError(f"Class '{target_class_name}' not found")
                    
                    target_def = self.environment["objects"][target_class_name]
                    intermediate_view = {
                        "fields": {},
                        "methods": {},
                        "parent_name": target_class_name,
                        "fields_annotations": {},
                        "__original_instance__": original,
                        "__is_casted__": True,
                        "__original_type__": real_type
                    }
                    
                    # 复制目标类定义的字段和方法
                    for field_name in target_def.get("fields", {}):
                        if field_name in original["fields"]:
                            intermediate_view["fields"][field_name] = original["fields"][field_name]
                    
                    for method_name in target_def.get("methods", {}):
                        if method_name in original["methods"]:
                            intermediate_view["methods"][method_name] = original["methods"][method_name]
                    
                    return intermediate_view
                else:
                    # 实例本身就是目标类型或其子类，直接返回
                    return instance
            else:
                # 转换到同一类型，直接返回
                return instance

        # ImplInterface(类名：string, 接口名:string)
        if node.name == "HasImplInterface":
            args = [self.evaluate(arg) for arg in node.args]

            classname = args[0]
            interface_name = args[1]
            print("classname: ", classname)
            print("interface_name: ", interface_name)
            print("\nobjects: ", self.environment["objects"])

            # 找到类
            class_find = self.environment["objects"][classname]
            print("class_find: ", class_find)

            # 找到接口
            interface_def = self.environment["interfaces"][interface_name]
            print("interface_def: ", interface_def)

            # 遍历接口的方法，判断类中是否有实现
            for method_name in interface_def["methods"]:
                if method_name not in class_find["methods"]:
                    return False
            return True

        if node.name == 'print':
            args = []
            for arg in node.args:
                evaluated_arg = self.evaluate(arg)
                # 检查是否为类实例（字典类型且包含 fields 和 methods）
                if isinstance(evaluated_arg, dict) and "fields" in evaluated_arg and "methods" in evaluated_arg:
                    # 这是一个类实例，尝试调用 ToString 方法
                    if "ToString" in evaluated_arg["methods"]:
                        # 有自定义 ToString，调用它
                        old_env = self.environment
                        old_current_object = self.current_object

                        # 🔥 关键修复：创建临时实例名
                        temp_instance_name = f"__temp_instance_{id(evaluated_arg)}__"
                        self.environment["instances"][temp_instance_name] = evaluated_arg

                        # 创建方法调用环境
                        method_dict = evaluated_arg["methods"]["ToString"]
                        new_env = {
                            "constants": [],
                            "objects": old_env.get("objects", {}),
                            "instances": old_env.get("instances", {}),
                        }

                        # 添加实例的字段到环境
                        for field_name, field_value in evaluated_arg["fields"].items():
                            new_env[field_name] = field_value

                        self.environment = new_env
                        # 🔥 修复：设置为字符串名称而不是字典
                        self.current_object = temp_instance_name

                        # 执行 ToString 方法体
                        result = None
                        for statement in method_dict['body']:
                            result = self.evaluate(statement)
                            if isinstance(statement, ReturnNode):
                                break

                        # 🔥 清理临时实例
                        del self.environment["instances"][temp_instance_name]

                        # 恢复环境
                        self.environment = old_env
                        self.current_object = old_current_object

                        args.append(result)
                    else:
                        # 没有 ToString，使用默认实现
                        class_name = evaluated_arg.get('parent_name', 'Object')

                        # 只显示 public 字段（首字母大写）
                        public_fields = {k: v for k, v in evaluated_arg["fields"].items() if k[0].isupper()}

                        if public_fields:
                            fields_str = ", ".join(f"{k}={v}" for k, v in public_fields.items())
                            default_str = f"{class_name}({fields_str})"
                        else:
                            # 没有 public 字段，只显示类名
                            default_str = f"{class_name}()"

                        args.append(default_str)
                else:
                    args.append(evaluated_arg)

            print(*args, end="")
            return None

        # 简单示例,仅支持打印函数
        if node.name == 'println':
            args = []
            for arg in node.args:
                evaluated_arg = self.evaluate(arg)
                # 检查是否为类实例（字典类型且包含 fields 和 methods）
                if isinstance(evaluated_arg, dict) and "fields" in evaluated_arg and "methods" in evaluated_arg:
                    # 这是一个类实例，尝试调用 ToString 方法
                    if "ToString" in evaluated_arg["methods"]:
                        # 有自定义 ToString，调用它
                        old_env = self.environment
                        old_current_object = self.current_object

                        # 🔥 关键修复：创建临时实例名
                        temp_instance_name = f"__temp_instance_{id(evaluated_arg)}__"
                        self.environment["instances"][temp_instance_name] = evaluated_arg

                        # 创建方法调用环境
                        method_dict = evaluated_arg["methods"]["ToString"]
                        new_env = {
                            "constants": [],
                            "objects": old_env.get("objects", {}),
                            "instances": old_env.get("instances", {}),
                        }

                        # 添加实例的字段到环境
                        for field_name, field_value in evaluated_arg["fields"].items():
                            new_env[field_name] = field_value

                        self.environment = new_env
                        # 🔥 修复：设置为字符串名称而不是字典
                        self.current_object = temp_instance_name

                        # 执行 ToString 方法体
                        result = None
                        for statement in method_dict['body']:
                            result = self.evaluate(statement)
                            if isinstance(statement, ReturnNode):
                                break

                        # 🔥 清理临时实例
                        del self.environment["instances"][temp_instance_name]

                        # 恢复环境
                        self.environment = old_env
                        self.current_object = old_current_object

                        args.append(result)
                    else:
                        # 没有 ToString，使用默认实现
                        class_name = evaluated_arg.get('parent_name', 'Object')

                        # 只显示 public 字段（首字母大写）
                        public_fields = {k: v for k, v in evaluated_arg["fields"].items() if k[0].isupper()}

                        if public_fields:
                            fields_str = ", ".join(f"{k}={v}" for k, v in public_fields.items())
                            default_str = f"{class_name}({fields_str})"
                        else:
                            # 没有 public 字段，只显示类名
                            default_str = f"{class_name}()"

                        args.append(default_str)
                else:
                    args.append(evaluated_arg)

            print(*args)
            return None
        # 输入函数
        if node.name == 'input':
            args = [self.evaluate(arg) for arg in node.args]
            prompt_msg = args[0] if len(args) > 0 else ""
            return input(prompt_msg)

        # ============ 类型转换与类型判断 ============
        if node.name == 'getType':
            # getType(obj) -> "string" / "number" / "list" / "object" ...
            args = [self.evaluate(arg) for arg in node.args]
            return CommonUtils.getType(args[0])

        if node.name == 'toInt':
            # toInt("42") -> 42
            args = [self.evaluate(arg) for arg in node.args]
            return CommonUtils.toInt(args[0])

        if node.name == 'toNumber':
            # toNumber("3.14") -> 3.14，能转数字就转，转不了保持原值
            args = [self.evaluate(arg) for arg in node.args]
            return CommonUtils.toNumber(args[0])

        if node.name == 'toFloat':
            args = [self.evaluate(arg) for arg in node.args]
            return CommonUtils.toFloat(args[0])

        if node.name == 'toStr':
            args = [self.evaluate(arg) for arg in node.args]
            return CommonUtils.toString(args[0])

        if node.name == 'toBool':
            args = [self.evaluate(arg) for arg in node.args]
            return CommonUtils.toBool(args[0])

        # ============ 对象的两个方法================
        if node.name == "ObjectKeys":
            # objectKeys(obj)
            if len(node.args) != 1:
                raise ValueError(f"Function '{node.name}' expects 1 argument but got {len(node.args)}.")
            args: dict = self.evaluate(node.args[0])
            return list(args.keys())

        if node.name == "ObjectValues":
            # objectValues(obj)
            if len(node.args) != 1:
                raise ValueError(f"Function '{node.name}' expects 1 argument but got {len(node.args)}.")
            args: dict = self.evaluate(node.args[0])
            return list(args.values())

        # =============Set类型======================
        if node.name == "SetLength":
            myset = self.evaluate(node.args[0])
            return len(myset)
        if node.name == "SetAdd":
            myset = self.evaluate(node.args[0])
            element = self.evaluate(node.args[1])
            try:
                myset.add(element)
                return True
            except:
                return False
        if node.name == "SetRemove":
            myset = self.evaluate(node.args[0])
            element = self.evaluate(node.args[1])
            try:
                myset.remove(element)
                return True
            except:
                return False

        if node.name == "SetContains":
            myset = self.evaluate(node.args[0])
            element = self.evaluate(node.args[1])
            return element in myset

        if node.name == "SetIsSubset":
            myset1 = self.evaluate(node.args[0])
            myset2 = self.evaluate(node.args[1])
            return myset1.issubset(myset2)

        if node.name == "SetIsSuperset":
            myset1 = self.evaluate(node.args[0])
            myset2 = self.evaluate(node.args[1])
            return myset1.issuperset(myset2)

        if node.name == "SetClear":
            myset = self.evaluate(node.args[0])
            myset.clear()
            return True

        if node.name == "SetUnion":
            myset1 = self.evaluate(node.args[0])
            myset2 = self.evaluate(node.args[1])
            return myset1.union(myset2)
        if node.name == "SetIntersection":
            myset1 = self.evaluate(node.args[0])
            myset2 = self.evaluate(node.args[1])
            return myset1.intersection(myset2)

        if node.name == "SetDiff":
            myset1 = self.evaluate(node.args[0])
            myset2 = self.evaluate(node.args[1])
            return myset1.difference(myset2)

        if node.name == "GetParamsByName":
            func_name = self.evaluate(node.args[0])
            return self.environment[func_name]["args"]

        # ==================================================
        # 通过方法名称获取默认参数
        if node.name == "GetDefaultValues":
            func_name = self.evaluate(node.args[0])
            defaults = self.environment[func_name]["defaults"]
            # defaults:  {'x': NumberNode(value=1)}
            # print("defaults: ", defaults)
            for key in defaults:
                defaults[key] = self.evaluate(defaults[key])
            return defaults

        # 通过方法名称调用函数
        # InvokeFunc("方法名称", {})
        if node.name == "InvokeFunc":
            name_and_params = [self.evaluate(arg) for arg in node.args]
            # print("name_and_params: ", name_and_params)
            # 比如: name_and_params:  ['cb', {'x': 5}]
            return self.invokefunc_server(self.environment[name_and_params[0]], name_and_params[1])

        # 返回类名的字段
        if node.name == "GetFieldsByClassName":
            if len(node.args) > 1:
                raise ValueError(f"Function '{node.name}' expects 1 argument but got {len(node.args)}.")
            # 传入的参数就是类名
            classname = self.evaluate(node.args[0])
            # 从环境中获取fields
            if classname not in self.environment.get("objects", {}):
                raise NameError(f"Class '{classname}' not found")
            fields = self.environment["objects"][classname]["fields"]
            return fields

        # GetInstanceFields
        if node.name == "GetInstanceFields":
            # 支持两种用法：1. 直接传入实例对象 2. 传入变量名
            arg = self.evaluate(node.args[0])
            if isinstance(arg, dict) and "fields" in arg and "methods" in arg:
                # 直接传入了实例对象
                return arg['fields']
            else:
                # 传入的是变量名（字符串）
                instance_name = f"{node.args[0].value}"
                instance_dict = self.environment["instances"][instance_name]
                return instance_dict['fields']

        # 获取实例的方法的相关信息
        if node.name == "GetInstanceMethods":
            # 支持两种用法：1. 直接传入实例对象 2. 传入变量名
            arg = self.evaluate(node.args[0])
            if isinstance(arg, dict) and "fields" in arg and "methods" in arg:
                # 直接传入了实例对象
                instance_methods_dict = arg["methods"]
            else:
                # 传入的是变量名
                instance_name = f"{node.args[0].value}"
                instance_methods_dict = self.environment["instances"][instance_name]["methods"]

            result = []
            for method_name in instance_methods_dict:
                single_method_dict = instance_methods_dict[method_name].copy()  # 使用copy避免修改原始数据
                # single method dict: {'args': ['x', 'y'], 'body': []}
                if 'body' in single_method_dict:
                    del single_method_dict['body']
                single_method_dict['method_name'] = method_name
                result.append(single_method_dict)
                for arg_name in single_method_dict.get('default_values', {}):
                    single_method_dict['default_values'][arg_name] = self.evaluate(single_method_dict['default_values'][arg_name])
            return result

        # 设置实例的字段值 SetInstanceField(instance_name,{field:value,field2:value2})
        if node.name == "SetInstanceField":
            # 支持两种用法：1. 直接传入实例对象 2. 传入变量名
            first_arg = self.evaluate(node.args[0])
            field_and_value = self.evaluate(node.args[1])
            
            if isinstance(first_arg, dict) and "fields" in first_arg and "methods" in first_arg:
                # 直接传入了实例对象，直接修改
                for field_name, field_value in field_and_value.items():
                    if field_name in first_arg["fields"]:
                        first_arg["fields"][field_name] = field_value
                    else:
                        raise NameError(f"Field '{field_name}' not defined in instance")
            else:
                # 传入的是变量名
                instance_name = f"{node.args[0].value}"
                for field_name, field_value in field_and_value.items():
                    if field_name in self.environment["instances"][instance_name]["fields"]:
                        self.environment["instances"][instance_name]["fields"][field_name] = field_value
                    else:
                        raise NameError(f"Field '{field_name}' not defined in instance '{instance_name}'")
            return True

        # 调用实例的方法 InvokeInstanceMethod(instance_name, "method_name", args_dict)
        # 似乎仅仅支持命名参数
        if node.name == "InvokeInstanceMethod":
            # 支持两种用法：1. 直接传入实例对象 2. 传入变量名
            first_arg = self.evaluate(node.args[0])
            method_name = self.evaluate(node.args[1])
            args = self.evaluate(node.args[2])
            
            if isinstance(first_arg, dict) and "fields" in first_arg and "methods" in first_arg:
                # 直接传入了实例对象
                method_dict = first_arg["methods"][method_name]
            else:
                # 传入的是变量名
                instance_name = f"{node.args[0].value}"
                method_dict = self.environment["instances"][instance_name]["methods"][method_name]
            
            return self.invokefunc_server(method_dict, args)

        # partialUpdate
        # args: [VariableNode(value=p), ObjectNode(properties={'x': NumberNode(value=4)})]
        if node.name == "partialUpdate":
            # 返回 False 或者 True 表示是否成功
            instance_name = f"{node.args[0].value}"
            # 比如  {'x': 4}
            if instance_name not in self.environment:
                return False
            update_dict = self.evaluate(node.args[1])
            for modification_key_name in update_dict:
                self.environment[instance_name]["value"][modification_key_name] = update_dict[modification_key_name]
            return True

        # GetMethodAnnotations
        if node.name == "GetMethodAnnotations":
            # GetMethodAnnotations(instance_name: 实例, method_name:str)
            # 支持两种用法：1. 直接传入实例对象 2. 传入变量名
            first_arg = self.evaluate(node.args[0])
            method_name = self.evaluate(node.args[1])
            
            try:
                if isinstance(first_arg, dict) and "fields" in first_arg and "methods" in first_arg:
                    # 直接传入了实例对象
                    annotations = first_arg["methods"][method_name].get("annotations", {})
                else:
                    # 传入的是变量名
                    instance_name = f"{node.args[0].value}"
                    annotations = self.environment["instances"][instance_name]["methods"][method_name].get("annotations", {})
                
                result = {}
                for key in annotations:
                    # 解析出值
                    result[key] = self.evaluate(annotations[key])
                return result
            except:
                return {}

        # GetFieldAnnotations
        if node.name == "GetFieldAnnotations":
            # GetFieldAnnotations(instance_name: 实例, field_name:str)
            # 支持两种用法：1. 直接传入实例对象 2. 传入变量名
            first_arg = self.evaluate(node.args[0])
            field_name = self.evaluate(node.args[1])
            
            try:
                if isinstance(first_arg, dict) and "fields" in first_arg and "methods" in first_arg:
                    # 直接传入了实例对象
                    annotations = first_arg.get("fields_annotations", {})
                else:
                    # 传入的是变量名
                    instance_name = f"{node.args[0].value}"
                    annotations = self.environment["instances"][instance_name].get("fields_annotations", {})
                
                if field_name in annotations:
                    return {field_name: annotations[field_name]}
                return {}
            except:
                return {}

        # Char2Asc
        if node.name == "Char2Asc":
            return ord(self.evaluate(node.args[0]))

        # Asc2Char
        if node.name == "Asc2Char":
            return chr(self.evaluate(node.args[0]))

        # =================================================================
        # 优先级检查：用户定义的函数/变量优先于内建工具类
        # =================================================================
        # ===== 类内部方法解析：在类方法/静态方法中直接调用同一类的方法（如 PrintType()） =====
        if self.current_class is not None:
            class_def = self.environment.get("objects", {}).get(self.current_class)
            if class_def is not None and name in class_def.get("methods", {}):
                # 等价于  ClassName->MethodName(args)
                temp_method_call = MethodCallNode(self.current_class, name, node.args)
                old_internal = self._internal_method_call
                self._internal_method_call = True
                try:
                    return self.evaluate_method_call(temp_method_call)
                finally:
                    self._internal_method_call = old_internal

        if name in self.environment:
            func_val = self.environment[name]

            # 如果是 pyFn 创建的 Python 可调用对象
            if callable(func_val) and not isinstance(func_val, dict):
                args = [self.evaluate(arg) for arg in node.args]
                # 调用前同步当前 DSL 环境
                self._py_globals["env"] = self.environment
                # DEBUG: 打印调用信息
                print(f"[DEBUG] 调用 pyFn: {name}")
                print(f"[DEBUG] 参数数量: {len(args)}")
                print(f"[DEBUG] 参数内容: {args}")
                result = func_val(*args)
                print(f"[DEBUG] 返回值: {result}")
                return result

            func_dict = func_val
            
            # 检查是否是类定义（从模块导入的类）
            if isinstance(func_dict, dict) and 'fields' in func_dict and 'methods' in func_dict and 'init' in func_dict:
                # 这是一个类定义，需要实例化
                # 生成一个临时的对象名
                temp_obj_name = f"__temp_obj_{id(node)}__"
                
                # 创建实例对象
                return_instance = {
                    "fields": {},
                    "methods": {},
                    "init": {},
                    "parent_name": name,
                    "fields_annotations": {},
                }
                
                # 复制类定义的内容到实例
                for field_name in func_dict['fields']:
                    return_instance["fields"][field_name] = func_dict['fields'][field_name]
                    
                for method_name in func_dict['methods']:
                    return_instance["methods"][method_name] = func_dict['methods'][method_name]
                
                # 处理构造函数
                init_def = func_dict['init']
                arg_len = len(node.args)
                matching_init = None
                
                if isinstance(init_def, list):
                    for init in init_def:
                        if len(init['args']) == arg_len:
                            matching_init = init
                            break
                else:
                    matching_init = init_def
                
                # 如果没有找到匹配的构造函数，检查是否允许无参构造
                if matching_init is None:
                    # 只有当字段数量为0时，才允许无参构造，否则报错
                    if len(func_dict['fields']) == 0:
                        # 创建一个默认的空构造函数
                        matching_init = {'args': [], 'body': [], 'default_values': {}}
                    else:
                        raise ValueError(f"No matching constructor found for class {name} with {arg_len} arguments")
                
                return_instance["init"] = matching_init
                
                # 创建新环境执行构造函数
                old_env = self.environment
                new_env = {
                    "constants": [],
                    "objects": self.environment.get("objects", {}),
                }
                
                # 将类的字段添加到新环境中
                for field_name, field_value in return_instance["fields"].items():
                    new_env[field_name] = field_value
                
                self.environment = new_env
                
                # 绑定构造函数参数
                init_args = matching_init['args']
                for i, arg_name in enumerate(init_args):
                    if i < len(node.args):
                        self.environment = old_env
                        arg_value = self.evaluate(node.args[i])
                        self.environment = new_env
                        self.environment[arg_name] = arg_value
                
                # 执行构造函数体
                from interpreter.Nodes import AssignmentNode
                init_body = matching_init['body']
                for statement in init_body:
                    if isinstance(statement, AssignmentNode) and statement.name in return_instance["fields"]:
                        value = self.evaluate(statement.value)
                        self.environment[statement.name] = value
                        return_instance["fields"][statement.name] = value
                    else:
                        self.evaluate(statement)
                
                # 将更新后的字段值复制回实例
                for field_name in return_instance["fields"]:
                    if field_name in self.environment:
                        return_instance["fields"][field_name] = self.environment[field_name]
                
                # 恢复环境
                self.environment = old_env
                
                return return_instance

            # 如果是模块函数（被 import {}）
            if isinstance(func_dict, dict) and "__module_env__" in func_dict:
                return self.call_function(
                    func_dict,
                    node.args,
                    func_dict["__module_env__"],
                    node.named_arg_values,
                )

            # 否则，本地函数
            closure_env = func_dict.get("__closure_env__", self.environment)
            return self.call_function(func_dict, node.args, closure_env, node.named_arg_values)

        # =================================================================
        # 内建工具类检查
        # =================================================================
        
        # ===============借用python的字符串方法===================================
        # name就是method_name
        # dir(StringUtils) 得到StringUtils的所有方法，包括自定义的，dir返回列表
        if node.name in dir(StringUtils):
            # 获取方法
            method = getattr(StringUtils, node.name)
            # 评估参数
            args = [self.evaluate(arg) for arg in node.args]
            # 调用方法并返回结果
            return method(*args)
        # ============================FileSystemUtils==============================
        if node.name in dir(FileSystemUtils):
            # 获取方法
            method = getattr(FileSystemUtils, node.name)
            # 评估参数
            args = [self.evaluate(arg) for arg in node.args]
            # 调用方法并返回结果
            return method(*args)
        # =============================FileSystemUtils===============================

        # =======================RandomUtils===================================================
        if node.name in dir(RandomUtils):
            # 获取方法
            method = getattr(RandomUtils, node.name)
            # 评估参数
            args = [self.evaluate(arg) for arg in node.args]
            # 调用方法并返回结果
            return method(*args)

        # =======================SystemUtils===================================================
        if node.name in dir(SystemUtils):
            # 获取方法
            method = getattr(SystemUtils, node.name)
            # 评估参数
            args = [self.evaluate(arg) for arg in node.args]
            # 调用方法并返回结果
            return method(*args)

        # ===================借用python的列表方法======================================
        if node.name in dir(ListUtils):
            # 获取方法
            method = getattr(ListUtils, node.name)
            # 评估参数
            args = [self.evaluate(arg) for arg in node.args]
            # 调用方法并返回结果
            return method(*args)

        # ====================借用python的字典方法=============================================================
        if node.name in dir(DictUtils):
            method = getattr(DictUtils, node.name)
            args = [self.evaluate(arg) for arg in node.args]
            return method(*args)

        # ====================借用python的数学模块=============================================================
        if node.name in dir(MathUtils):
            method = getattr(MathUtils, node.name)
            args = [self.evaluate(arg) for arg in node.args]
            return method(*args)

        # =============================借用其他 common的方法。比如type=========
        if node.name in dir(CommonUtils):
            method = getattr(CommonUtils, node.name)
            args = [self.evaluate(arg) for arg in node.args]
            return method(*args)

        # =============================借用python的time模块===================================
        if node.name in dir(TimeUtils):
            method = getattr(TimeUtils, node.name)
            args = [self.evaluate(arg) for arg in node.args]
            return method(*args)

        # 文件操作（FileUtils）
        if node.name in dir(FileUtils):
            method = getattr(FileUtils, node.name)
            args = [self.evaluate(arg) for arg in node.args]
            result =  method(*args)
            return result

        # uuid
        if node.name in dir(UUIDUtils):
            method = getattr(UUIDUtils, node.name)
            args = [self.evaluate(arg) for arg in node.args]
            return method(*args)

        # JsonUtils
        if node.name in dir(JsonUtils):
            method = getattr(JsonUtils, node.name)
            args = [self.evaluate(arg) for arg in node.args]
            return method(*args)

        # 网络操作（NetworkUtils）
        if node.name in dir(NetworkUtils):
            method = getattr(NetworkUtils, node.name)
            args = [self.evaluate(arg) for arg in node.args]
            return method(*args)

        if node.name == "GetFnAnnotations":
            # 获取方法的注释
            annotations = {}
            func_description = self.evaluate(node.args[0])
            if "annotations" in func_description:
                annotations = func_description["annotations"]
            # print("func_description: ",annotations)
            return annotations

        # ===== 模块函数 =====
        if "." in name:
            mod, fn = name.split(".", 1)
            module_env = self.module_aliases.get(mod)
            if not module_env:
                raise NameError(f"{name} not found")
            module_id = module_env.get("__module_id__") or module_env.get("__name__")
            allowed_exports = self.exports.get(module_id)
            # 模块函数必须在 exports 中显式导出
            if not allowed_exports or fn not in allowed_exports:
                raise ImportError(
                    f"Function '{fn}' is not exported by module '{mod}'. (Did you forget to add it to 'exports'?)")
            if fn not in module_env:
                raise NameError(f"{name} not found")

            target = module_env[fn]

            # 如果是 pyFn 创建的 Python 可调用对象
            if callable(target) and not isinstance(target, dict):
                call_args = [self.evaluate(arg) for arg in node.args]

                # 构造与 DSL 函数类似的调用环境：内建 -> 当前环境 -> 模块环境
                call_env = {}
                call_env.update(self._builtin_env)
                call_env.update(self.environment)
                call_env.update(module_env)

                # 调用前将该环境暴露给 Python 侧
                self._py_globals["env"] = call_env
                return target(*call_args)

            return self.call_function(target, node.args, module_env, node.named_arg_values)

        # ===== 普通函数 =====
        if name in self.environment:
            func_val = self.environment[name]

            # 如果是 pyFn 创建的 Python 可调用对象
            if callable(func_val) and not isinstance(func_val, dict):
                args = [self.evaluate(arg) for arg in node.args]
                # 调用前同步当前 DSL 环境
                self._py_globals["env"] = self.environment
                # DEBUG: 打印调用信息
                print(f"[DEBUG] 调用 pyFn: {name}")
                print(f"[DEBUG] 参数数量: {len(args)}")
                print(f"[DEBUG] 参数内容: {args}")
                result = func_val(*args)
                print(f"[DEBUG] 返回值: {result}")
                return result

            func_dict = func_val
            
            # 检查是否是类定义（从模块导入的类）
            if isinstance(func_dict, dict) and 'fields' in func_dict and 'methods' in func_dict and 'init' in func_dict:
                # 这是一个类定义，需要实例化
                # 生成一个临时的对象名
                temp_obj_name = f"__temp_obj_{id(node)}__"
                
                # 创建实例对象
                return_instance = {
                    "fields": {},
                    "methods": {},
                    "init": {},
                    "parent_name": name,
                    "fields_annotations": {},
                }
                
                # 复制类定义的内容到实例
                for field_name in func_dict['fields']:
                    return_instance["fields"][field_name] = func_dict['fields'][field_name]
                    
                for method_name in func_dict['methods']:
                    return_instance["methods"][method_name] = func_dict['methods'][method_name]
                
                # 处理构造函数
                init_def = func_dict['init']
                arg_len = len(node.args)
                matching_init = None
                
                if isinstance(init_def, list):
                    for init in init_def:
                        if len(init['args']) == arg_len:
                            matching_init = init
                            break
                else:
                    matching_init = init_def
                
                # 如果没有找到匹配的构造函数，检查是否允许无参构造
                if matching_init is None:
                    # 只有当字段数量为0时，才允许无参构造，否则报错
                    if len(func_dict['fields']) == 0:
                        # 创建一个默认的空构造函数
                        matching_init = {'args': [], 'body': [], 'default_values': {}}
                    else:
                        raise ValueError(f"No matching constructor found for class {name} with {arg_len} arguments")
                
                return_instance["init"] = matching_init
                
                # 创建新环境执行构造函数
                old_env = self.environment
                new_env = {
                    "constants": [],
                    "objects": self.environment.get("objects", {}),
                }
                
                # 将类的字段添加到新环境中
                for field_name, field_value in return_instance["fields"].items():
                    new_env[field_name] = field_value
                
                self.environment = new_env
                
                # 绑定构造函数参数
                init_args = matching_init['args']
                for i, arg_name in enumerate(init_args):
                    if i < len(node.args):
                        self.environment = old_env
                        arg_value = self.evaluate(node.args[i])
                        self.environment = new_env
                        self.environment[arg_name] = arg_value
                
                # 执行构造函数体
                from interpreter.Nodes import AssignmentNode
                init_body = matching_init['body']
                for statement in init_body:
                    if isinstance(statement, AssignmentNode) and statement.name in return_instance["fields"]:
                        value = self.evaluate(statement.value)
                        self.environment[statement.name] = value
                        return_instance["fields"][statement.name] = value
                    else:
                        self.evaluate(statement)
                
                # 将更新后的字段值复制回实例
                for field_name in return_instance["fields"]:
                    if field_name in self.environment:
                        return_instance["fields"][field_name] = self.environment[field_name]
                
                # 恢复环境
                self.environment = old_env
                
                return return_instance

            # 如果是模块函数（被 import {}）
            if isinstance(func_dict, dict) and "__module_env__" in func_dict:
                return self.call_function(
                    func_dict,
                    node.args,
                    func_dict["__module_env__"],
                    node.named_arg_values,
                )

            # 否则，本地函数
            closure_env = func_dict.get("__closure_env__", self.environment)
            return self.call_function(func_dict, node.args, closure_env, node.named_arg_values)

        raise NameError(f"Function '{name}' not defined")


    def call_function(self, func_dict, args, module_env, named_args=None):
        # 检查是否为组合函数
        if isinstance(func_dict, dict) and func_dict.get('is_combined', False):
            return self.call_combined_function(func_dict, args)
        
        func_args = func_dict["args"]
        body = func_dict["body"]
        defaults = func_dict.get("defaults", {})
        vararg_name = func_dict.get("vararg_name", None)  # 获取可变参数名
        
        # 新建子环境，parent 指向定义环境；自由变量沿链可读写到定义环境
        call_env = Environment(module_env)

        # 合并主环境与模块环境的注册表（让模块函数能访问主程序定义的类/结构体/枚举等）
        for key in ('objects', 'interfaces', 'structs', 'enums'):
            main_val = self.environment.get(key, {})
            if main_val:
                existing = call_env.get(key, {})
                merged = dict(existing)
                merged.update(main_val)
                call_env.define(key, merged)

        # 再：默认参数（define 到本层）
        for k, v in defaults.items():
            call_env.define(k, self.evaluate(v))

        # 然后：位置实参（绑定到普通参数）
        for name, arg in zip(func_args, args):
            call_env.define(name, self.evaluate(arg))

        # 最后：命名实参（按名称覆盖），并做基本校验
        if named_args:
            for param_name, value_node in named_args.items():
                if param_name not in func_args:
                    raise TypeError(f"Function argument '{param_name}' not defined")
                # 如果该参数已经通过位置参数赋值，禁止重复赋值
                positional_count = min(len(func_args), len(args))
                if param_name in func_args[:positional_count]:
                    raise TypeError(f"Multiple values for argument '{param_name}'")
                call_env.define(param_name, self.evaluate(value_node))

        # 处理可变参数：将多余的位置参数收集到一个列表中
        if vararg_name:
            # 计算已经绑定的参数数量
            bound_count = len(func_args)
            # 收集多余的参数
            varargs = []
            for i in range(bound_count, len(args)):
                varargs.append(self.evaluate(args[i]))
            # 绑定可变参数到环境
            call_env.define(vararg_name, varargs)

        # 切环境执行
        old_env = self.environment
        self.environment = call_env

        try:
            result = None
            for stmt in body:
                # 检查是否直接遇到 return 语句
                if isinstance(stmt, ReturnNode):
                    return self.evaluate(stmt)
                else:
                    result = self.evaluate(stmt)
                if isinstance(result, dict) and result.get("fight_tag") == True:
                    return result["value"]
            return result
        finally:
            # 无论正常返回、提前 return 还是抛异常，都必须把环境切回去，
            # 否则被调用函数的局部环境会泄漏给调用方，导致局部变量互相覆盖
            self.environment = old_env

    def _call_function_in_env(self, func_dict, args, base_env):
        """
        在指定环境中调用函数

        参数:
            func_dict: 函数定义字典 {'args': [...], 'body': [...], 'defaults': {...}}
            args: 传入的参数节点列表
            base_env: 基础环境（模块环境或全局环境）
        """

        # ========== 准备参数 ==========
        func_args = func_dict['args']
        body_statements = func_dict['body']
        default_values = func_dict.get('defaults', {})

        # 评估实参
        arg_values = [self.evaluate(arg) for arg in args]

        # ========== 创建局部作用域 ==========
        local_scope = base_env.copy()  #  继承基础环境

        # 绑定默认参数
        for param, default in default_values.items():
            local_scope[param] = self.evaluate(default)

        # 绑定实参
        for param, value in zip(func_args, arg_values):
            local_scope[param] = value

        # ========== 执行函数体 ==========
        old_env = self.environment
        self.environment = local_scope

        result = None
        try:
            for statement in body_statements:
                if isinstance(statement, ReturnNode):
                    result = self.evaluate(statement.value)
                    break
                result = self.evaluate(statement)
                # 检查 if 语句等控制流中的 return（通过 fight_tag 标记）
                if isinstance(result, dict) and result.get("fight_tag") == True:
                    result = result["value"]
                    break
        finally:
            # 恢复环境
            self.environment = old_env

        return result
    
    def evaluate_combine_expr(self, node):
        """
        处理函数组合表达式，如 f & g & h
        """
        func_names = node.funcs
        
        # 验证所有函数都存在
        for func_name in func_names:
            if func_name not in self.environment:
                raise NameError(f"Function '{func_name}' is not defined in function combination")
            
            func_value = self.environment[func_name]
            # 检查是否为函数
            if not isinstance(func_value, dict) or 'body' not in func_value:
                raise TypeError(f"'{func_name}' is not a function, cannot be used in function combination")
        
        # 创建一个组合函数字典，包含特殊标记
        combined_func = {
            'is_combined': True,
            'functions': func_names,
            'args': ['__combined_arg__'],  # 占位参数，实际调用时会被替换
            'body': [],  # 组合函数没有具体的body，通过特殊处理执行
            '__evaluator__': self  # 保存evaluator引用以便后续调用
        }
        
        return combined_func
    
    def evalFnCombineNode(self,node:FunctionCombinationNode):
        """
            函数组合节点: let comb = z & y & g;
            思路：创建一个组合函数，它会依次调用所有函数，将前一个函数的结果作为下一个函数的参数
            
            使用示例:
                let combined = getVal & multi & add;
                combined(5);  # 先调用getVal(5), 然后将结果传给multi, 最后传给add
        """
        # 获取所有要组合的函数名称
        func_names = node.combinations
        
        # 验证所有函数都存在
        for func_name in func_names:
            if func_name not in self.environment:
                raise NameError(f"Function '{func_name}' is not defined in function combination")
            
            func_value = self.environment[func_name]
            # 检查是否为函数
            if not isinstance(func_value, dict) or 'body' not in func_value:
                raise TypeError(f"'{func_name}' is not a function, cannot be used in function combination")
        
        # 创建一个组合函数字典，包含特殊标记
        combined_func = {
            'is_combined': True,
            'functions': func_names,
            'args': ['__combined_arg__'],  # 占位参数，实际调用时会被替换
            'body': [],  # 组合函数没有具体的body，通过特殊处理执行
            '__evaluator__': self  # 保存evaluator引用以便后续调用
        }
        
        return combined_func
    
    def call_combined_function(self, func_dict, args):
        """
            调用组合函数
            
            参数:
                func_dict: 组合函数字典，包含 'functions' 键，存储要依次调用的函数名列表
                args: 传递给第一个函数的参数列表
            
            返回:
                最后一个函数的返回值
        """
        func_names = func_dict['functions']
        
        # 先对初始参数进行求值
        evaluated_args = [self.evaluate(arg) for arg in args]
        
        # 依次调用每个函数，将前一个函数的结果作为下一个函数的参数
        result = None
        for i, func_name in enumerate(func_names):
            # 获取函数定义
            if func_name not in self.environment:
                raise NameError(f"Function '{func_name}' is not defined")
            
            func = self.environment[func_name]
            
            if i == 0:
                # 第一个函数，使用传入的参数
                from interpreter.Nodes import NumberNode, StringNode, BooleanNode
                # 将Python值转换为节点以便传递
                arg_nodes = []
                for val in evaluated_args:
                    if isinstance(val, NumberNode):
                        arg_nodes.append(val)
                    elif isinstance(val, StringNode):
                        arg_nodes.append(val)
                    elif isinstance(val, BooleanNode):
                        arg_nodes.append(val)
                    elif isinstance(val, (int, float)):
                        arg_nodes.append(NumberNode(val))
                    elif isinstance(val, str):
                        arg_nodes.append(StringNode(val))
                    elif isinstance(val, bool):
                        arg_nodes.append(BooleanNode(val))
                    else:
                        # 对于其他类型，直接使用值
                        arg_nodes.append(val)
                result = self.call_function(func, arg_nodes, self.environment)
            else:
                # 后续函数，使用前一个函数的返回值作为参数
                from interpreter.Nodes import NumberNode, StringNode, BooleanNode
                # 将结果转换为节点
                if isinstance(result, NumberNode):
                    arg_node = result
                elif isinstance(result, StringNode):
                    arg_node = result
                elif isinstance(result, BooleanNode):
                    arg_node = result
                elif isinstance(result, (int, float)):
                    arg_node = NumberNode(result)
                elif isinstance(result, str):
                    arg_node = StringNode(result)
                elif isinstance(result, bool):
                    arg_node = BooleanNode(result)
                else:
                    arg_node = result
                result = self.call_function(func, [arg_node], self.environment)
        return result
    def evaluate_list_assign(self, node: ListAssignNode):
        """
            实现列表赋值
            d[index] = val;
        """
        try:
            self.environment[self.evaluate(node.list_name)][self.evaluate(node.index_expr)] = self.evaluate(
                node.value_expr)
            return True
        except:
            return False

    def evaluate_object_assign(self, node: ObjectAssignNode):
        """
            实现对象赋值
            d{"key"} = val;
        """
        obj_name = node.object_name
        obj = self.environment[obj_name]
        obj[self.evaluate(node.key_expr)] = self.evaluate(node.value_expr)

    def evaluate_divide_assign(self, node: DivideAssignNode):
        """
            实现 /= 系列
        """
        var_name = node.var_name
        div_val = self.evaluate(node.div_val)
        self.environment[var_name] /= div_val
        return None

    def evaluate_multiply_assign(self, node: MultiplyAssignNode):
        """
            实现 *= 系列
        """
        var_name = node.var_name
        mul_val = self.evaluate(node.mul_val)
        self.environment[var_name] *= mul_val
        return None

    def evaluate_minus_assign(self, node: MinusAssignNode):
        """
            实现 -= 系列
        """
        var_name = node.var_name
        dec_val = self.evaluate(node.dec_val)
        self.environment[var_name] -= dec_val
        return None

    def evaluate_plus_assign(self, node: PlusAssignNode):
        """
            实现 += 系列
        """
        var_name = node.var_name
        inc_val = self.evaluate(node.inc_val)
        self.environment[var_name] += inc_val
        return None

    def evaluate_serial_call(self, node: SerialCall):
        """
        1. instance的连续调用
            println(p->GetName()->upper()->split("O"));
        2. str/list等类型的连续调用
            let x = "xx|xx"->upper()->split("|")->combine("@");
        """
        # 处理匿名调用（字面量调用方法）
        if node.caller == "anonymous":
            current_value = self.evaluate(node.extra)

            for method in node.methods_list:
                # 创建临时变量存储当前值
                temp_name = "__serial_temp__"
                self.environment[temp_name] = current_value
                method.instance_name = temp_name

                # 根据当前值类型决定调用方式
                if isinstance(current_value, (str, list, set)) or \
                        (isinstance(current_value, dict) and "fields" not in current_value):
                    current_value = self.execute_by_instance_type(method)
                else:
                    current_value = self.evaluate_method_call(method)

                # 清理临时变量
                del self.environment[temp_name]

            return current_value

        # 处理变量调用
        else:
            # 获取初始值
            if node.caller in self.environment["instances"]:
                # 是类实例
                current_value = self.environment["instances"][node.caller]
                is_instance = True
            elif node.caller in self.environment:
                current_value = self.environment[node.caller]
                is_instance = False
            else:
                raise NameError(f"'{node.caller}' is not defined")

            for i, method in enumerate(node.methods_list):
                # 保存当前实例，以便在方法没有返回值时使用
                previous_instance = current_value
                
                if i == 0 and is_instance:
                    # 第一个方法且 caller 是类实例，使用实例方法调用
                    result = self.evaluate_method_call(method)
                    # 如果方法没有返回值（返回None），则继续使用原实例以支持链式调用
                    if result is None and isinstance(previous_instance, dict) and "fields" in previous_instance:
                        current_value = previous_instance
                    else:
                        current_value = result
                else:
                    # 后续方法或非实例调用，基于当前值类型
                    temp_name = "__serial_temp__"
                    self.environment[temp_name] = current_value
                    method.instance_name = temp_name

                    # 判断当前值是基本类型还是实例
                    if isinstance(current_value, (str, list, set)) or \
                            (isinstance(current_value, dict) and "fields" not in current_value):
                        current_value = self.execute_by_instance_type(method)
                    else:
                        # 是实例对象
                        self.environment["instances"][temp_name] = current_value
                        result = self.evaluate_method_call(method)
                        # 如果方法没有返回值（返回None），则继续使用原实例以支持链式调用
                        if result is None and isinstance(previous_instance, dict) and "fields" in previous_instance:
                            current_value = previous_instance
                        else:
                            current_value = result
                        del self.environment["instances"][temp_name]

                    del self.environment[temp_name]

            return current_value

    def evaluate_list_generator(self, node: ListGeneratorNode):
        """
            实现列表生成器
        """
        pre_env = self.environment.copy()

        start = self.evaluate(node.start)
        end = self.evaluate(node.end)
        step = self.evaluate(node.step)

        # 返回的列表
        gen_list = []

        self.environment[f"{node.iter_name}"] = start

        # 左closed, right closed
        for i in range(start, end + 1, step):
            # print("i = ", i)
            gen_list.append(self.evaluate(node.gen_expr))
            if end > start:
                self.environment[f"{node.iter_name}"] = i + step
            else:
                self.environment[f"{node.iter_name}"] = i - step

        # print("gen_list = ", gen_list)
        self.environment = pre_env.copy()
        return gen_list

    def evaluate_do_while(self, node: DoWhileNode):
        """
            实现 do while 循环
        """

        for statement in node.body:
            self.evaluate(statement)
        cond = self.evaluate(node.condition)
        while cond:
            for statement in node.body:
                self.evaluate(statement)
            cond = self.evaluate(node.condition)

    def execute_by_instance_type(self, node: MethodCallNode):
        """
            根据实例的类型，调用相应的方法
        """
        # print("进入execute_by_instance_type")
        is_anonymous_call = False
        # ""->lower()->split()这样 字面量调用方法
        if node.instance_name == "anonymous":
            is_anonymous_call = True
            # ["anonymous"] = 初始值
            self.environment[node.instance_name] = self.evaluate(node.extra)

        var_value = self.environment[node.instance_name]

        # 根据数据类型进行对应方法的调用，也就是说，这样存在一个对类型的隐式判断
        if isinstance(var_value, str):
            val = self.evaluate_string_type_method_call(node)
            if is_anonymous_call:
                del self.environment[node.instance_name]
            return val

        if isinstance(var_value, list):
            val = self.evaluate_list_type_method_call(node)
            if is_anonymous_call:
                del self.environment[node.instance_name]
            return val

        if isinstance(var_value, dict):
            val = self.evaluate_dict_type_method_call(node)
            if is_anonymous_call:
                del self.environment[node.instance_name]
            return val

        if isinstance(var_value, set):
            val = self.evaluate_set_type_method_call(node)
            if is_anonymous_call:
                del self.environment[node.instance_name]
            return val

    def evaluate_set_type_method_call(self, node: MethodCallNode):
        """
            调用set的方法
        """
        var_name = node.instance_name
        method_name = node.method_name
        arguments = [self.evaluate(arg) for arg in node.arguments]

        # 获取参数的值
        if method_name == "add":
            try:
                for arg in arguments:
                    self.environment[var_name].add(arg)
                return True
            except:
                return False
        if method_name == "remove":
            try:
                self.environment[var_name].remove(arguments[0])
                return True
            except:
                return False
        if method_name == "clear":
            self.environment[var_name].clear()
            return True
        if method_name == "size":
            return len(self.environment[var_name])
        if method_name == "contains":
            return arguments[0] in self.environment[var_name]

        # =======集合上的方法=============
        # s->isSubset( z2): bool
        # isSuperset(): bool
        # union(): Set
        # intersection(): Set
        # difference(): Set
        if method_name == "isSubset":
            return set(self.environment[var_name]).issubset(arguments[0])
        if method_name == "isSuperset":
            return set(self.environment[var_name]).issuperset(arguments[0])
        if method_name == "union":
            return set(self.environment[var_name]).union(arguments[0])
        if method_name == "intersection":
            return set(self.environment[var_name]).intersection(arguments[0])
        if method_name == "difference":
            return set(self.environment[var_name]).difference(arguments[0])

    def evaluate_dict_type_method_call(self, node: MethodCallNode):
        """
            调用字典的方法
        """
        var_name = node.instance_name
        method_name = node.method_name
        # 获取参数的值
        arguments = [self.evaluate(arg) for arg in node.arguments]
        # print("======================================")
        # print("变量名称: ", var_name)
        # print("方法每次: ", method_name)
        # print("参数: ", arguments)
        # print("==========")
        if method_name == "getKeys":
            return list(self.environment[var_name].keys())
        if method_name == "getValues":
            return list(self.environment[var_name].values())

        if method_name == "getValue":
            return self.environment[var_name].get(arguments[0])

        # 通过key 删除元素
        if method_name == "deleteItem":
            return self.environment[var_name].pop(arguments[0])

        if method_name == "update":
            self.environment[var_name].update(arguments[0])
            return None

        if method_name == "clear":
            self.environment[var_name].clear()
            return None

        # 返回嵌套的list 比如： [['name', 'Alice'], ['age', 20]]
        if method_name == "getItems":
            return list([list(item) for item in self.environment[var_name].items()])

        if method_name == "hasKey":
            return arguments[0] in self.environment[var_name]

    def evaluate_string_type_method_call(self, node: MethodCallNode):
        """
            调用字符串的方法
        """
        var_name = node.instance_name
        method_name = node.method_name
        # 获取参数的值
        arguments = [self.evaluate(arg) for arg in node.arguments]
        # print("======================================")
        # print("变量名称: ", var_name)
        # print("方法每次: ", method_name)
        # print("参数: ", arguments)
        # print("======================================")

        # 常见方法
        if method_name == "length":
            return len(self.environment[var_name])
        if method_name == "upper":
            self.environment[var_name] = self.environment[var_name].upper()
            return self.environment[var_name]
        if method_name == "lower":
            self.environment[var_name] = self.environment[var_name].lower()
            return self.environment[var_name]
        if method_name == "startsWith":
            return self.environment[var_name].startswith(arguments[0])
        if method_name == "endsWith":
            return self.environment[var_name].endswith(arguments[0])
        if method_name == "capitalize":
            self.environment[var_name] = self.environment[var_name].capitalize()
            return self.environment[var_name]
        if method_name == "swapcase":
            self.environment[var_name] = self.environment[var_name].swapcase()
            return self.environment[var_name]
        # 分割与连接
        if method_name == "split":
            separator = arguments[0]
            return self.environment[var_name].split(separator)
        if method_name == "strip":
            self.environment[var_name] = self.environment[var_name].strip()
            return self.environment[var_name]
        # 类型检查
        if method_name == "isAlpha":
            return self.environment[var_name].isalpha()
        if method_name == "isDigit":
            return self.environment[var_name].isdigit()
        if method_name == "isAlphaNum":
            return self.environment[var_name].isalnum()
        if method_name == "isSpace":
            return self.environment[var_name].isspace()
        if method_name == "isLower":
            return self.environment[var_name].islower()
        if method_name == "isUpper":
            return self.environment[var_name].isupper()
        if method_name == "concat":  # 连接字符串
            self.environment[var_name] = self.environment[var_name] + arguments[0]
            return self.environment[var_name]
        if method_name == "charAt":
            return self.environment[var_name][arguments[0]]

        if method_name == "indexOf":
            return self.environment[var_name].find(arguments[0])

        if method_name == "contains":
            return arguments[0] in self.environment[var_name]

    def evaluate_list_type_method_call(self, node: MethodCallNode):

        """
            改进：
                记录每个数据的初始类型（类型推断），然后在调用方法的时候
                根据类型进行调用

            调用基本数据类型的方法，比如字符串的split()方法
        """
        pass
        var_name = node.instance_name
        method_name = node.method_name
        arguments = [self.evaluate(arg) for arg in node.arguments]

        # 列表的append方法
        if method_name == "append":
            # 列表的append方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only append to list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的追加
            for arg in arguments:
                value.append(arg)
            return value

        # insert方法
        if method_name == "insert":
            # 列表的insert方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only insert to list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的插入
            index = arguments[0]
            for arg in arguments[1:]:
                value.insert(index, arg)
                index += 1
            return value

        # 删除成功，返回True，否则返回False
        # remove(元素),
        if method_name == "remove":
            # 列表的remove方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only remove from list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的删除
            for arg in arguments:
                value.remove(arg)
            return value

        # 删除指定位置的元素
        # removeAt(索引)
        if method_name == "removeAt":
            # 列表的pop方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only removeAt from list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的删除
            index = arguments[0]
            value.pop(index)
            return value
        # 查找元素的索引
        if method_name == "indexOf":
            # 列表的index方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only index list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的索引
            arg = arguments[0]

            # 列表中不存在该元素，返回-1
            if arg not in value:
                return -1
            return value.index(arg)

        # 计数: count(元素)
        if method_name == "count":
            # 列表的count方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only count list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的计数
            arg = arguments[0]
            return value.count(arg)

        # reverse()方法
        if method_name == "reverse":
            # 列表的reverse方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only reverse list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的反转
            value.reverse()
            return value

        # clear()方法
        if method_name == "clear":
            # 列表的clear方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only clear list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的清空
            value.clear()
            return value

        # 判断列表是否包含某个元素
        if method_name == "has" or method_name == "contains":
            # list的for in
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only has list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的判断是否包含
            arg = arguments[0]
            return arg in value

        # set 设置列表某个索引的值
        if method_name == "setAt":
            # 列表的set方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            xlist = self.environment[var_name]

            if type(xlist) != list:
                raise TypeError(f"can only set list, but got {type(xlist)}")
            # 支持任意数量和任意类型类型的数据的设置
            index = arguments[0]
            xlist[index] = arguments[1]

            return xlist
        # isEmpty()方法
        if method_name == "isEmpty":
            # 列表的isEmpty方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            if type(value) != list:
                raise TypeError(f"can only isEmpty list, but got {type(value)}")
            # 支持任意数量和任意类型类型的数据的判断是否为空
            return len(value) == 0
        # length()方法
        if method_name == "length":
            # 列表的length方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            value = self.environment[var_name]
            # 支持任意数量和任意类型类型的数据的长度
            # print("len = ", len(value))
            return len(value)

        # combine, 类似join方法
        if method_name == "combine":
            # 列表的combine方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            xlist = self.environment[var_name]
            if type(xlist) != list:
                raise TypeError(f"can only combine list, but got {type(xlist)}")
            # 支持任意数量和任意类型类型的数据的合并
            separator = arguments[0]

            # 将每个元素转化为字符串
            xlist = [str(x) for x in xlist]

            return separator.join(xlist)

        # FunctionDeclarationNode
        # filter()方法
        if method_name == "filter":
            # 列表的filter方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            xlist = self.environment[var_name]
            if type(xlist) != list:
                raise TypeError(f"can only filter list, but got {type(xlist)}")
            # 支持任意数量和任意类型类型的数据的过滤
            filter_func_dict = arguments[0]
            return self.filter_server(filter_func_dict, xlist)

        # map()方法
        if method_name == "map":
            # 列表的map方法
            if var_name not in self.environment:
                raise NameError(f"name '{var_name}' is not defined")
            xlist = self.environment[var_name]
            if type(xlist) != list:
                raise TypeError(f"can only map list, but got {type(xlist)}")
            # 支持任意数量和任意类型类型的数据的映射
            map_func_dict = arguments[0]
            return self.map_server(map_func_dict, xlist)
        # ===============set类型的方法=======================

    def map_server(self, map_func, xlist):
        """
            服务map函数的, 可以服务map等函数
            map_func_dict: 匿名函数，用来map的条件
            xlist: 待映射的列表
        """
        func_dict = map_func  # 值居然是None
        # print("predicate_param_name: ", func_dict)  # None

        # 组合函数（f & g）没有函数体，需要走组合函数的调用逻辑
        if func_dict.get('is_combined'):
            mapped_result = []
            for element in xlist:
                mapped_result.append(self.call_combined_function(func_dict, [element]))
            return mapped_result

        predicate_param_name = func_dict['args'][0]  # 形参名称,比如['x']
        # 用定义时的闭包环境调用函数，保证闭包能访问其自由变量
        closure_env = func_dict.get("__closure_env__", self.environment)
        return [self.call_function(func_dict, [element], closure_env) for element in xlist]

    def filter_server(self, filter_predicate, xlist):
        """
            服务filter函数的, 可以服务map等函数
            filter_predicate: 匿名函数，用来filter的条件
            xlist: 待过滤的列表
        """
        # func_dict的样子: {
        #   args': ['x'],
        #   'body': [ReturnNode(value=BinaryOpNode(left=VariableNode(value=x), op=GT, right=NumberNode(value=1)))]

        func_dict = filter_predicate  # 值居然是None

        # 组合函数（f & g）没有函数体，需要走组合函数的调用逻辑
        if func_dict.get('is_combined'):
            filtered_result = []
            for element in xlist:
                if self.call_combined_function(func_dict, [element]):
                    filtered_result.append(element)
            return filtered_result

        predicate_param_name = func_dict['args'][0]  # 形参名称,比如['x']
        # 用定义时的闭包环境调用函数
        closure_env = func_dict.get("__closure_env__", self.environment)
        return [element for element in xlist if self.call_function(func_dict, [element], closure_env)]

    # def evaluate_enum_access(self, node: EnumAccessNode):
    #     is_from_module = self.check_is_from_module(node.name)
    #     print("\n\nis_from_module(枚举): ", is_from_module, "\n")
    #
    #     # 保存旧环境
    #     old_env = self.environment.copy()
    #
    #     # 说明是来自模块的函数
    #     if isinstance(is_from_module, str):
    #         # 找到模块环境
    #         module_env = self.modules[is_from_module]
    #         print("module_env: ",module_env)  # enums里面是empty
    #
    #         # 合并模块内部的和外部的环境（核心）
    #         self.environment.update(module_env)
    #         # 使用合并后的环境进行函数调用
    #         value = self.evaluate_enum_access2(node)
    #         # 还原环境
    #         self.environment = old_env
    #         return value
    #
    #
    #     # 说明是来自 main 环境的函数
    #     elif isinstance(is_from_module, bool):
    #         # 调用函数
    #         value = self.evaluate_enum_access2(node)
    #         return value

    def evaluate_enum_access(self, node: EnumAccessNode):
        """
            let x = enum::Color.Red;
            EnumAccessNode(name=Color, value=Red)
            task:
                检查访问的属性是否存在于枚举类中，
                1，存在；返回值
                2，不存在；raise NameError
        """
        # 检擦枚举类是否存在

        if node.enum_name not in self.environment["enums"]:
            raise NameError(f"Enum {node.enum_name} not found!")
        if node.enum_property not in self.environment["enums"][node.enum_name]:
            raise NameError(f"Enum property '{node.enum_property}' not found in {node.enum_name}!")
        return node.enum_property
    
    def evaluate_module_enum_access(self, node: ModuleEnumAccessNode):
        """
        求值模块枚举访问: bigJ.Color::RED
        
        处理流程：
        1. 通过模块名获取模块环境
        2. 从模块环境中获取枚举定义
        3. 检查枚举值是否存在
        """
        # 获取模块环境
        module_env = self.module_aliases.get(node.module_name)
        if module_env is None:
            raise NameError(f"Module '{node.module_name}' not found or not imported!")
        
        # 从模块环境中检查枚举是否存在
        if node.enum_name not in module_env.get("enums", {}):
            raise NameError(f"Enum '{node.enum_name}' not found in module '{node.module_name}'!")
        
        enum_values = module_env["enums"][node.enum_name]
        
        # 检查枚举值是否存在
        if node.enum_property not in enum_values:
            raise NameError(
                f"Enum property '{node.enum_property}' not found in {node.enum_name}! "
                f"Available values: {enum_values}"
            )
        
        return node.enum_property
    
    def evaluate_module_class_instantiation(self, node: ModuleClassInstantiationNode):
        """
        求值模块类实例化: let c = new bigJ.Cal("name")
        
        处理流程：
        1. 通过模块名获取模块环境
        2. 从模块环境中获取类定义
        3. 实例化该类（类似于 evaluate_new_object_expr，但从模块环境中获取类定义）
        """
        # 获取模块环境
        module_env = self.module_aliases.get(node.module_name)
        if module_env is None:
            raise NameError(f"Module '{node.module_name}' not found or not imported!")
        
        # 从模块环境中检查类是否存在
        if node.class_name not in module_env.get("objects", {}):
            raise NameError(f"Class '{node.class_name}' not found in module '{node.module_name}'!")
        
        # 获取类定义
        original_class_definition = module_env["objects"][node.class_name]
        
        # 保存当前状态
        old_current_class = self.current_class
        old_current_parent = self.current_parent_class
        self.current_class = node.class_name
        
        # 创建实例对象
        return_instance = {
            "fields": {},
            "methods": {},
            "init": {},
            "parent_name": node.class_name,
            "fields_annotations": {},
        }
        
        # 设置父类名称
        self.current_parent_class = original_class_definition.get("parent_name", "")
        
        # 处理 fields
        for field_name in original_class_definition['fields']:
            field_value = original_class_definition['fields'][field_name]
            return_instance["fields"][field_name] = field_value
        
        # 处理 fields_annotations
        for field_name in original_class_definition['fields_annotations']:
            field_annotation = original_class_definition['fields_annotations'][field_name]
            return_instance["fields_annotations"][field_name] = field_annotation
        
        # 处理 methods
        for method_name in original_class_definition['methods']:
            method_body = original_class_definition['methods'][method_name]['body']
            method_args = original_class_definition['methods'][method_name]['args']
            method_default_values = original_class_definition['methods'][method_name]['default_values']
            return_instance["methods"][method_name] = {
                "annotations": original_class_definition['methods'][method_name]["annotations"],
                "args": method_args,
                "body": method_body,
                "default_values": method_default_values,
            }
        
        # 选择匹配的构造函数
        arg_len = len(node.arguments)
        matching_init = None
        if isinstance(original_class_definition['init'], list):
            for init in original_class_definition['init']:
                if len(init['args']) == arg_len:
                    matching_init = init
                    break
        else:
            matching_init = original_class_definition['init']
        
        if matching_init is None:
            raise ValueError(f"No matching constructor found for {arg_len} arguments")
        
        # 使用匹配的构造函数
        init_args = matching_init['args']
        init_body = matching_init['body']
        init_default_values = matching_init.get('default_values', {})
        return_instance["init"] = {
            "args": init_args,
            "body": init_body,
            "default_values": init_default_values
        }
        
        # 保存 objects 引用，供 super 使用
        # 注意：这里需要同时保存当前环境和模块环境的 objects
        self._saved_objects = {**self.environment.get("objects", {}), **module_env.get("objects", {})}
        
        # 创建新环境
        old_env = self.environment
        new_env = {
            "constants": [],
            "objects": {},
        }
        
        # 将类的字段添加到新环境中
        for field_name, field_value in return_instance["fields"].items():
            new_env[field_name] = field_value
        
        self.environment = new_env  # 切换到新环境
        
        # 将传进来的参数放到新环境里面
        for i in range(len(node.arguments)):
            arg_name = init_args[i]
            # 临时用旧环境来解析参数
            self.environment = old_env
            arg_value = self.evaluate(node.arguments[i])
            self.environment = new_env
            self.environment[arg_name] = arg_value
        
        # init里面的this->xxx()类方法
        delay_calls = []
        delay_caller = None
        
        # 处理init函数体
        for statement in init_body:
            if isinstance(statement, AssignmentNode) and statement.name in return_instance["fields"]:
                # 更新字段值
                value = self.evaluate(statement.value)
                self.environment[statement.name] = value
                return_instance["fields"][statement.name] = value
            elif isinstance(statement, CallClassInnerMethod):
                # 处理this->xxx()调用
                delay_calls.append(statement)
                delay_caller = node.object_name
            else:
                self.evaluate(statement)
        
        # 将更新后的字段值复制回return_instance
        for field_name in return_instance["fields"]:
            if field_name in self.environment:
                return_instance["fields"][field_name] = self.environment[field_name]
        
        # 恢复旧环境
        self.environment = old_env
        
        # 将实例对象放到environment中
        self.environment["instances"][node.object_name] = return_instance
        
        # 处理延迟调用
        for this_call_in_init in delay_calls:
            self.evaluate_call_class_inner_method(this_call_in_init, delay_caller)
        
        # 恢复之前的 current_class
        self.current_class = old_current_class
        self.current_parent_class = old_current_parent
        
        return return_instance

    def evaluate_enum_declaration(self, node: EnumDeclarationNode):
        """
            枚举类型定义
        """
        # 枚举类型定义
        # print("node: ", node)
        enum_values = []
        for enum_name in node.enum_values:
            enum_values.append(enum_name)
        self.environment["enums"][node.enum_name] = enum_values
        # print(f"Enum {node.enum_name} declared.")
        # print("env: ", self.environment)
        return None

    def evaluate_struct_access(self, node: StructAccessNode):
        """
             访问结构体的属性
             比如:
                p::x
        """
        if node.struct_instance_name not in self.environment:
            raise NameError(f"struct instance {node.struct_instance_name} not found!")

        struct_dict = self.environment[node.struct_instance_name]
        # struct_dict 比如: {'type': 'struct', 'name': 'Point', 'value': {'x': 1, 'y': 2}}

        # 访问不存在的属性
        if node.field_name not in struct_dict["value"]:
            return False
        return struct_dict["value"][node.field_name]

    def evaluate_struct_access_assign(self, node: StructAccessAssignNode):
        """
            给结构体实例的属性赋值
            比如:
                p::x = 99;
        """
        if node.struct_instance_name not in self.environment:
            raise NameError(f"struct instance {node.struct_instance_name} not found!")

        struct_dict = self.environment[node.struct_instance_name]
        # struct_dict 比如: {'type': 'struct', 'name': 'Point', 'value': {'x': 1, 'y': 2}}

        if node.field_name not in struct_dict["value"]:
            raise NameError(
                f"struct {struct_dict['name']} has no field '{node.field_name}'!")

        value = self.evaluate(node.value_expr)
        struct_dict["value"][node.field_name] = value
        return value

    def evaluate_struct_assign(self, node: StructAssignNode):

        # 检查结构体是否存在
        if node.struct_name not in self.environment["structs"]:
            raise NameError(f"struct  {node.struct_name} not found!")

        # 检查结构体是否有这个属性: 不能瞎赋值
        for field_name in node.struct_fields_values:
            if field_name not in self.environment["structs"][node.struct_name]:
                raise NameError(f"struct {node.struct_name} has no field '{field_name}'!")

        result = {
            "type": "struct",
            "name": f"{node.struct_name}",
            "value": {}
        }
        for field_name in node.struct_fields_values:
            field_value = self.evaluate(node.struct_fields_values[field_name])
            result["value"][field_name] = field_value
        return result
    
    def evaluate_module_struct_assign(self, node: ModuleStructAssignNode):
        """
        求值模块结构体实例化: bigJ.Book{title: "Fight", price: 99}
        
        处理流程：
        1. 通过模块名获取模块环境
        2. 从模块环境中获取结构体定义
        3. 根据字段值实例化结构体
        """
        # 获取模块环境
        module_env = self.module_aliases.get(node.module_name)
        if module_env is None:
            raise NameError(f"Module '{node.module_name}' not found or not imported!")
        
        # 从模块环境中检查结构体是否存在
        if node.struct_name not in module_env.get("structs", {}):
            raise NameError(f"Struct '{node.struct_name}' not found in module '{node.module_name}'!")
        
        struct_definition = module_env["structs"][node.struct_name]
        
        # 处理简写格式：按字段顺序赋值
        if '__short_format__' in node.struct_fields_values:
            field_values = node.struct_fields_values['__short_format__']
            # 获取结构体字段的顺序（Python 3.7+ 字典保持插入顺序）
            field_names = list(struct_definition.keys())
            
            if len(field_values) != len(field_names):
                raise ValueError(
                    f"Struct '{node.struct_name}' expects {len(field_names)} fields, "
                    f"but got {len(field_values)} values"
                )
            
            # 构造完整格式的字段字典
            struct_fields_values = {}
            for field_name, field_value in zip(field_names, field_values):
                struct_fields_values[field_name] = field_value
        else:
            # 完整格式：直接使用
            struct_fields_values = node.struct_fields_values
            
            # 检查字段是否都存在
            for field_name in struct_fields_values:
                if field_name not in struct_definition:
                    raise NameError(
                        f"Struct '{node.struct_name}' has no field '{field_name}'!"
                    )
        
        # 构造结构体实例
        result = {
            "type": "struct",
            "name": f"{node.struct_name}",
            "value": {}
        }
        
        for field_name in struct_fields_values:
            field_value = self.evaluate(struct_fields_values[field_name])
            result["value"][field_name] = field_value
        
        return result

    def evaluate_struct_declaration(self, node: StructDeclarationNode):
        """
            将结构体的名称放到env中，以便后续使用
        :param node:
        :return:
        """
        # if node.struct_name  in self.environment["structs"]:
        #     raise NameError(f"Struct '{node.struct_name}' already exists!")
        self.environment["structs"][node.struct_name] = node.fields
        return None

    def evaluate_set_node(self, node: SetNode):
        # 借用python的set类型创建set类型
        set_result = []
        for element in node.set_values:
            r = self.evaluate(element)
            set_result.append(r)
        return set(set_result)

    def evaluate_decrement(self, node: DecrementNode):
        # 处理自减运算符
        var_name = node.var_name
        if var_name not in self.environment:
            raise NameError(f"name '{var_name}' is not defined")
        value = self.environment[var_name]
        if type(value) != int:
            raise TypeError(f"can only decrement integer, but got {type(value)}")
        self.environment[var_name] = value - 1
        # return value - 1

    def evaluate_increment(self, node: IncrementNode):
        # 处理自增运算符
        var_name = node.var_name
        if var_name not in self.environment:
            raise NameError(f"name '{var_name}' is not defined")
        value = self.environment[var_name]
        if type(value) != int:
            raise TypeError(f"can only increment integer, but got {type(value)}")
        self.environment[var_name] = value + 1
        # return value + 1

    def evaluate_try_catch_finally(self, node: TryCatchFinallyNode):
        # 解析try catch finally语句
        """
            核心科技:
                当捕获到异常时，你需要将Python的异常转换为你的语言中对应的异常类型。


        """
        # 定义异常类型映射
        exception_mapping = {
            ZeroDivisionError: "ZeroDivisionError",
            ValueError: "ValueError",
            TypeError: "TypeError",
            NameError: "NameError",
            IndexError: "IndexError",
            KeyError: "KeyError",
            AttributeError: "AttributeError",
            FileNotFoundError: "FileNotFoundError",
            IOError: "IOError",
            ImportError: "ImportError",
            SyntaxError: "SyntaxError",
            IndentationError: "IndentationError",
            OverflowError: "OverflowError",
            AssertionError: "AssertionError",
            RuntimeError: "RuntimeError",
            MemoryError: "MemoryError",
            RecursionError: "RecursionError",
            NotImplementedError: "NotImplementedError",
            PermissionError: "PermissionError",
            TimeoutError: "TimeoutError",
        }

        # 定义打印红色字体的函数
        # def print_red(text):
        #     print("\033[91m{}\033[0m".format(text))

        try:
            for statement in node.try_block:
                self.evaluate(statement)
        except Exception as e:

            # 异常映射
            # 将Python异常转换为你的语言的异常
            caught_exception = exception_mapping.get(type(e), "Exception")
            # print_red(f"Caught Exception: {e}")
            # 捕获异常  catch_block = [{err_type: [stmt1, stmt2, stmt3] }]
            for catch_dict in node.catch_block:
                for err_type in catch_dict:
                    # 遍历catch_block字典，找到对应的异常类型
                    if err_type == caught_exception:
                        for stmt in catch_dict[err_type]:
                            self.evaluate(stmt)
        finally:
            # 没有异常，执行finally语句
            for finally_statement in node.finally_block:
                self.evaluate(finally_statement)

    def evaluate_for_range_number(self, node: ForRangeNumberNode):
        # 两种类型： 1，递增 2，递减  如果传进来的参数是小说，range方法自己会报错

        # for(idx: 1..10){}
        # 解析for循环语句
        # 先计算表达式的值
        start_value = self.evaluate(node.start_num)
        end_value = self.evaluate(node.end_num)

        # 判断是不是小数
        if type(start_value) == float:
            raise TypeError(f"only support integer, but got float {start_value}")
        if type(end_value) == float:
            raise TypeError(f"only support integer, but got float {end_value}")

        # 只保存循环变量自身之前的状态。
        # 注意：不能对整个环境做快照还原，否则循环体内对其他变量的赋值会被回滚掉
        had_loop_var = node.var_name in self.environment
        old_loop_var_value = self.environment.get(node.var_name)

        # 设置初始变量
        self.environment[node.var_name] = -100

        # for(idx: 1..10){} 递增类型（起始值等于结束值时也要执行一次）
        if start_value <= end_value:
            # 遍历每个元素
            for i in range(start_value, end_value + 1):
                # print("i = ",i)
                self.environment[node.var_name] = i
                try:
                    for statement in node.body:
                        if isinstance(statement, ReturnNode):
                            return {"fight_tag": True, "value": self.evaluate(statement.value)}
                        result = self.evaluate(statement)
                        if isinstance(result, dict) and result.get("fight_tag") is True:
                            return result
                except BreakException:
                    break

        # for(idx: 10..1){} 倒退类型
        if start_value > end_value:
            # 遍历每个元素
            for i in range(start_value, end_value - 1, -1):
                # print("i = ",i)
                self.environment[node.var_name] = i
                try:
                    for statement in node.body:
                        if isinstance(statement, ReturnNode):
                            return {"fight_tag": True, "value": self.evaluate(statement.value)}
                        result = self.evaluate(statement)
                        if isinstance(result, dict) and result.get("fight_tag") is True:
                            return result
                except BreakException:
                    break

        # 只还原循环变量，循环体内产生的其他副作用要保留
        if had_loop_var:
            self.environment[node.var_name] = old_loop_var_value
        else:
            self.environment.pop(node.var_name, None)

    def evaluate_interface_declaration(self, node: InterfaceNode):
        # 处理接口定义: 将接口加入到environment中, 类实现的时候要用到
        # {"接口名称": {"methods": [方法名称1, 方法名称2, ...], "constants": {常量名: 常量值}}}
        
        # 求值常量
        evaluated_constants = {}
        for const_name, const_value_node in node.constants.items():
            evaluated_constants[const_name] = self.evaluate(const_value_node)
        
        # 存储接口定义
        self.environment["interfaces"][node.interface_name] = {
            "methods": node.methods,
            "constants": evaluated_constants
        }

    def evaluate_list_deconstruct_assign(self, node: ListDeconstructAssignNode):
        # 解构列表赋值, 比如 let [a, _,b] = [1, 2,3];

        # node.vars_list 是一个dict，里面是变量名
        for var_name in node.vars_list:
            # 判断变量是否已经存在于环境中
            if var_name in self.environment:
                raise NameError(f"Variable '{var_name}' already exists!")
            # node.vars_list的样子： {”a“:index1, “b”:index2}
            index = node.vars_list[var_name]  # 获取变量名称对应的索引
            if index >= len(self.evaluate(node.list_obj)):
                raise IndexError(f"Index {index} out of range for list of length {len(self.evaluate(node.list_obj))}")
            value = self.evaluate(node.list_obj)[index]
            # 将值放到环境中
            self.environment[var_name] = value

    def evaluate_decontruct_assign(self, node: DecontructAssignNode):
        # 解构赋值  let {a, b} = {"a": 1, "b": 2}; 或者 let {c,d} = dictObj;
        # 否则，直接求值

        # 判断变量是否已经存在于环境中
        for var in node.vars_list:
            if var in self.environment:
                raise NameError(f"Variable '{var}' already exists!")

        for var_name in node.vars_list:
            key_exist = False
            # print(var_name)
            for key in self.evaluate(node.dict_obj):
                if key == var_name:
                    key_exist = True
                    self.environment[var_name] = self.evaluate(node.dict_obj)[key]
                    break
            if not key_exist:
                raise NameError(f"Key '{var_name}' not found in the right object.")

    def evaluate_switch_statement(self, node: SwitchNode):
        """
            解析switch语句
            switch(x){
                case(x){

                }
                case(y){

                }
                default{

                }
            }
        """
        # node.cases是一个字典，key是case的表达式，value是list装的一系列的语句

        # 先计算表达式的值
        condition_value = self.evaluate(node.expr)
        # print("condition_value: ", condition_value)
        for case in node.cases:  # case是xxNode()，需要解析
            # print("case: ", self.evaluate(case))
            if self.evaluate(case) == condition_value:
                for statement in node.cases[case]:
                    self.evaluate(statement)
                break
            elif self.evaluate(case) == "default":
                for statement in node.cases[case]:
                    self.evaluate(statement)
                break

    def evaluate_match_expr(self, node: MatchExprNode):
        """
            解析 match 表达式，支持：
            1) 单值匹配:      1 => "one"
            2) 多个值匹配:    1,2 => "one and two"
            3) 范围匹配:      1-10 => "between 1 and 10"   （仅在 case 中视为闭区间，不做减法）
        """
        # 先计算被匹配的表达式的值
        condition_value = self.evaluate(node.expr)

        # 依次按照定义顺序遍历所有 case
        for case_node, result_expr in node.case_value_dict.items():
            # 1. 范围匹配：形如 1-10 的 BinaryOpNode，并且左右都是数字常量
            if (isinstance(case_node, BinaryOpNode)
                    and case_node.op == "MINUS"
                    and isinstance(case_node.left, NumberNode)
                    and isinstance(case_node.right, NumberNode)):
                start = self.evaluate(case_node.left)
                end = self.evaluate(case_node.right)

                # 支持写成 10-1 或 1-10，统一转换成 [low, high]
                low, high = (start, end) if start <= end else (end, start)

                # 只有当被匹配值是数字时才做区间判断
                if isinstance(condition_value, (int, float)) and low <= condition_value <= high:
                    return self.evaluate(result_expr)
                # 不匹配则继续后续 case
                continue

            # 2. 普通等值匹配：evaluate(case_node) == condition_value
            if self.evaluate(case_node) == condition_value:
                return self.evaluate(result_expr)

        # 3. 没有任何 case 匹配，执行 else 分支（如果有）
        if node.else_expr is not None:
            return self.evaluate(node.else_expr)
        # 如果没有 else 分支，返回 None
        return None

    def evaluate_if_expr(self, node: IfExprNode):
        """
            解析if表达式
            先计算条件表达式，然后根据条件表达式的结果，决定执行哪个分支
            注意：if表达式的返回值是表达式的值，而不是语句的值
        """
        # 计算条件表达式
        condition_value = self.evaluate(node.condition)
        # print("condition_value: ", condition_value)
        if type(condition_value) != bool:
            raise TypeError(f"Condition expression must be a boolean, but got {type(condition_value)}")

        # 根据条件表达式的结果，决定执行哪个分支
        if condition_value:
            return self.evaluate(node.expr_if_true)
        else:
            return self.evaluate(node.expr_if_false)

    def evaluate_call_class_inner_method(self, node: CallClassInnerMethod, outer_instance_name=None):
        """
                解析类内部方法调用: this->xxx()

            语义：仅在“当前有实例”的上下文中使用：
            - 普通实例方法中：使用 self.current_object 作为实例名
            - init 内部延迟调用：调用方通过 outer_instance_name 显式传入
        """
        # 静态方法中禁止使用 this，避免从静态上下文调用实例方法
        if self._static_context:
            raise RuntimeError("Cannot use 'this' inside a static method")

        # 确定 this 指向的实例名
        instance_name = outer_instance_name or self.current_object

        if instance_name is None:
            raise RuntimeError("this->method() can only be used inside an instance context")

        # 复用实例方法调用逻辑，保持字段更新等行为一致
        temp_method_call = MethodCallNode(instance_name, node.method_name, node.arguments)
        old_internal = self._internal_method_call
        self._internal_method_call = True
        try:
            return self.evaluate_method_call(temp_method_call)
        finally:
            self._internal_method_call = old_internal

    def evaluate_get_instance_member(self, node: GetMemberNode):
        """
        GetMemberNode
             self.instance_name = instance_name
             self.member_name = member_name
        """

        # ==============接口常量========================================
        # 判断是不是在访问接口的常量
        if node.instance_or_class_name in self.environment.get("interfaces", {}):
            interface_def = self.environment["interfaces"][node.instance_or_class_name]
            if node.member_name in interface_def["constants"]:
                return interface_def["constants"][node.member_name]
            else:
                raise NameError(f"Constant '{node.member_name}' not found in interface '{node.instance_or_class_name}'")
        # ==============接口常量========================================

        # ==============静态属性========================================
        # 判断是不是在访问类的static属性
        if node.instance_or_class_name in self.environment.get("objects", {}):
            # print("md 一个类啊")
            return self.environment["objects"][node.instance_or_class_name]["static_fields"][node.member_name]
        # ==============静态属性========================================

        # 将instance的字段对应的值返回
        instance_name = node.instance_or_class_name
        field_name = node.member_name

        # 新增：检查是否是环境中的变量（值为实例字典）
        if instance_name in self.environment:
            instance_val = self.environment[instance_name]
            if isinstance(instance_val, dict) and "fields" in instance_val:
                # private属性不允许访问
                if field_name[0].islower():
                    raise NameError(f"Field {field_name} is not public (no such field)")
                if field_name in instance_val["fields"]:
                    return instance_val["fields"][field_name]
                else:
                    raise NameError(f"Field '{field_name}' not found in instance")

        # 先尝试从实例字段中获取
        if instance_name in self.environment.get("instances", {}):
            instance_dict = self.environment["instances"][instance_name]
            if field_name in instance_dict["fields"]:
                # 判断属性是否是public
                if field_name[0].islower():
                    raise NameError(f"Field {field_name} is not public (no such field)")
                return instance_dict["fields"][field_name]

            # 如果实例字段中没有，尝试从对应类的静态字段中获取
            parent_class_name = instance_dict.get("parent_name")
            if parent_class_name and parent_class_name in self.environment.get("objects", {}):
                class_def = self.environment["objects"][parent_class_name]
                if field_name in class_def.get("static_fields", {}):
                    return class_def["static_fields"][field_name]

        # 都找不到，抛出原来的错误
        raise NameError(f"Field {field_name} not found in instance {instance_name}")

    def evaluate_get_member_by_this(self, node: GetMemberNodeByThis):
        """解析 this->Field 属性访问"""
        # 静态方法中禁止使用 this
        if self._static_context:
            raise RuntimeError("Cannot use 'this' inside a static method")

        instance = self.current_object
        if instance is None:
            raise RuntimeError("this->field can only be used inside an instance context")

        # 如果 current_object 是字典（实例对象），直接从中获取字段
        if isinstance(instance, dict) and "fields" in instance:
            field_name = node.member_name
            if field_name in instance["fields"]:
                return instance["fields"][field_name]
            else:
                raise NameError(f"Field '{field_name}' not found in instance")

        # 否则，复用已有的实例/静态字段访问逻辑
        temp_node = GetMemberNode(instance, node.member_name)
        return self.evaluate_get_instance_member(temp_node)

    def evaluate_set_member(self, node: SetMemberNode):
        """
        解析 instance->field = value; 或 Class->StaticField = value; 这样的赋值
        如 p->X = 10; 或 Pos->Origin = 777;
        """
        instance_name = node.instance_name
        field_name = node.member_name
        value = self.evaluate(node.value)

        # 检查属性是否是 public（首字母大写）
        if field_name[0].islower():
            raise NameError(f"Field '{field_name}' is not public. Cannot assign to private field from outside the class.")

        # 检查是否是类的静态属性赋值（如 Pos->Origin = 777）
        if instance_name in self.environment.get("objects", {}):
            class_def = self.environment["objects"][instance_name]
            if field_name in class_def.get("static_fields", {}):
                class_def["static_fields"][field_name] = value
                return value
            else:
                raise NameError(f"Static field '{field_name}' not found in class '{instance_name}'")

        # 先检查环境中的变量（值为实例字典）
        if instance_name in self.environment:
            instance_val = self.environment[instance_name]
            if isinstance(instance_val, dict) and "fields" in instance_val:
                if field_name in instance_val["fields"]:
                    instance_val["fields"][field_name] = value
                    return value
                else:
                    raise NameError(f"Field '{field_name}' not found in instance")

        # 尝试从 instances 中获取
        if instance_name in self.environment.get("instances", {}):
            instance_dict = self.environment["instances"][instance_name]
            if field_name in instance_dict["fields"]:
                instance_dict["fields"][field_name] = value
                return value
            else:
                raise NameError(f"Field '{field_name}' not found in instance '{instance_name}'")

        raise NameError(f"Instance or class '{instance_name}' not found")

    def evaluate_method_call(self, node: MethodCallNode):
        # ====================version 2============================================
        caller = node.instance_name  # 记录调用者的名字
        self.current_object = caller  # 记录当前的对象，用于this的解析

        # ====================类调用方法开始============================================
        # 在环境中找到类的定义
        if caller in self.environment["objects"]:
            # print("哦吼，调用的是一个类")
            class_name = caller
            # 找到类的定义
            class_definition = self.environment["objects"][class_name]
            # 找到方法的定义
            method_name = node.method_name
            # 判断是不是private静态方法，如果是，拒绝访问（类外部）
            if method_name[0].islower() and not self._internal_method_call:
                raise Exception(f"Method {caller}->{method_name}() is not public. Access denied.")
            
            method_candidate = class_definition["methods"][method_name]
            
            # 处理方法重载：根据参数数量选择匹配的方法
            args_pass_in = [self.evaluate(arg) for arg in node.arguments]
            named_args = getattr(node, 'named_arg_values', {})
            total_arg_count = len(args_pass_in) + len(named_args)
            
            if isinstance(method_candidate, list):
                method_dict = None
                for candidate in method_candidate:
                    # 考虑默认参数：实际参数数量应该在 [必须参数数量, 总参数数量] 范围内
                    total_params = len(candidate['args'])
                    default_count = len(candidate.get('default_values', {}))
                    required_params = total_params - default_count
                    
                    if required_params <= total_arg_count <= total_params:
                        method_dict = candidate
                        break
                if method_dict is None:
                    raise ValueError(f"No matching method '{method_name}' found for {total_arg_count} arguments")
            else:
                method_dict = method_candidate
            
            # 检查：类名只能调用静态方法，不能调用实例方法
            if not method_dict.get("is_static", False):
                raise RuntimeError(f"Cannot call instance method '{method_name}' on class '{class_name}'. Instance methods can only be called on instances.")

            # 保存旧环境
            old_env = self.environment
            # 记录旧的静态上下文
            old_static = self._static_context
            old_current_class = self.current_class  # 保存当前类名
            self._static_context = method_dict.get("is_static", False)
            self.current_class = class_name  # 设置当前类名，确保静态方法内部可以调用同类的其他静态方法
            
            # 创建新环境，包含方法参数
            self.environment = {**old_env}  # 包含全局环境
            
            # 处理默认参数：先绑定默认值
            default_values = method_dict.get('default_values', {})
            for param, default in default_values.items():
                self.environment[param] = self.evaluate(default)
            
            # 然后绑定位置参数（会覆盖默认值）
            for param, value in zip(method_dict['args'], args_pass_in):
                self.environment[param] = value
            
            # 最后绑定命名参数（会覆盖位置参数和默认值）
            if named_args:
                for param_name, value_node in named_args.items():
                    if param_name not in method_dict['args']:
                        raise TypeError(f"Method '{method_name}' got an unexpected keyword argument '{param_name}'")
                    # 检查是否通过位置参数已经赋值
                    positional_count = len(args_pass_in)
                    if param_name in method_dict['args'][:positional_count]:
                        raise TypeError(f"Multiple values for argument '{param_name}'")
                    self.environment[param_name] = self.evaluate(value_node)
            # 执行方法体
            result = None
            for statement in method_dict['body']:
                result = self.evaluate(statement)
            # 恢复旧环境
            self.environment = old_env
            self._static_context = old_static
            self.current_class = old_current_class  # 恢复当前类名
            return result
        # ====================类调用方法结束============================================

        # ====== ====================== 实例方法调用===============================
        # print("caller: ", caller)
        method_name = node.method_name
        args_pass_in = [self.evaluate(arg) for arg in node.arguments]
        named_args = getattr(node, 'named_arg_values', {})
        total_arg_count = len(args_pass_in) + len(named_args)

        try:
            # 尝试找到该对象
            # 实例对象的所有东西
            instance_dict = self.environment["instances"][caller]
            
            # 判断是不是private方法，如果是，拒绝访问（类外部调用）
            if method_name[0].islower() and not self._internal_method_call:
                raise Exception(f"Method {caller}->{method_name}() is not public. Access denied.")
            # 对象的所有方法
            method_candidate = instance_dict["methods"][method_name]
            
            # 处理方法重载：根据参数数量选择匹配的方法
            if isinstance(method_candidate, list):
                method_dict = None
                for candidate in method_candidate:
                    # 考虑默认参数：实际参数数量应该在 [必须参数数量, 总参数数量] 范围内
                    total_params = len(candidate['args'])
                    default_count = len(candidate.get('default_values', {}))
                    required_params = total_params - default_count
                    
                    if required_params <= total_arg_count <= total_params:
                        method_dict = candidate
                        break
                if method_dict is None:
                    raise ValueError(f"No matching method '{method_name}' found for {total_arg_count} arguments")
            else:
                method_dict = method_candidate
        except KeyError:
            # 找不到该对象
            raise NameError(f"Object {caller} not found.")

        # 保存旧环境
        old_env = self.environment

        # 创建新环境
        new_env = {**old_env}  # 包含全局环境
        
        # 添加实例字段
        new_env.update(instance_dict['fields'])
        
        # 处理默认参数：先绑定默认值
        default_values = method_dict.get('default_values', {})
        for param, default in default_values.items():
            new_env[param] = self.evaluate(default)
        
        # 然后绑定位置参数（会覆盖默认值）
        for param, value in zip(method_dict['args'], args_pass_in):
            new_env[param] = value
        
        # 最后绑定命名参数（会覆盖位置参数和默认值）
        if named_args:
            for param_name, value_node in named_args.items():
                if param_name not in method_dict['args']:
                    raise TypeError(f"Method '{method_name}' got an unexpected keyword argument '{param_name}'")
                # 检查是否通过位置参数已经赋值
                positional_count = len(args_pass_in)
                if param_name in method_dict['args'][:positional_count]:
                    raise TypeError(f"Multiple values for argument '{param_name}'")
                new_env[param_name] = self.evaluate(value_node)

        # 新增：将参数也添加到 instances 字典中
        if 'instances' not in new_env:
            new_env['instances'] = {}
        for arg_name, arg_value in zip(method_dict['args'], args_pass_in):
            # 判断是不是实例对象
            if isinstance(arg_value, dict) and "fields" in arg_value:
                new_env['instances'][arg_name] = arg_value
        # 记录旧的静态上下文
        old_static = self._static_context
        self._static_context = method_dict.get("is_static", False)
        self.environment = new_env
        # ===============================test============================

        # 执行方法体
        result = None
        for statement in method_dict['body']:
            result = self.evaluate(statement)
            if isinstance(statement,ReturnNode):
                return result
            if isinstance(result,dict) and 'fight_tag' in result:
                return result['value']
            for field_name in instance_dict['fields']:
                if field_name in self.environment:
                    instance_dict['fields'][field_name] = self.environment[field_name]
        # 恢复旧环境
        self.environment = old_env
        self._static_context = old_static

        return result

    def evaluate_new_object_expr(self, node: NewObjectNode):
        """
        从environment中获取类定义，就是复制属性、方法、及其init
        """
        global delay_caller

        self.current_class = node.class_name

        # 保存旧状态
        old_current_class = self.current_class
        old_current_parent = self.current_parent_class

        return_instance = {
            "fields": {},
            "methods": {},
            "init": {},
            "parent_name": node.class_name,
            "fields_annotations": {},
            "operators": {},  # 运算符重载
        }
        class_name = node.class_name

        # 先获取类定义, 也就是类的原型
        # 优先在 objects 中查找，其次在直接导入的类中查找
        original_class_definition = None
        
        if class_name in self.environment.get("objects", {}):
            original_class_definition = self.environment["objects"][class_name]
        elif class_name in self.environment:
            # 检查是否是从模块导入的类
            candidate = self.environment[class_name]
            if isinstance(candidate, dict) and 'fields' in candidate and 'methods' in candidate and 'init' in candidate:
                original_class_definition = candidate
        
        if original_class_definition is None:
            raise NameError(f"Class '{class_name}' not found.")

        #  设置父类名称（在创建新环境之前！）
        self.current_parent_class = original_class_definition.get("parent_name", "")

        # 处理fields
        for field_name in original_class_definition['fields']:
            field_value = original_class_definition['fields'][field_name]
            return_instance["fields"][field_name] = field_value

        # 处理fields_annotations
        for field_name in original_class_definition['fields_annotations']:
            field_annotation = original_class_definition['fields_annotations'][field_name]
            return_instance["fields_annotations"][field_name] = field_annotation

        # 处理 methods
        for method_name in original_class_definition['methods']:
            method_info = original_class_definition['methods'][method_name]
            
            # 处理方法重载：如果是列表，需要复制整个列表
            if isinstance(method_info, list):
                method_list = []
                for single_method in method_info:
                    method_list.append({
                        "annotations": single_method["annotations"],
                        "args": single_method['args'],
                        "body": single_method['body'],
                        "default_values": single_method['default_values'],
                        "is_static": single_method.get("is_static", False),
                    })
                return_instance["methods"][method_name] = method_list
            else:
                # 单个方法
                method_body = method_info['body']
                method_args = method_info['args']
                method_default_values = method_info['default_values']
                return_instance["methods"][method_name] = {
                    "annotations": method_info["annotations"],
                    "args": method_args,
                    "body": method_body,
                    "default_values": method_default_values,
                    "is_static": method_info.get("is_static", False),
                }

        # 处理运算符重载
        for operator_name in original_class_definition.get('operators', {}):
            operator_info = original_class_definition['operators'][operator_name]
            return_instance["operators"][operator_name] = {
                "args": operator_info['args'],
                "body": operator_info['body'],
                "default_values": operator_info.get('default_values', {}),
            }

        # 选择匹配的构造函数
        arg_len = len(node.arguments)
        matching_init = None
        if isinstance(original_class_definition['init'], list):
            for init in original_class_definition['init']:
                if len(init['args']) == arg_len:
                    matching_init = init
                    break
        else:
            matching_init = original_class_definition['init']

        # 如果没有找到匹配的构造函数，检查是否允许无参构造
        if matching_init is None:
            # 只有当字段数量为0时，才允许无参构造，否则报错
            if len(original_class_definition['fields']) == 0:
                # 创建一个默认的空构造函数
                matching_init = {'args': [], 'body': [], 'default_values': {}}
            else:
                raise ValueError(f"No matching constructor found for {arg_len} arguments")

        # 使用匹配的构造函数
        init_args = matching_init['args']
        init_body = matching_init['body']
        init_default_values = matching_init.get('default_values', {})
        return_instance["init"] = {
            "args": init_args,
            "body": init_body,
            "default_values": init_default_values
        }

        # 创建新环境，包含类的字段
        #  保存 objects 引用，供 super 使用
        self._saved_objects = self.environment["objects"]
        # 设置当前正在初始化的实例（供 super() 调用时更新字段）
        self._current_instance = return_instance

        # 记录旧环境
        # 记录旧环境
        old_env = self.environment
        new_env = {
            "constants": [],
            "objects": {},
        }

        # 将类的字段添加到新环境中
        for field_name, field_value in return_instance["fields"].items():
            new_env[field_name] = field_value

        # 记录旧环境
        old_env = self.environment
        self.environment = new_env # 切换到新环境

        # 将传进来的参数放到新环境里面
        # for i in range(len(node.arguments)):
        #     arg_name = init_args[i]
        #     arg_value = self.evaluate(node.arguments[i])
        #     self.environment[arg_name] = arg_value
        for i in range(len(node.arguments)):
            arg_name = init_args[i]
            arg_value = old_env.copy()  # 临时用旧环境来解析参数
            self.environment = old_env
            arg_value = self.evaluate(node.arguments[i])
            self.environment = new_env
            self.environment[arg_name] = arg_value

        # init里面的this->xxx()类方法
        delay_calls = []
        delay_caller = None

        # 处理init函数体
        for statement in init_body:
            if isinstance(statement, AssignmentNode) and statement.name in return_instance["fields"]:
                # 更新字段值
                value = self.evaluate(statement.value)
                self.environment[statement.name] = value
                return_instance["fields"][statement.name] = value
            elif isinstance(statement, CallClassInnerMethod):
                # 处理this->xxx()调用
                delay_calls.append(statement)
                delay_caller = node.object_name
            else:
                self.evaluate(statement)
                # super()调用后，立即同步所有字段值
                # 因为super()中的赋值已经更新了self.environment
                for field_name in return_instance["fields"]:
                    if field_name in self.environment:
                        return_instance["fields"][field_name] = self.environment[field_name]

        # 将更新后的字段值复制回return_instance
        for field_name in return_instance["fields"]:
            if field_name in self.environment:
                return_instance["fields"][field_name] = self.environment[field_name]

        # 恢复旧环境
        self.environment = old_env
        # 清除当前实例引用
        self._current_instance = None

        # 将实例对象放到environment中
        self.environment["instances"][node.object_name] = return_instance

        # 处理延迟调用
        for this_call_in_init in delay_calls:
            self.evaluate_call_class_inner_method(this_call_in_init, delay_caller)

        # 恢复之前的 current_class
        self.current_class = old_current_class
        self.current_parent_class = old_current_parent

        return return_instance

    def evaluate_class_declaration(self, node: ClassDeclarationNode):
        """
           解析类的声明
            引入类的机制和引入包的方法一致:
                environment中存放类的全部属性和方法，对于调用静态的方法，直接在environment中查找
                对于static类型的： 加入到environment中，形式是：类名.xxx
                对于非static类型的： 加入到environment中,形式是：实例.xxx
            类存储的形式：
            @@@self.environment:
            {
                'constants': [],
                'objects': {
                    'Person': {
                        'fields': {'name': 'Alice', 'Age': 25},
                        'methods': {
                            'hi': {'args': [], 'body': [], 'default_values': {}},
                            'SayHello': {'args': [], 'body': [FunctionCallNode(name=log, args=[NumberNode(value=1)], named_arg_values={})], 'default_values': {}}},
                        'init': {'args': [], 'body': [FunctionCallNode(name=log, args=[StringNode(value=init)], named_arg_values={})], 'default_values': {}}}}}
                    }
                }
            }

        """
        # print("当前的nodexxx: ", node)
        class_name = node.classname

        # class_dict表示当前解析的类
        class_dict = {
            'fields': {},
            'methods': {},
            'init': None,
            "static_fields": {},
            "static_methods": {},  # 静态方法
            "fields_annotations": {},
            "parent_name": node.parent_name, # 父类名称
            "operators": {}  # 运算符重载
        }

        # print(" \n node---------------------> ", node,"\n")

        # ====================static 类型属性============================================
        for field_name in node.static_fields:
            # field_name = field.name
            field_value = self.evaluate(node.static_fields[field_name])
            # 这里的field_name是类名.field_name
            class_dict['static_fields'][field_name] = field_value
        # ====================static 类型属性============================================

        # ====================static 方法============================================
        for method_name in node.methods:
            # print("method_name: ", method_name)
            method_node_or_list = node.methods[method_name]
            
            # 处理方法重载：方法可能是单个或列表
            if isinstance(method_node_or_list, list):
                # 多个重载方法，处理静态方法
                for method_node in method_node_or_list:
                    if getattr(method_node, "is_static", False) == True:
                        # 静态方法重载也需要存储为列表
                        if method_name not in class_dict['static_methods']:
                            class_dict['static_methods'][method_name] = []
                        class_dict['static_methods'][method_name].append({
                            'args': method_node.args,
                            'body': method_node.body,
                            "default_values": method_node.default_values
                        })
            else:
                # 单个方法
                method_node = method_node_or_list
                if getattr(method_node, "is_static", False) == True:
                    class_dict['static_methods'][method_name] = {
                        'args': method_node.args,
                        'body': method_node.body,
                        "default_values": method_node.default_values
                    }
        # ====================static 方法============================================

        # ===============处理字段的注解===========================
        for field_name in node.fields_annotations:
            annot = node.fields_annotations[
                field_name]  # 格式:  {'permission': StringNode(value=public), 'returnType': StringNode(value=string)}
            annot_return = {}  # 要返回的annotation
            for key in annot:
                annot_return[key] = self.evaluate(annot[key])
            class_dict['fields_annotations'][field_name] = annot_return
            # print("class_dict['fields_annotations'] : ", class_dict['fields_annotations'])

        # ===============处理字段的注解===========================

        # ==========================处理字段======================
        # field就是key
        for field_name in node.fields:
            # field_name = field.name
            field_value = self.evaluate(node.fields[field_name])
            class_dict['fields'][field_name] = field_value
        # fields的形式:  {'name': 'Alice', 'Age': 25}
        # print("fields: ", class_dict['fields'])

        # 处理方法
        for method_name in node.methods:
            method_node_or_list = node.methods[method_name]
            
            # 处理方法重载：Parser已经把重载方法转换为列表
            if isinstance(method_node_or_list, list):
                # 多个重载方法
                method_list = []
                for method_node in method_node_or_list:
                    method_list.append({
                        "annotations": method_node.annotations,
                        'args': method_node.args,
                        'body': method_node.body,
                        "default_values": method_node.default_values,
                        "is_static": getattr(method_node, "is_static", False),
                    })
                class_dict['methods'][method_name] = method_list
            else:
                # 单个方法
                method_node = method_node_or_list
                class_dict['methods'][method_name] = {
                    "annotations": method_node.annotations,
                    'args': method_node.args,
                    'body': method_node.body,
                    "default_values": method_node.default_values,
                    "is_static": getattr(method_node, "is_static", False),
                }
        # print("class_dict(methods): ", class_dict['methods'])

        # ================ 处理运算符重载=================================
        for operator_name in node.operators:
            operator_node = node.operators[operator_name]
            class_dict['operators'][operator_name] = {
                'args': operator_node.args,
                'body': operator_node.body,
                "default_values": operator_node.default_values,
            }
        # print("operators: ", class_dict['operators'])

        # ================ 处理初始化函数=================================
        # print("node.init: ", node.init)
        if isinstance(node.init, list):
            # 处理构造函数重载或空列表
            if len(node.init) == 0:
                # 没有定义任何构造函数
                class_dict['init'] = None
            elif len(node.init) == 1:
                # 只有一个构造函数
                class_dict['init'] = {
                    'args': node.init[0].args,
                    'body': node.init[0].body,
                    "default_values": node.init[0].default_values,
                }
            else:
                # 多个构造函数（重载）
                inits = []
                for init in node.init:
                    inits.append({
                        'args': init.args,
                        'body': init.body,
                        "default_values": init.default_values,
                    })
                class_dict['init'] = inits
        elif node.init is None:
            # 没有定义init
            class_dict['init'] = None
        else:
            # 只有一个初始化函数
            class_dict['init'] = {
                'args': node.init.args,
                'body': node.init.body,
                "default_values": node.init.default_values,
            }

        # print("init: ", class_dict['init'])
        # 将类定义存储在环境中
        self.environment["objects"][class_name] = class_dict

        # print("class_dict: ", self.environment["objects"][class_name])

        # ==============extends========测试=========================================
        # 有一个问题, 初始类问题,
        # class_dict: {
        #       'fields': {'brand': 'Bulldog'},
        #       'methods': {'Bark': {'args': [], 'body': [
        #                 FunctionCallNode(name=log, args=[StringNode(value=dog is barking /)], named_arg_values={})],
        #                                                                   'default_values': {}}},
        #       'init': {'args': [], 'body': [FunctionCallNode(name=log, args=[StringNode(value=Dog init)],
        #                       named_arg_values = {})], 'default_values': {}},
        #       'static_fields': {}, 'static_methods': {}}
        def ifSubclassHasAttribute(subclass_name, attr):
            subclass_fields = self.environment["objects"][subclass_name]["fields"]
            for f in subclass_fields:
                if f == attr:
                    return True
            return False

        def ifSubclassHasMethod(subclass_name, check_method_name):
            subclass_methods_dict = self.environment["objects"][subclass_name]["methods"]
            for method in subclass_methods_dict:
                if method == check_method_name:
                    return True
            return False

        # ===========================处理继承===========================================
        if node.parent_name != "":
            extended_fields = {}
            extended_methods = {}
            # 处理父类的fields
            for parent_field_name in self.environment["objects"][node.parent_name]["fields"]:
                # 继承public类型的属性（如果子类没有同名的属性）
                if parent_field_name[0].isupper() and not ifSubclassHasAttribute(node.classname, parent_field_name):
                    extended_fields[parent_field_name] = self.environment["objects"][node.parent_name]["fields"][
                        parent_field_name]
            # 处理父类的methods
            for parent_method_name in self.environment["objects"][node.parent_name]["methods"]:
                # 继承public类型的属性
                if parent_method_name[0].isupper() and not ifSubclassHasMethod(node.classname, parent_method_name):
                    extended_methods[parent_method_name] = self.environment["objects"][node.parent_name]["methods"][
                        parent_method_name]

            # ============关键一步==============================
            # 将方法和属性合并到class_dict中
            class_dict['fields'].update(extended_fields)
            class_dict['methods'].update(extended_methods)
            # print("class_dict(new): ", class_dict)
            # print("class_dict(fields): ", class_dict['fields'])
            # print("class_dict(methods): ", class_dict['methods'])
            # print("\n继承后的样子：\n")

            # for field_name in class_dict['fields']:
            # print("field_name: ", field_name)
            # for method_name in class_dict['methods']:
            #     print("method_name: ", method_name)
            # print("class_name: ", class_name)
            # ==============extends=================================================

            # 将类定义存储在环境中
            self.environment["objects"][class_name] = class_dict

        # ========================处理接口实现问题===============================
        # {'接口名称': {"methods": [方法列表], "constants": {常量字典}}}  => {接口名称：[方法列表]}
        # 处理方法: 判断类中有没有接口声明的方法，如果没有，报错!
        # node.interfaces表达式的是类自己要implements的接口列表
        # print("mynode: ", node.interfaces)i
        # print("环境: ", self.environment)
        
        # ====================多接口方法冲突检查===============================
        # 先检查多个接口之间是否有同名方法冲突
        if len(node.interfaces) > 1:
            interface_methods_map = {}  # {方法名: [接口名列表]}
            
            for interface_name in node.interfaces:
                if interface_name not in self.environment["interfaces"]:
                    raise ValueError(f"Interface '{interface_name}' is not defined.")
                interface_def = self.environment["interfaces"][interface_name]
                
                # 检查每个方法
                for method_name in interface_def["methods"]:
                    if method_name not in interface_methods_map:
                        interface_methods_map[method_name] = []
                    interface_methods_map[method_name].append(interface_name)
            
            # 检查是否有方法冲突
            for method_name, interface_list in interface_methods_map.items():
                if len(interface_list) > 1:
                    raise ValueError(
                        f"Method conflict: Method '{method_name}' is declared in multiple interfaces: {', '.join(interface_list)}. "
                        f"Class '{class_name}' cannot implement conflicting interfaces."
                    )
        # ====================多接口方法冲突检查===============================
        
        # 检查类是否实现了所有接口方法
        for interface_name in node.interfaces:
            # 先获取接口定义
            if interface_name not in self.environment["interfaces"]:
                raise ValueError(f"Interface '{interface_name}' is not defined.")
            interface_def = self.environment["interfaces"][interface_name]
            # 遍历接口定义中的方法，判断类中是否有实现
            for method_name in interface_def["methods"]:
                if method_name not in class_dict['methods']:
                    raise NotImplementedError(
                        f"Class '{class_name}' does not implement method '{method_name}' declared in interface '{interface_name}'")
        # ========================处理接口实现问题===============================

    def invokefunc_server(self, func_dictx, args):
        """
            1,该函数就是用来服务 InvokeFunc方法的
            2,func_dictx是函数字典，args是实际传入的参数
              args是命名参数，比如 {a:1, b:2}
        """
        func_dict = func_dictx  # 值居然是None
        # 如果 func 是一个函数（包括 Lambda 函数）
        func_args = func_dict['args']  # 形参名称,比如 ['a', 'b']
        body_statements = func_dict['body']  # 函数体
        return_value = None  # 函数返回值

        local_scope = {}
        # 这里使用命名参数 {a:1, b:2} 这种
        for named_arg, named_arg_value in args.items():
            local_scope[named_arg] = named_arg_value
        # =======================环境================================
        # 保存当前的环境，以便函数执行完后恢复
        previous_environment = self.environment.copy()
        # 更新环境为局部作用域, 并执行函数体, 这样做，内部函数可以访问外界的变量
        self.environment.update(local_scope)

        # ==================执行方法体=============================
        return_value = None  # 默认的返回值
        for statement in body_statements:
            return_value = self.evaluate(statement)
            if isinstance(return_value, ReturnNode):
                return return_value.value  # 直接返回返回值
        # ========================恢复环境===================
        # 恢复之前的环境
        self.environment = previous_environment

        return return_value  # 确保返回函数的返回值

    def eval_by_func_dict(self, func_dictx, args):
        """
                该方法用来辅助执行嵌套函数调用
                func_dict是在environment中找到的函数字典，args是实际传入的参数
                func_dict通过名称来获取，比如:
                self.environment[func_name]
        """

        # 准备函数的参数和体
        func_dict = func_dictx  # 值居然是None
        # 如果 func 是一个函数（包括 Lambda 函数）
        func_args = func_dict['args']  # 形参名称,比如 ['a', 'b']
        body_statements = func_dict['body']  # 函数体
        return_value = None  # 函数返回值

        # ============默认参数的部分===========================
        # FunctionCallNode(
        #       name=add,
        #       args=[NumberNode(value=111111), StringNode(value=empty str)])
        # node.args:  是实际传入的参数  func_args：是形参,函数参数名称(list类型)
        local_scope = {}
        print("args: ", args)
        # node.args是实参，func_args是形参
        for arg_name, arg_value in zip(func_args, args):
            local_scope[arg_name] = self.evaluate(arg_value)

        # =======================环境================================
        # 保存当前的环境，以便函数执行完后恢复
        previous_environment = self.environment.copy()
        # 更新环境为局部作用域, 并执行函数体, 这样做，内部函数可以访问外界的变量
        self.environment.update(local_scope)

        # ==================执行方法体=============================
        return_value = None  # 默认的返回值
        for statement in body_statements:
            return_value = self.evaluate(statement)
            if isinstance(return_value, ReturnNode):
                return return_value.value  # 直接返回返回值
            # 如果在 if/elif/else 中提前返回，会带有 fight_tag 标记
            if isinstance(return_value, dict) and return_value.get("fight_tag") is True:
                # 拆包并返回真正的值
                self.environment = previous_environment
                return return_value["value"]

        # ========================恢复环境===================
        # 恢复之前的环境
        self.environment = previous_environment

        # =======================返回值=========================
        # 上面的for in 循环,如果for in 遇到return,会直接返回,这里就不会执行
        return return_value  # 确保返回函数的返回值

    def evaluate_for_in(self, node: ForInNode):
        # print("node: ",node)
        # print("variable:", node.variable)

        # 检查循环变量是否已存在，保存原值以便恢复
        had_loop_var = node.variable in self.environment
        old_loop_var_value = self.environment.get(node.variable) if had_loop_var else None

        # 获取迭代对象
        iter_obj = self.evaluate(node.iteration_obj)
        # print("iter_obj:", iter_obj)

        # 遍历每个元素
        for item in iter_obj:
            self.environment[node.variable] = item
            try:
                for statement in node.body:
                    if isinstance(statement, ReturnNode):
                        return {"fight_tag": True, "value": self.evaluate(statement.value)}
                    result = self.evaluate(statement)
                    if isinstance(result, dict) and result.get("fight_tag") is True:
                        return result
            except BreakException:
                break

        # 循环结束后，清理或恢复循环变量
        if had_loop_var:
            # 如果循环变量之前存在，恢复原值
            self.environment[node.variable] = old_loop_var_value
        else:
            # 如果循环变量是新创建的，删除它
            if node.variable in self.environment:
                del self.environment[node.variable]

    def evaluate_object_index(self, node: ObjectIndexNode):
        """
        解析对象索引访问，支持：
        1. 普通对象: obj{"key"}
        2. 模块访问: Math.pi (实际是 Math{"pi"})
        3. 接口常量访问: Config.VERSION
        """
        # ========== 获取对象 ==========
        if isinstance(node.object_name, str):
            # 直接是变量名
            # 先检查是否是接口
            if node.object_name in self.environment.get("interfaces", {}):
                # 访问接口常量
                interface_def = self.environment["interfaces"][node.object_name]
                key = self.evaluate(node.key_expr)
                if key in interface_def.get("constants", {}):
                    return interface_def["constants"][key]
                else:
                    raise NameError(f"Constant '{key}' not found in interface '{node.object_name}'")
            
            # 再检查是否是普通变量
            if node.object_name not in self.environment:
                raise NameError(f"Object '{node.object_name}' not defined")
            obj = self.environment[node.object_name]
        else:
            # 嵌套访问: list[0][1] 或 obj{"a"}{"b"}
            obj = self.evaluate(node.object_name)

        # ========== 获取键 ==========
        key = self.evaluate(node.key_expr)

        # ========== 访问成员 ==========
        if isinstance(obj, dict):
            # 模块环境访问需要遵守 exports 限制
            if obj.get("_is_module_env"):
                module_id = obj.get("__module_id__") or obj.get("__name__")
                allowed_exports = self.exports.get(module_id)
                # 兼容性兜底：如果按 module_id 没查到，再尝试用文件名（math、jj 等简单名）
                if not allowed_exports:
                    from pathlib import Path as _P
                    simple_name = None
                    file_path = obj.get("__file__")
                    if file_path:
                        try:
                            simple_name = _P(file_path).stem
                        except Exception:
                            simple_name = None
                    if simple_name:
                        allowed_exports = self.exports.get(simple_name)
                        if allowed_exports is not None:
                            module_id = simple_name

                if not allowed_exports or key not in allowed_exports:
                    raise KeyError(
                        f"Key '{key}' not exported by module '{module_id}'. (Did you forget to add it to 'exports'?)"
                    )
                # 先查找structs
                if "structs" in obj and key in obj["structs"]:
                    return obj["structs"][key]
                # 再查找enums
                if "enums" in obj and key in obj["enums"]:
                    return obj["enums"][key]
                # 再查找objects（类）
                if "objects" in obj and key in obj["objects"]:
                    return obj["objects"][key]
                if key not in obj:
                    raise KeyError(f"Key '{key}' not found in module '{module_id}'")
                return obj[key]

            # 普通对象访问
            # 再查找structs
            if "structs" in obj and key in obj["structs"]:
                return obj["structs"][key]
            # 再查找enums
            if "enums" in obj and key in obj["enums"]:
                return obj["enums"][key]
            # 再查找objects（类）
            if "objects" in obj and key in obj["objects"]:
                return obj["objects"][key]
            if key not in obj:
                # 提供更友好的错误信息
                available_keys = [k for k in obj.keys()
                                  if not k.startswith('_') and
                                  k not in ["arg_to_instance", "instances", "constants",
                                            "objects", "interfaces", "structs", "enums"]]
                raise KeyError(
                    f"Key '{key}' not found.\n"
                    f"Available keys: {available_keys}"
                )
            return obj[key]

        elif isinstance(obj, list):
            if not isinstance(key, int):
                raise TypeError(f"List indices must be integers, not {type(key).__name__}")
            if key < 0 or key >= len(obj):
                raise IndexError(f"Index {key} out of range for list of length {len(obj)}")
            return obj[key]

        else:
            raise TypeError(
                f"Object of type '{type(obj).__name__}' does not support indexing"
            )

    def evaluate_multi_list_index(self, node: MultiListIndexNode):
        # =========================版本2==============================
        # isinstance 会检查 node.list_name 是否是这个元组中任何一个类型的实例。
        if isinstance(node.list_name, (ListIndexNode, ObjectIndexNode, MultiListIndexNode)):
            current_result = self.evaluate(node.list_name)
        else:
            if node.list_name not in self.environment:
                raise NameError(f"List '{node.list_name}' not defined")
            current_result = self.environment[node.list_name]

        for dim_indexes in node.index_list:
            start_index = self.evaluate(dim_indexes[0])
            end_index = None if dim_indexes[1] is None else self.evaluate(dim_indexes[1])

            if end_index is None:
                current_result = current_result[start_index]
            else:
                current_result = current_result[start_index:end_index + 1]

        return current_result

    def evaluate_list_index(self, node: ListIndexNode):

        # ====================版本2===============================
        # 如果 node.list_name 是 ObjectIndexNode 或 ListIndexNode，先评估它
        if isinstance(node.list_name, (ObjectIndexNode, ListIndexNode, MultiListIndexNode)):
            lst = self.evaluate(node.list_name)
        else:
            if node.list_name not in self.environment:
                raise NameError(f"List '{node.list_name}' not defined")
            lst = self.environment[node.list_name]

        start_index = self.evaluate(node.start_index)

        if node.end_index is None:
            return lst[start_index]
        else:
            end_index = self.evaluate(node.end_index)
            return lst[start_index:end_index + 1]

    def evaluate_function_declaration(self, node: FunctionDeclarationNode):
        # 处理函数声明
        """
            FunctionDeclarationNode(
                    name=myprint,
                    args=[],
                    body=[
                            FunctionCallNode(name=print, args=[StringNode(value=add function被调用...)])
                         ]
            )
        一个想法：
            如果在方法前面加上指定的模块名称，是不是就实现了定义域问题了?
            比如：@module.function() 这样就可以调用模块中的函数了。
        """
        annot = {}
        for key in node.annotations:
            annot[key] = self.evaluate(node.annotations[key])

        # 为了解决在main env声明的函数没有被放到main env的问题，
        # 注释掉了下面的代码，下面的代码好像是来处理传入箭头函数、匿名函数函数的？？

        # =========================================
        # 处理函数里面传入匿名、箭头函数的？？？

        # # 先看看是不是在环境中已经存在了
        # if node.name in self.environment:
        #     print("node.name??: ", node.name)
        #     # raise NameError(f"Function '{node.name}' already defined")
        #     # ==================================================
        #     if node.tag is None:  # 函数表示作为参数进行传递
        #         print("tag为none - 遇到的节点: ",node.name,"\n\n")
        #         # print("收到tag是none的节点: ",node)
        #         return {
        #             "annotations": annot,
        #             "args": node.args,
        #             "body": node.body,
        #             "defaults": node.default_values,  # 假设在 AST 中传递默认值
        #         }
        #     raise NameError(f"Function '{node.name}' already defined")
        # ============================================================

        # 处理annotations
        annot = {}
        for key in node.annotations:
            annot[key] = self.evaluate(node.annotations[key])

        """
        
        没修改前: 
            self.environment[node.name] = {
                "annotations": annot,
                "args": node.args,
                "body": node.body,
                "defaults": node.default_values,  # 假设在 AST 中传递默认值
            }
        
        
        """

        # ================修改后=====================
        result = {
            # "name": node.name,
            "annotations": annot,
            "args": node.args,
            "body": node.body,
            #
            "defaults": node.default_values,  # 假设在 AST 中传递默认值
            "vararg_name": node.vararg_name,  # 可变参数名

            # 闭包保存的 __closure_env__ 是「指向定义时那个环境对象的引用」
            # 词法作用域：记住定义时的环境，调用时从这里开始查找自由变量
            "__closure_env__": self.environment,
        }
        self.environment[node.name] = result
        return result

    def evaluate_if_statement(self, node:IfStatementNode):

        # 评估条件表达式
        condition_value: bool = self.evaluate(node.condition)

        # 根据条件的结果执行相应的代码块
        if condition_value:  # 如果条件为真，执行 if 代码块
            # if_body是一个列表，可能有多个语句
            for statement in node.ifBlock:
                # 如果在if语句中遇到return,可以返回值到外界
                if isinstance(statement, ReturnNode):
                    return {"fight_tag": True, "value": self.evaluate(statement.value)}  # 直接返回返回值
                    # return self.evaluate(statement.value)
                else:
                    self.evaluate(statement)
            # return
        # elif_: [{"condition": condition, "elif_statements": [statement1, statement2, statement3]}]
        for elseifDict in node.elifBlock:
            if condition_value:
                return
            condition_value: bool = self.evaluate(elseifDict['condition'])
            if condition_value:
                # return self.evaluate(elseif.body)
                elif_statements = elseifDict['elif_statements']
                for statement in elif_statements:
                    # 如果在if语句中遇到return,可以返回值到外界
                    if isinstance(statement, ReturnNode):
                        return {"fight_tag": True, "value": self.evaluate(statement.value)}
                    self.evaluate(statement)
                return
        else:
            # 如果执行了if分支，else肯定不执行
            if condition_value:
                return
            # 如果有 else 部分，执行 else 代码块
            else_statements = node.elseBlock

            for statement in else_statements:
                # 如果在if语句中遇到return,可以返回值到外界
                if isinstance(statement, ReturnNode):
                    return {"fight_tag": True, "value": self.evaluate(statement.value)}  # 直接返回返回值
                else:
                    self.evaluate(statement)

    def evaluate_object(self, node):
        obj =  {k: self.evaluate(v) for k, v in node.k_v.items()}
        return obj
    def evaluate_string(self, node):
        # 解析里面的模板字符串，替换变量值
        template_str = node.value

        def replace_expression(match):
            expr_str = match.group(1)  # 提取 ${} 中的内容

            # 方式1：先尝试简单变量查找（优化性能）
            if expr_str.isidentifier() and expr_str in self.environment:
                return str(self.environment[expr_str])

            # 方式2：作为表达式解析和求值
            try:
                # 词法分析
                from interpreter.Tokenizer import Tokenizer
                from interpreter.Parser import Parser
                tokenizer = Tokenizer(expr_str)
                tokens = tokenizer.tokenize()
                # 语法分析
                parser = Parser(tokens)
                expr_node = parser.expr()  # 只解析表达式，不是完整程序
                # 求值 (使用当前的解释器,因为拥有环境)
                result = self.evaluate(expr_node)
                return str(result)
            except Exception as e:
                # 解析失败，返回原内容
                print(f"模板表达式解析错误: {expr_str}, 错误: {e}")
                return f"${{{expr_str}}}"

            # 使用正则表达式替换所有 ${...}，内容里允许一层嵌套花括号，如 ${d{k}}、${obj{"key"}}
        result = re.sub(r'\${((?:[^{}]|\{[^{}]*\})*)}', replace_expression, template_str)
        return result

    def evaluate_number(self, node):
        # node是字符串类型,需要转换为数字类型
        try:
            if '.' in str(node.value):
                return float(node.value)
            else:
                return int(node.value)
        except ValueError:
            raise ValueError(f"Invalid number: {node.value}")

    def evaluate_variable(self, node: VariableNode):
        if node.value not in self.environment:
            raise NameError(f"Variable '{node.value}' not defined")

        value = self.environment[node.value]

        # 检查是否是宏参数（AST 节点包装器）
        if isinstance(value, dict) and value.get('_macro_ast_node'):
            # 每次访问时重新求值
            return self.evaluate(value['node'])

        # 原有逻辑
        if isinstance(value, dict):
            if value.get('type') == 'struct':
                return value['value']
        return value
    def evaluate_unary_op(self, node: UnaryOpNode):
        # 操作数 operand
        # 运算符 operator
        operand = self.evaluate(node.operand)
        if node.operator == "NOT":
            return not operand
        elif node.operator == "not":
            # 兼容旧的not操作符
            return not operand
        elif node.operator == "minus":
            return -operand  # 一元负号运算符
        else:
            raise ValueError(f"Unknown unary operator: {node.operator}")

        # 默认运算符处理（保持不变）...
    def evaluate_binary_op(self, node):
        left_val = self.evaluate(node.left)
        right_val = self.evaluate(node.right)

        # 运算符重载检查：如果左操作数是类实例，尝试调用运算符方法
        if isinstance(left_val, dict) and "fields" in left_val and "methods" in left_val:
            # 运算符映射表
            operator_map = {
                'PLUS': 'plus',
                'MINUS': 'minus',
                'MUL': 'multiply',
                'DIV': 'divide',
                'POW': 'power',
                'MOD': 'mod',
                'FLOOR_DIV': 'floordiv',
                'GT': 'gt',
                'LT': 'lt',
                'GE': 'ge',
                'LE': 'le',
                'EQ': 'eq',
                'NEQ': 'neq'
            }
            
            operator_method = operator_map.get(node.op)
            if operator_method and "operators" in left_val and operator_method in left_val["operators"]:
                # 找到了运算符重载方法，调用它
                operator_def = left_val["operators"][operator_method]
                
                # 保存旧环境
                old_env = self.environment.copy()
                old_current_object = self.current_object

                temp_instance_name = f"__temp_op_instance_{id(left_val)}__"
                self.environment["instances"][temp_instance_name] = left_val

                #  设置为字符串名称而不是字典
                self.current_object = temp_instance_name
                # 设置当前对象上下文
                # self.current_object = left_val
                
                # 将实例的字段添加到环境
                for field_name, field_value in left_val["fields"].items():
                    self.environment[field_name] = field_value
                
                # 绑定参数（右操作数）
                if isinstance(operator_def, dict):
                    args = operator_def.get('args', [])
                    if len(args) > 0:
                        self.environment[args[0]] = right_val
                    
                    # 执行运算符方法体
                    result = None
                    for statement in operator_def['body']:
                        result = self.evaluate(statement)
                        if isinstance(statement, ReturnNode):
                            break
                    # 🔥 清理临时实例
                    del self.environment["instances"][temp_instance_name]

                    # 恢复环境
                    self.environment = old_env
                    self.current_object = old_current_object
                    
                    return result

        # 默认运算符处理
        if node.op == 'PLUS':
            # 如果有一边是字符串，自动将另一边转换为字符串
            if isinstance(left_val, str) or isinstance(right_val, str):
                return str(left_val) + str(right_val)
            return left_val + right_val
        elif node.op == 'MINUS':
            return left_val - right_val
        elif node.op == 'MUL':
            return left_val * right_val
        elif node.op == 'DIV':
            return left_val / right_val
        elif node.op == 'POW':
            return left_val ** right_val
        elif node.op == "MOD":
            return left_val % right_val
        elif node.op == 'FLOOR_DIV':
            return left_val // right_val
        # 逻辑比较
        elif node.op == 'GT':  # 大于
            return left_val > right_val

        elif node.op == 'LT':  # 小于
            return left_val < right_val

        elif node.op == 'LE':  # 小于等于
            return left_val <= right_val

        elif node.op == 'GE':  # 大于等于
            return left_val >= right_val

        elif node.op == 'EQ':  # 等于
            return left_val == right_val

        elif node.op == 'NEQ':  # 不等于
            return left_val != right_val

        # 逻辑运算
        elif node.op == 'AND':
            # 对于算术比较，直接得到bool类型的值了
            # 字符串转bool
            if left_val == "True":
                left_val = True
            if left_val == "False":
                left_val = False
            if right_val == "True":
                right_val = True
            if right_val == "False":
                right_val = False
            # ================ 对逻辑运算的类型进行检查======================
            if not isinstance(left_val, bool) or not isinstance(right_val, bool):
                raise TypeError("逻辑运算只适合布尔类型!")
            return left_val and right_val

        elif node.op == 'OR':
            return left_val or right_val
        else:
            raise ValueError(f"Unknown operator: {node.op}")

    def evaluate_assignment(self, node):
        """
            赋值节点：将变量的值存入环境变量

            lambda 函数的赋值：
                AssignmentNode(
                    name=x,
                    value=LambdaFunctionCallNode(
                        args=[VariableNode(value=x), VariableNode(value=y)],
                        body=[NumberNode(value=10)]))
        """
        # 应该将函数信息保存到环境中，而不是执行他
        # 如果赋值的是一个函数声明，存储完整的函数信息
        # print("node.value: ",node.value)
        """
            node.value是FunctionDeclarationNode类型, 说明是函数声明，需要将函数信息保存到环境中
            这样在函数调用的时候自己会解析并调用！！！！
        """

        if isinstance(node.value, FunctionDeclarationNode):
            # 将函数的参数和体存入环境  node.value是FunctionDeclarationNode类型， 需要里面的参数和body_statements
            self.environment[node.name] = {
                "args": node.value.args,
                "body": node.value.body,
                # 对于let z = def(){}这种形式，需要将默认参数放到environment中, 否则在
                # 函数调用的时候找不到参数,而对let z = def(){}类和箭头函数的默认参数，需要在
                # evaluate_assignment中进行处理，对于 def main(){}这类函数，参数需要在
                # evaluate_function_declaration中处理,这就是差异！！！
                "defaults": node.value.default_values,  # 假设在 AST 中传递默认值
                # 词法作用域：匿名函数同样记住定义时的环境
                "__closure_env__": self.environment,
            }
        else:
            # =======================常量检查===============================
            if node.name in self.environment['constants']:
                raise ValueError(f"Constant '{node.name}' cannot be reassigned")
                # 如果当前节点是常量，加入到constants列表中, 用于检查是否重复赋值
            if node.is_constant:
                self.environment['constants'].append(node.name)
            # 否则，直接求值
            value = self.evaluate(node.value)

            # 赋值：let 声明写本层（允许遮蔽外层同名变量）；普通赋值沿链写（改到定义环境）
            if getattr(node, 'is_declaration', False) and isinstance(self.environment, Environment):
                self.environment.define(node.name, value)
            else:
                self.environment[node.name] = value
            return value

    def evaluate_loop(self, node):
        """
            self.condition = condition
            self.body = body
        """
        # 用于跳出while循环
        break_flag = False
        condition_value: bool = self.evaluate(node.condition)
        # 不断判断条件
        while condition_value:
            for statement in node.body:
                # print("statement: ",statement)
                # 1，可能遇到跳出循环的情况
                if isinstance(statement, BreakNode):
                    break_flag = True
                try:
                    if isinstance(statement, ReturnNode):
                        return {"fight_tag": True, "value": self.evaluate(statement.value)}
                    result = self.evaluate(statement)
                    if isinstance(result, dict) and result.get("fight_tag") is True:
                        return result
                    # 2，重新计算条件表达式
                    condition_value = self.evaluate(node.condition)
                except BreakException:
                    break_flag = True
                    break
            if break_flag:
                break

    def evaluate_macro_definition(self, node: MacroDefinitionNode):
        """
        处理宏定义: macro PI => 3.14159;
        将宏定义存储到环境中
        """
        macro_info = {
            'type': 'simple',  # 简单宏
            'params': node.params,  # 参数列表
            'body': node.body       # 宏体（表达式节点）
        }
        self.environment['macros'][node.macro_name] = macro_info
        return f"Macro '{node.macro_name}' defined"
    
    def evaluate_block_macro(self, node: BlockMacroNode):
        """
        处理代码块宏: macro repeat(n, body) { ... };
        将宏定义存储到环境中
        """
        macro_info = {
            'type': 'block',  # 代码块宏
            'params': node.params,  # 参数列表
            'body_statements': node.body_statements  # 代码块语句列表
        }
        self.environment['macros'][node.macro_name] = macro_info
        return f"Block macro '{node.macro_name}' defined"

    def expand_macro(self, macro_name, arguments=None):
        """展开宏"""
        if macro_name not in self.environment['macros']:
            raise NameError(f"Macro '{macro_name}' not defined")

        macro_info = self.environment['macros'][macro_name]

        if macro_info['type'] == 'simple':
            # 简单宏：求值参数
            if arguments is None:
                arguments = []
            evaluated_args = [self.evaluate(arg) for arg in arguments]

            if len(evaluated_args) != len(macro_info['params']):
                raise ValueError(f"Macro '{macro_name}' expects {len(macro_info['params'])} arguments")

            old_env = self.environment.copy()
            for param_name, arg_value in zip(macro_info['params'], evaluated_args):
                self.environment[param_name] = arg_value

            result = self.evaluate(macro_info['body'])
            self.environment = old_env
            return result

        elif macro_info['type'] == 'block':
            # 代码块宏：使用特殊的"可求值对象"
            if arguments is None:
                arguments = []

            if len(arguments) != len(macro_info['params']):
                raise ValueError(f"Block macro '{macro_name}' expects {len(macro_info['params'])} arguments")

            old_env = self.environment.copy()

            # 将 AST 节点包装成"可多次求值的对象"
            for param_name, arg_node in zip(macro_info['params'], arguments):
                # 创建一个特殊的包装器
                self.environment[param_name] = {
                    '_macro_ast_node': True,
                    'node': arg_node
                }
            result = None
            for statement in macro_info['body_statements']:
                result = self.evaluate(statement)
            self.environment = old_env
            return result

    def check_and_expand_macro(self, var_name):
        """
        检查变量名是否是宏，如果是则展开
        这个方法只处理无参数的宏（如 PI）
        有参数的宏会在函数调用时处理
        """
        if "macros" in self.environment:
            if var_name in self.environment['macros']:
                macro_info = self.environment['macros'][var_name]
                # 无参数的宏
                if len(macro_info['params']) == 0:
                    return self.expand_macro(var_name)
        return None
