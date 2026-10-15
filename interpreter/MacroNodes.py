from interpreter.Node import Node


# 宏定义节点
class MacroDefinitionNode(Node):
    """
    简单宏定义: macro PI => 3.14159;
    参数宏定义: macro MAX(a, b) => if(a > b) a : b;
    """
    def __init__(self, macro_name, params, body):
        self.macro_name = macro_name  # 宏名称
        self.params = params  # 参数列表，空列表表示无参数宏
        self.body = body  # 宏体（可以是表达式节点或语句列表）
    
    def __repr__(self):
        return f"MacroDefinitionNode(name={self.macro_name}, params={self.params}, body={self.body})"


# 宏调用节点
class MacroCallNode(Node):
    """
    宏调用: PI 或 MAX(10, 20)
    """
    def __init__(self, macro_name, arguments=None):
        self.macro_name = macro_name
        self.arguments = arguments if arguments is not None else []
    
    def __repr__(self):
        return f"MacroCallNode(name={self.macro_name}, arguments={self.arguments})"


# 代码块宏定义节点
class BlockMacroNode(Node):
    """
    代码块宏: 
    macro repeat(n, body) {
        for(i: 0..n) {
            body;
        }
    };
    """
    def __init__(self, macro_name, params, body_statements):
        self.macro_name = macro_name
        self.params = params  # 参数列表
        self.body_statements = body_statements  # 代码块语句列表
    
    def __repr__(self):
        return f"BlockMacroNode(name={self.macro_name}, params={self.params}, body={self.body_statements})"
