from interpreter import Node
from interpreter.Tokens import Tokens
from interpreter.ClassNodes import ClassDeclarationNode, NewObjectNode, MethodCallNode, GetMemberNode, \
    CallClassInnerMethod, ThisNode, InterfaceNode, SuperCallNode, SuperMethodCallNode, GetMemberNodeByThis, SetMemberNode
from interpreter.ModuleNodes import ImportModuleNode, PackageDeclarationNode, ExportsNode
from interpreter.MacroNodes import MacroDefinitionNode, MacroCallNode, BlockMacroNode
from interpreter.Nodes import (AssignmentNode, FunctionCallNode, BinaryOpNode,
                               NumberNode, VariableNode, IfStatementNode,
                               BooleanNode, StringNode, PyExecNode, PyFnNode, BreakNode, ReturnNode, ListNode, ObjectNode, UnaryOpNode,
                               ListIndexNode, ObjectIndexNode, ForInNode,
                               CommentNode, IfExprNode, MatchExprNode, SwitchNode, DecontructAssignNode,
                               ListDeconstructAssignNode, ForRangeNumberNode, TryCatchFinallyNode, IncrementNode,
                               DecrementNode, SetNode, CombineNode, MultiListIndexNode, StructDeclarationNode,
                               StructAssignNode, ModuleStructAssignNode, StructAccessNode, StructAccessAssignNode, EnumDeclarationNode,
                               EnumAccessNode, ModuleEnumAccessNode, ModuleClassInstantiationNode, DoWhileNode,
                               ListGeneratorNode, AbsNode, SerialCall, PlusAssignNode, MinusAssignNode,
                               MultiplyAssignNode, DivideAssignNode, ObjectAssignNode, ListAssignNode,
                               FunctionCombinationNode,
                               )
from interpreter.Nodes import LoopNode, FunctionDeclarationNode
from interpreter.Tokenizer import Tokenizer


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        # self.current_class = None  # 新增：跟踪当前正在解析的类
        # self.current_object = None

    def parse(self, from_module=None):
        return self.program()

    def parse_expr_with_macro(self):
        """
        解析表达式，支持宏调用
        """
        # 先检查是否是宏调用（标识符后跟左括号）
        if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'LPAREN':
            # 检查是否是宏
            macro_name = self.currentTokenValue()
            # 这里暂时先返回函数调用，后续可以在Evaluator中判断是否是宏
            return self.function_call_expr()
        
        # 检查是否是简单的宏调用（标识符，无参数）
        if self.currentTokenType() == 'ID':
            # 检查是否是已定义的宏
            macro_name = self.currentTokenValue()
            # 暂时返回变量节点，后续在Evaluator中处理
            return self.primary()
        
        return self.expr()

    # 解析程序
    def program(self):
        statements = []
        while self.pos < len(self.tokens):
            statements.append(self.statement())
        return statements

    """
        解析语句, 包括赋值语句、函数调用语句、
        该方法是解析的根本方法
        statement: assignment | function_call_expr | if_statement | loop_statement 
                | break_statement | return_statement | let_statement | function_declaration
                | expr END (比如x+1;)
    """
    def nextToken(self) -> tuple[str,str]:
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1]
        else:
            return ('EOF', '')
    def nextTokenVal(self)->str:
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1][1]
        else:
            return ''
    # 尝试判断是不是在对对象属性进行赋值
    def object_assign_statement(self):
        """
            d{"key"} = val;
        """
        try:
            obj_name = self.currentTokenValue()
            self.eatCurrentTokenType("ID")
            self.eatCurrentTokenType("LBRACE")  # {

            key = self.expr()  # 解析key,一般是字符串，可以是变量

            self.eatCurrentTokenType("RBRACE")
            self.eatCurrentTokenType("ASSIGN")
            val = self.expr()
            self.eatCurrentTokenType("END")
            return ObjectAssignNode(obj_name, key, val)
        except:
            return False

    def list_assign_statement(self):
        """
            d[index] = val;
        """
        try:
            lst_name = self.currentTokenValue()
            self.eatCurrentTokenType("ID")
            self.eatCurrentTokenType("LBRACKET")  # [

            index = self.expr()  # 解析index,一般是数字，可以是变量

            self.eatCurrentTokenType("RBRACKET")
            self.eatCurrentTokenType("ASSIGN")
            val = self.expr()
            self.eatCurrentTokenType("END")
            return ListAssignNode(lst_name, index, val)
        except:
            return False

    def statement(self):

        ops = ["PLUS", "MINUS", "MUL", "DIV"]
        # keyword: ['let', 'if', 'else', "elif", 'break', 'loop', 'function', 'return']
        
        # this->field = value; 这种语句
        if self.currentTokenValue() == 'this' and self.peekNextTokenType() == 'MINUS' and \
                self.pos + 2 < len(self.tokens) and self.tokens[self.pos + 2][0] == 'GT' and \
                self.pos + 3 < len(self.tokens) and self.tokens[self.pos + 3][0] == 'ID' and \
                self.pos + 4 < len(self.tokens) and self.tokens[self.pos + 4][0] == 'ASSIGN':
            return self.this_member_assign_statement()
        
        # instance->field = value; 这种语句（通过实例变量给属性赋值）
        if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'MINUS' and \
                self.pos + 2 < len(self.tokens) and self.tokens[self.pos + 2][0] == 'GT' and \
                self.pos + 3 < len(self.tokens) and self.tokens[self.pos + 3][0] == 'ID' and \
                self.pos + 4 < len(self.tokens) and self.tokens[self.pos + 4][0] == 'ASSIGN':
            return self.instance_member_assign_statement()
        
        if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'ASSIGN':
            return self.assignment()

        # id+=exp;
        elif self.currentTokenType() == 'ID' and (self.peekNextTokenType() in ops) and self.tokens[self.pos + 2][
            0] == 'ASSIGN':
            if self.peekNextTokenType() == "PLUS":
                return self.plus_assign_statement()
            if self.peekNextTokenType() == "MINUS":
                return self.minus_assign_statement()
            if self.peekNextTokenType() == "MUL":
                return self.mul_assign_statement()
            if self.peekNextTokenType() == "DIV":
                return self.div_assign_statement()

        # d{"key"}
        elif self.currentTokenType() == "ID" and self.peekNextTokenType() == "LBRACE":
            # 比如 d{"key"} = "val";
            val = self.object_assign_statement()  # val是节点或者False
            if isinstance(val, ObjectAssignNode):
                return val
        # d[index] = val
        elif self.currentTokenType() == "ID" and self.peekNextTokenType() == "LBRACKET":
            # 比如 d[index] = "val";
            val = self.list_assign_statement()  # val是节点或者False
            if isinstance(val, ListAssignNode):
                return val
        # 比如add()
        elif self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'LPAREN':
            # print("函数调用表达式")
            return self.function_call_expr()
            # 解构赋值  let {x, y} = dict对象;
        elif self.currentTokenValue() == "let" and self.peekNextTokenType() == "LBRACE":
            return self.destruct_assignment()
        # 列表解构赋值  let [x, y] = list对象;
        elif self.currentTokenValue() == "let" and self.peekNextTokenType() == "LBRACKET":
            return self.list_destruct_assignment()
        # let id = expr;
        elif self.currentTokenValue() == 'let' and self.peekNextTokenType() != "LBRACE":
            return self.let_statement()


        # 变量声明语句
        elif self.currentTokenValue() == "$":
            return self.variable_declaration()


        elif self.currentTokenValue() == 'if':
            return self.if_statement()

        elif self.currentTokenValue() == 'loop':
            return self.loop_statement()
        elif self.currentTokenValue() == 'break':
            return self.break_statement()
        # elif self.currentTokenType() == 'KEYWORD' and self.currentTokenValue() == 'function':
        elif self.currentTokenValue() == 'def':
            return self.function_declaration()

        # 注解或者函数调用
        elif self.currentTokenValue() == '@':
            # 函数注解  @annotation
            if self.tokens[self.pos + 1][1] == "annotation":
                return self.annotation()
            # else:
            # 函数调用
            return self.function_call_statement()


        elif self.currentTokenValue() == 'return':
            return self.return_statement()
        elif self.currentTokenValue() == "for":
            return self.for_in_statement()

        elif self.currentTokenValue() == 'const':
            return self.const_statement()

        # package机制解析
        elif self.currentTokenValue() == "package":
            return self.package_statement()

        # module 引入
        elif self.currentTokenValue() == "import":
            if self.peekNextTokenType() == "LT":
                return self.import_class_statement()
            return self.import_module_statement()

        # @Util.add(1,2);  @FUNCTION_CALL_PREFIX ID Dot ID ( )
        elif self.currentTokenType() == "FUNCTION_CALL_PREFIX" and self.peekNextTokenType() == "ID":
            if self.tokens[self.pos + 2][0] == "DOT" and self.tokens[self.pos + 3][0] == "ID":
                return self.module_method_call()

        # 类声明
        elif self.currentTokenValue() == "class":
            return self.class_declaration()
        # 添加 super 语句处理
        elif self.currentTokenValue() == "super":
            return self.super_statement()
        # super{}
        # elif self.currentTokenValue() == "super":
        #     print("super")
        #     return self.super_statement()

        # 解析实例调用方法的表达式 比如 p->show();
        elif self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'MINUS' and self.tokens[self.pos + 2][
            0] == 'GT' and self.tokens[self.pos + 3][0] == "ID" and self.tokens[self.pos + 4][0] == "LPAREN":
            return self.method_call()

        # 结构体属性赋值  p::x = value;
        elif self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'COLON' and \
                self.pos + 2 < len(self.tokens) and self.tokens[self.pos + 2][0] == 'COLON' and \
                self.pos + 3 < len(self.tokens) and self.tokens[self.pos + 3][0] == 'ID' and \
                self.pos + 4 < len(self.tokens) and self.tokens[self.pos + 4][0] == 'ASSIGN':
            return self.struct_access_assign_statement()

        # 解析注释
        elif self.currentTokenType() == "COMMENT":
            return self.parseComment()

        # switch statement
        elif self.currentTokenValue() == "switch":
            return self.switch_statement()

        # 接口
        elif self.currentTokenValue() == "interface":
            return self.interface_statement()
        # try catch finally
        elif self.currentTokenValue() == "try":
            return self.try_catch_finally_statement()

        elif self.currentTokenType() == "ID" and self.tokens[self.pos + 1][1] == "+" and self.tokens[self.pos + 2][
            1] == "+":
            # id++;
            return self.increment_statement()
        elif self.currentTokenType() == "ID" and self.tokens[self.pos + 1][1] == "-" and self.tokens[self.pos + 2][
            1] == "-":
            # id--;
            return self.decrement_statement()

        elif self.currentTokenValue() == "struct":
            return self.struct_statement()

        # enum Color{} 这样的声明语句
        elif self.currentTokenValue() == "enum" and self.peekNextTokenType() == "ID":
            return self.enum_statement()
        # do while statement
        elif self.currentTokenValue() == "do":
            return self.do_while_statement()
        # exports
        elif self.currentTokenValue() == "exports":
            return self.exports_statement()
        # 宏定义  macro PI => 3.14159;
        elif self.currentTokenValue() == "macro":
            return self.macro_definition()
        else:
            node = self.expr()
            if self.currentTokenType() == 'END':
                self.eatCurrentTokenType('END')
            return node

    def exports_statement(self):
        """
            exports = ["e","pi"] 这样
        """
        self.eatCurrentTokenType(Tokens.KEYWORD)  # exports
        self.eatCurrentTokenType(Tokens.ASSIGN)  # =
        self.eatCurrentTokenType(Tokens.LBRACKET)  # [

        exportNames = []

        # 处理空列表的情况 exports = []
        if self.currentTokenType() == Tokens.RBRACKET:
            self.eatCurrentTokenType(Tokens.RBRACKET)
            return ExportsNode([])

        while True:
            # 1. 解析字符串
            if self.currentTokenType() == Tokens.STRING:
                exportNames.append(self.currentTokenValue())
                self.eatCurrentTokenType(Tokens.STRING)

            # 2. 消费完字符串后，立即检查当前是否为逗号
            if self.currentTokenType() == Tokens.COMMA:
                self.eatCurrentTokenType(Tokens.COMMA)
                # 继续循环解析下一个字符串

            # 3. 或者检查是否为右中括号，如果是则结束
            elif self.currentTokenType() == Tokens.RBRACKET:
                self.eatCurrentTokenType(Tokens.RBRACKET)
                break  # 跳出循环

            else:
                # 遇到非逗号也非右括号的情况，为了防止死循环，必须抛出异常或强制跳出
                raise SyntaxError(f"Expected COMMA or RBRACKET in exports, got {self.currentTokenType()}")

        return ExportsNode(exportNames)

    def div_assign_statement(self):
        # x/=1;
        var_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("DIV")  # /
        self.eatCurrentTokenType("ASSIGN")  # =
        div_val = self.expr()
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return DivideAssignNode(var_name, div_val)

    def mul_assign_statement(self):
        # x*=1;
        var_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("MUL")  # *
        self.eatCurrentTokenType("ASSIGN")  # =
        mul_val = self.expr()
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return MultiplyAssignNode(var_name, mul_val)

    def minus_assign_statement(self):
        """
            id-=exp;
        """
        var_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("MINUS")  # -
        self.eatCurrentTokenType("ASSIGN")  # =
        dec_val = self.expr()
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return MinusAssignNode(var_name, dec_val)

    def plus_assign_statement(self):
        """
            id+=exp;
        """
        var_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("PLUS")  # +
        self.eatCurrentTokenType("ASSIGN")  # =
        inc_val = self.expr()
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return PlusAssignNode(var_name, inc_val)

    def variable_declaration(self):
        """
            $x = expr;
        """
        self.eatCurrentTokenType("DOLLAR")  # $
        var_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")

        self.eatCurrentTokenType("ASSIGN")  # =

        var_value = self.expr()
        # print("var_value", var_value)

        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return AssignmentNode(var_name, var_value)

    def this_member_assign_statement(self):
        """
            this->field = value;
            在 init 方法中使用，用于给实例字段赋值
        """
        self.eatCurrentTokenType("KEYWORD")  # this
        self.eatCurrentTokenType("MINUS")    # -
        self.eatCurrentTokenType("GT")       # >
        field_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")       # field name
        self.eatCurrentTokenType("ASSIGN")   # =
        value = self.expr()                   # 赋的值
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        # 返回一个赋值节点，字段名就是 field_name
        return AssignmentNode(field_name, value)

    def instance_member_assign_statement(self):
        """
            instance->field = value;
            通过实例变量给属性赋值，如 p->X = 10;
        """
        instance_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")       # instance name
        self.eatCurrentTokenType("MINUS")    # -
        self.eatCurrentTokenType("GT")       # >
        field_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")       # field name
        self.eatCurrentTokenType("ASSIGN")   # =
        value = self.expr()                   # 赋的值
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return SetMemberNode(instance_name, field_name, value)

    def do_while_statement(self):
        """
            do{


            }while()

        """
        self.eatCurrentTokenType("KEYWORD")  # do
        self.eatCurrentTokenType("LBRACE")  # {
        # do while 代码块
        do_blocks = []
        while self.currentTokenType() != "RBRACE":
            stmt = self.statement()
            do_blocks.append(stmt)
        self.eatCurrentTokenType("RBRACE")  # }
        self.eatCurrentTokenType("KEYWORD")  # while
        self.eatCurrentTokenType("LPAREN")  # (
        cond = self.expr()
        self.eatCurrentTokenType("RPAREN")
        # do{}while(cond); 允许结尾带分号，和其他语句保持一致
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")
        return DoWhileNode(cond, do_blocks)

    def annotation(self):
        # 解析注解
        self.eatCurrentTokenType("FUNCTION_CALL_PREFIX")  # @
        self.eatCurrentTokenType("KEYWORD")  # annotation
        self.eatCurrentTokenType("LPAREN")  # (
        properties = {}
        while self.currentTokenType() != "RPAREN":

            # annotation(id = 1, name = "xxx")
            property_name = self.currentTokenValue()
            self.eatCurrentTokenType("ID")
            self.eatCurrentTokenType("ASSIGN")  # =
            property_value = self.expr()
            if self.currentTokenType() == "COMMA":
                self.eatCurrentTokenType("COMMA")
            # 解析注解的属性
            properties.update({property_name: property_value})
        self.eatCurrentTokenType("RPAREN")  # )
        fnc_dec_node: FunctionDeclarationNode = self.function_declaration()
        fnc_dec_node.annotations = properties
        return fnc_dec_node

    def parse_annotation(self):
        # 解析注解
        self.eatCurrentTokenType("FUNCTION_CALL_PREFIX")  # @
        self.eatCurrentTokenType("KEYWORD")  # annotation
        self.eatCurrentTokenType("LPAREN")  # (
        properties = {}
        while self.currentTokenType() != "RPAREN":

            # annotation(id = 1, name = "xxx")
            property_name = self.currentTokenValue()
            self.eatCurrentTokenType("ID")
            self.eatCurrentTokenType("ASSIGN")  # =
            property_value = self.expr()
            if self.currentTokenType() == "COMMA":
                self.eatCurrentTokenType("COMMA")
            # 解析注解的属性
            properties.update({property_name: property_value})
        self.eatCurrentTokenType("RPAREN")  # )

        return properties

    def enum_access_expr(self):
        # let x= enum::Color::RED;
        self.eatCurrentTokenType("KEYWORD")  # enum
        self.eatCurrentTokenType("COLON")  # :
        self.eatCurrentTokenType("COLON")  # :
        # 比如Color
        enum_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        # 解析enum的属性 ::RED
        self.eatCurrentTokenType("COLON")  # :
        self.eatCurrentTokenType("COLON")  # :
        # 比如RED
        enum_property = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        return EnumAccessNode(enum_name, enum_property)

    def enum_statement(self):
        # 解析enum
        self.eatCurrentTokenType("KEYWORD")  # enum
        enum_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("LBRACE")  # {
        # 解析属性
        properties = []
        while self.currentTokenType() != "RBRACE":
            property_name = self.currentTokenValue()
            self.eatCurrentTokenType("ID")
            properties.append(property_name)
            if self.currentTokenType() == "COMMA":
                self.eatCurrentTokenType("COMMA")
        self.eatCurrentTokenType("RBRACE")  # }
        return EnumDeclarationNode(enum_name, properties)

    def struct_statement(self):
        """
                struct 名称 {
                    属性名1, 属性名2;
                }
                每个属性的init_value = -1


        :return:
        """
        # 解析struct
        self.eatCurrentTokenType("KEYWORD")  # struct
        struct_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("LBRACE")  # {
        # 解析属性
        properties = {}
        while self.currentTokenType() != "RBRACE":
            property_name = self.currentTokenValue()
            self.eatCurrentTokenType("ID")
            properties.update({property_name: -1})
            if self.currentTokenType() == "COMMA":
                self.eatCurrentTokenType("COMMA")

        self.eatCurrentTokenType("RBRACE")  # }
        return StructDeclarationNode(struct_name, properties)

    def decrement_statement(self):
        # id--;
        id_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("MINUS")
        self.eatCurrentTokenType("MINUS")
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return DecrementNode(id_name)

    def try_catch_finally_statement(self):
        # try catch finally 机制

        self.eatCurrentTokenType("KEYWORD")  # try
        self.eatCurrentTokenType("LBRACE")  # {
        # try的代码块
        try_blocks = []
        while self.currentTokenType() != "RBRACE":
            stmt = self.statement()
            try_blocks.append(stmt)
        self.eatCurrentTokenType("RBRACE")  # }
        print("try_blocks", try_blocks)

        # catch 和finally blocks
        catch_block = []
        while self.currentTokenValue() == "catch":
            self.eatCurrentTokenType("KEYWORD")  # catch
            self.eatCurrentTokenType("LPAREN")  # (

            # 解析异常类型
            catch_type = self.currentTokenValue()
            self.eatCurrentTokenType("ID")
            self.eatCurrentTokenType("RPAREN")  # )
            self.eatCurrentTokenType("LBRACE")  # {
            blocks = []
            while self.currentTokenType() != "RBRACE":
                stmt_catch = self.statement()
                # catch_block.append(stmt_catch)
                blocks.append(stmt_catch)
            self.eatCurrentTokenType("RBRACE")  # }  catch的后大括号
            # {错误类型: block_statements}
            catch_block.append({catch_type: blocks})

        # finally 代码解析
        finally_block = []
        if self.currentTokenValue() == "finally":
            self.eatCurrentTokenType("KEYWORD")  # finally
            self.eatCurrentTokenType("LBRACE")  # {
            finally_stmt = self.statement()
            finally_block.append(finally_stmt)
            self.eatCurrentTokenType("RBRACE")  # }
        return TryCatchFinallyNode(try_blocks, catch_block, finally_block)

    def increment_statement(self):
        # id++;
        id_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("PLUS")
        self.eatCurrentTokenType("PLUS")
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return IncrementNode(id_name)

    def interface_statement(self):
        # 解析interface

        """
            interface 名称 {
                方法名(参数);
                常量名 = 常量值;
            }

        :return:
        """
        self.eatCurrentTokenType("KEYWORD")  # interface
        interface_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")
        self.eatCurrentTokenType("LBRACE")  # {

        # 解析方法和常量
        methods = []
        constants = {}  # {常量名: 常量值Node}
        
        while self.currentTokenValue() != "}":
            # 解析方法或常量
            member_name = self.currentTokenValue()
            self.eatCurrentTokenType("ID")
            
            # 如果是方法：后面跟 (
            if self.currentTokenType() == "LPAREN":
                methods.append(member_name)
                self.eatCurrentTokenType("LPAREN")  # (
                args = []
                while self.currentTokenType() != 'RPAREN':
                    args.append(self.currentTokenValue())
                    self.eatCurrentTokenType("ID")
                    if self.currentTokenType() == 'COMMA':
                        self.eatCurrentTokenType("COMMA")
                self.eatCurrentTokenType("RPAREN")  # )
                if self.currentTokenType() == "END":
                    self.eatCurrentTokenType("END")  # ;
            
            # 如果是常量：后面跟 =
            elif self.currentTokenType() == "ASSIGN":
                self.eatCurrentTokenType("ASSIGN")  # =
                constant_value = self.expr()  # 解析常量值表达式
                constants[member_name] = constant_value
                if self.currentTokenType() == "END":
                    self.eatCurrentTokenType("END")  # ;
            else:
                raise SyntaxError(f"Expected '(' or '=' after '{member_name}' in interface '{interface_name}'")
                
        self.eatCurrentTokenType("RBRACE")  # }
        return InterfaceNode(interface_name, methods, constants)

    def list_destruct_assignment(self):
        # let [a,_,b] = [1,2,3];  list可以说变量或者list
        self.eatCurrentTokenType("KEYWORD")  # let
        self.eatCurrentTokenType("LBRACKET")  # [
        variables = {}  # {varname: index}
        index_count = 0  # 记录当前id的下标
        while self.currentTokenType() == "ID" or self.currentTokenType() == "UNDERLINE":
            if self.currentTokenType() == "UNDERLINE":
                self.eatCurrentTokenType("UNDERLINE")  # _
            elif self.currentTokenType() == "ID":
                # 使用列表存放变量名
                variables[self.currentTokenValue()] = index_count
                self.eatCurrentTokenType("ID")
            if self.currentTokenType() == "COMMA":
                self.eatCurrentTokenType("COMMA")
            index_count += 1  # 下标自增
        self.eatCurrentTokenType("RBRACKET")  # ]
        self.eatCurrentTokenType("ASSIGN")  # =
        value = self.expr()  # 解析赋值表达式
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        # print(ListDeconstructAssignNode(variables, value))
        return ListDeconstructAssignNode(variables, value)

    def destruct_assignment(self):
        # let {a,b} = dict;  dict可以说变量或者dict
        self.eatCurrentTokenType("KEYWORD")  # let
        self.eatCurrentTokenType("LBRACE")  # {
        variables = []
        while self.currentTokenType() == "ID":
            # 使用列表存放变量名
            variables.append(self.currentTokenValue())
            self.eatCurrentTokenType("ID")
            if self.currentTokenType() == "COMMA":
                self.eatCurrentTokenType("COMMA")
        self.eatCurrentTokenType("RBRACE")  # }
        self.eatCurrentTokenType("ASSIGN")  # =
        value = self.expr()  # 解析赋值表达式
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType("END")  # ;
        return DecontructAssignNode(variables, value)

    def switch_statement(self):
        self.eatCurrentTokenType("KEYWORD")  # switch
        self.eatCurrentTokenType("LPAREN")  # (
        expr = self.expr()  # 要比较的表达式
        self.eatCurrentTokenType("RPAREN")  # )
        self.eatCurrentTokenType("LBRACE")  # {
        cases = {}  # {case: statements}
        while self.currentTokenValue() != "}":

            # 解析case
            if self.currentTokenValue() == "case":
                self.eatCurrentTokenType("KEYWORD")  # case
                self.eatCurrentTokenType("LPAREN")  # :
                case_expr = self.expr()
                self.eatCurrentTokenType("RPAREN")  # )
                self.eatCurrentTokenType("LBRACE")  # {
                statements = []  # 语句列表
                while self.currentTokenValue() != "}":  # case的 }
                    statements.append(self.statement())  # 如果语句遇到},也会自己解析，所以最后case的}还在
                # cases.append((case_expr, {case_expr: statements}))
                cases[case_expr] = statements
                self.eatCurrentTokenType("RBRACE")  # }

            # 解析default
            elif self.currentTokenValue() == "default":
                self.eatCurrentTokenType("KEYWORD")  # default
                self.eatCurrentTokenType("LBRACE")  # {
                statements = []  # 语句列表
                while self.currentTokenValue() != "}":  # case的 }
                    statements.append(self.statement())  # 如果语句遇到},也会自己解析，所以最后case的}还在
                # cases.append((case_expr, {case_expr: statements}))
                cases[StringNode("default")] = statements
                self.eatCurrentTokenType("RBRACE")  # }
        self.eatCurrentTokenType("RBRACE")  # }
        return SwitchNode(expr, cases)

    def evaluate_call_class_inner_method(self):
        """
            使用this->xxx()或 this->Field 解析调用

            - this->Method(args)  => CallClassInnerMethod
            - this->Field         => GetMemberNodeByThis
        """
        # 解析实例内部的方法/属性访问   this->xxx()
        # 进来的时候遇到的第一个token是 this
        self.eatCurrentTokenType('KEYWORD')  # this
        self.eatCurrentTokenType('MINUS')    # -
        self.eatCurrentTokenType('GT')       # >

        member_name = self.currentTokenValue()  # 方法名或字段名
        self.eatCurrentTokenType('ID')

        # 方法调用: this->Method(...)
        if self.currentTokenType() == 'LPAREN':
            self.eatCurrentTokenType('LPAREN')  # (
            args = []
            while self.currentTokenType() != 'RPAREN':
                args.append(self.expr())
                if self.currentTokenType() == 'COMMA':
                    self.eatCurrentTokenType('COMMA')
            self.eatCurrentTokenType('RPAREN')  # )
            # 注意: 不在这里吃 ';'，由外层 statement() 统一处理
            return CallClassInnerMethod(member_name, args)

        # 属性访问: this->Field
        return GetMemberNodeByThis(member_name)

    def call_class_inner_method(self):
        # this->xxx();
        if self.currentTokenValue() == "this" and self.peekNextTokenType() == "MINUS" and \
                self.tokens[self.pos + 2][1] == ">":
            return True
        return False

    def method_call(self):
        """
            解析实例调用方法的表达式 比如 p->show();

        """
        instance_name = self.currentTokenValue()  # 实例名
        self.eatCurrentTokenType('ID')
        self.eatCurrentTokenType('MINUS')
        self.eatCurrentTokenType('GT')
        method_name = self.currentTokenValue()  # 方法名
        self.eatCurrentTokenType('ID')
        self.eatCurrentTokenType('LPAREN')  # (
        
        # 解析参数，支持位置参数 + 命名参数
        args = []
        named_arg_values = {}
        seen_named = False
        
        while self.currentTokenType() != 'RPAREN':
            # 命名参数: 形如 x = expr
            if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'ASSIGN':
                seen_named = True
                param_name = self.currentTokenValue()
                self.eatCurrentTokenType('ID')
                self.eatCurrentTokenType('ASSIGN')
                named_arg_values[param_name] = self.expr()
            else:
                # 一旦出现过命名参数，后面就不允许再出现位置参数
                if seen_named:
                    raise SyntaxError("Positional arguments cannot follow named arguments")
                args.append(self.expr())
            
            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')
        
        self.eatCurrentTokenType('RPAREN')  # )

        # ; 是可选的
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType('END')  # ;

        # ===========================连续调用============================
        methods = []
        methods.append(MethodCallNode(instance_name, method_name, args, named_arg_values=named_arg_values))
        # 实例进行连续调用
        while self.currentTokenType() == "MINUS" and self.peekNextTokenType() == "GT":
            method_node = self.single_method_call(instance_name)
            methods.append(method_node)

        return MethodCallNode(instance_name, method_name, args, named_arg_values=named_arg_values)

    def single_method_call(self, instance_name=None):
        """
            解析实例调用方法的表达式 比如 p->show();

        """
        # instance_name = self.currentTokenValue()  # 实例名
        # if self.currentTokenType() == "ID":
        # self.eatCurrentTokenType('ID')
        self.eatCurrentTokenType('MINUS')
        self.eatCurrentTokenType('GT')
        method_name = self.currentTokenValue()  # 方法名
        self.eatCurrentTokenType('ID')
        self.eatCurrentTokenType('LPAREN')  # (
        args = []
        while self.currentTokenType() != 'RPAREN':
            args.append(self.expr())
            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')
        self.eatCurrentTokenType('RPAREN')  # )

        # ; 是可选的
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType('END')  # ;

        return MethodCallNode(instance_name, method_name, args)

    # 解析类的声明  class 类名 { fields{} init{} methods{} }
    def class_declaration(self):
        # 进来的时候是class关键字
        global init_method, fields_annotations, init_methods
        self.eatCurrentTokenType("KEYWORD")  # class
        class_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 类名

        parent_name = ""
        # =======================extends=============================
        # extends 继承
        if self.currentTokenValue() == "extends":
            self.eatCurrentTokenType("KEYWORD")  # extends
            parent_name = self.currentTokenValue()
            self.eatCurrentTokenType('ID')  # 父类名
        # ====================================================

        # ===============解析接口实现=====================
        interfaces = []  # 接口列表
        if self.currentTokenValue() == "implements":
            self.eatCurrentTokenType("KEYWORD")  # implements
            while self.currentTokenType() == "ID":
                interface_name = self.currentTokenValue()
                self.eatCurrentTokenType('ID')  # 接口名
                print("implements: ", interface_name)
                interfaces.append(interface_name)
                if self.currentTokenType() == "COMMA":
                    self.eatCurrentTokenType("COMMA")

        # ===============解析接口实现=====================
        self.eatCurrentTokenType("LBRACE")  # {

        # =============static解析==========
        static_fields = {}  # 静态属性
        static_methods = {}  # 静态方法
        # =============static解析==========

        # 属性和方法
        fields = {}
        methods = {}
        operators = {}  # 运算符重载
        init_methods = []
        fields_annotations = {}  # 字段注解
        while self.currentTokenValue() != "}":
            # 非法的定义
            if self.currentTokenValue() in ['def']:
                raise SyntaxError(f"cannot declare a function inside a non-methods section")
            # 解析属性
            if self.currentTokenValue() == "fields":
                self.eatCurrentTokenType("KEYWORD")  # fields
                self.eatCurrentTokenType("LBRACE")  # {

                if_fields_parsed = False  # 是否解析过fields

                # 检查是否是合法的字段开头：ID、static关键字、@注解
                def is_field_start():
                    return (self.currentTokenType() == 'ID' or 
                            self.currentTokenValue() == 'static' or 
                            self.currentTokenValue() == '@')
                
                while is_field_start():
                    # 属性注解
                    field_annotation = None
                    if self.currentTokenValue() == "@":
                        field_annotation = self.parse_annotation()
                        print("field_annotation: ", field_annotation)

                    # ======================static test========================
                    is_static = False
                    if self.currentTokenValue() == "static":
                        is_static = True
                        self.eatCurrentTokenType("KEYWORD")  # 消费 static

                    # ===============static test=============end==================

                    if_fields_parsed = True
                    field = self.currentTokenValue()  # 解析属性名

                    # {属性名称: 函数注解{}}
                    if field_annotation is not None:
                        fields_annotations[field] = field_annotation  # 存入字段的注解


                    # 判断static修饰的属性名是否首字母大写，如果不是，报错
                    # ===========static== test==========================
                    if is_static and field[0].islower():
                        raise Exception(
                            "static field must be capitalized.")
                    # ===========static=======end=====================

                    self.eatCurrentTokenType("ID")
                    self.eatCurrentTokenType("ASSIGN")  # =
                    value = self.expr()  # 解析属性值

                    # ===========================static test=====================
                    if is_static:
                        static_fields[field] = value
                    else:
                        fields[field] = value
                    # ===========================static test============end========

                    # 解析属性值
                    # fields[field] = value  这里需要注释回来        (old version)
                    if self.currentTokenType() == "END":
                        self.eatCurrentTokenType("END")  # ;
                if if_fields_parsed:
                    self.eatCurrentTokenType("RBRACE")  # }

            # 解析方法
            is_methods_parsed = False  # 是否解析过methods
            if self.currentTokenValue() == "methods":
                is_methods_parsed = True
                self.eatCurrentTokenType("KEYWORD")  # methods
                self.eatCurrentTokenType("LBRACE")  # {

                # =====================static method=======================
                # @annotation()
                while self.currentTokenValue() == "def" or self.currentTokenValue() == "static" or self.currentTokenValue() == "@":
                    # method_def_node = self.function_declaration();
                    method_def_node = self.class_method_declaration()  # 解析方法定义节点
                    # SayHello': FunctionDeclarationNode(is_static=True,name=SayHello, args=['arg'],去哦他)

                    method_name = method_def_node.name  # 方法名
                    
                    # 支持方法重载：如果同名方法已存在，转换为列表存储
                    if method_name in methods:
                        existing = methods[method_name]
                        # 如果还不是列表，先转换为列表
                        if not isinstance(existing, list):
                            methods[method_name] = [existing]
                        methods[method_name].append(method_def_node)
                    else:
                        methods[method_name] = method_def_node
                    # 存入方法的注解

                if is_methods_parsed:
                    self.eatCurrentTokenType("RBRACE")  # }

            # init_methods = []
            while self.currentTokenValue() == "init":
                if_init_parsed = True
                init_method = self.parse_init_method()
                init_methods.append(init_method)
                if if_init_parsed:
                    self.eatCurrentTokenType("RBRACE")  # }

            # 解析运算符重载
            is_operators_parsed = False
            if self.currentTokenValue() == "operators":
                is_operators_parsed = True
                self.eatCurrentTokenType("KEYWORD")  # operators
                self.eatCurrentTokenType("LBRACE")  # {

                while self.currentTokenValue() == "def":
                    operator_def_node = self.class_method_declaration()  # 解析运算符定义
                    operator_name = operator_def_node.name  # 运算符名（如 plus, minus）
                    operators[operator_name] = operator_def_node

                if is_operators_parsed:
                    self.eatCurrentTokenType("RBRACE")  # }

        # 出来，遇到 }
        self.eatCurrentTokenType("RBRACE")  # 类声明的 }

        # 构造函数重载
        if len(init_methods) == 1:
            init_method = init_methods[0]
        else:
            init_method = init_methods

        return ClassDeclarationNode(class_name, methods, fields,
                                    init_method, static_methods,
                                    static_fields, parent_name, interfaces, 
                                    fields_annotations=fields_annotations, operators=operators)

    def super_statement(self):
        """
        解析两种 super 语法：
        1. super(args);          - 调用父类构造函数
        2. super->method(args);  - 调用父类方法
        """
        self.eatCurrentTokenType("KEYWORD")  # super

        # super(args) - 调用父类构造函数
        if self.currentTokenType() == "LPAREN":
            self.eatCurrentTokenType("LPAREN")  # (
            args = []
            while self.currentTokenType() != "RPAREN":
                args.append(self.expr())
                if self.currentTokenType() == "COMMA":
                    self.eatCurrentTokenType("COMMA")
            self.eatCurrentTokenType("RPAREN")  # )
            if self.currentTokenType() == "END":
                self.eatCurrentTokenType("END")  # ;
            return SuperCallNode(args)

        # super->method(args) - 调用父类方法
        elif self.currentTokenType() == "MINUS" and self.peekNextTokenType() == "GT":
            self.eatCurrentTokenType("MINUS")  # -
            self.eatCurrentTokenType("GT")  # >
            method_name = self.currentTokenValue()
            self.eatCurrentTokenType("ID")  # method name
            self.eatCurrentTokenType("LPAREN")  # (
            args = []
            while self.currentTokenType() != "RPAREN":
                args.append(self.expr())
                if self.currentTokenType() == "COMMA":
                    self.eatCurrentTokenType("COMMA")
            self.eatCurrentTokenType("RPAREN")  # )
            if self.currentTokenType() == "END":
                self.eatCurrentTokenType("END")  # ;
            return SuperMethodCallNode(method_name, args)
        else:
            raise SyntaxError("Invalid super syntax. Use super(args) or super->method(args)")

    def parse_init_method(self):
        self.eatCurrentTokenType('KEYWORD')  # init
        self.eatCurrentTokenType('LPAREN')  # (

        # 默认值
        default_values = {}
        # 可变参数名
        vararg_name = None
        
        params = []
        while self.currentTokenType() != 'RPAREN':
            # 检查是否是可变参数 ...args
            if self.currentTokenType() == 'ELLIPSIS':
                self.eatCurrentTokenType('ELLIPSIS')  # ...
                vararg_name = self.currentTokenValue()
                self.eatCurrentTokenType('ID')  # 参数名
                if self.currentTokenType() == 'COMMA':
                    raise SyntaxError("Variadic parameter must be the last parameter")
                break
            
            # 解析参数
            params.append(self.currentTokenValue())
            self.eatCurrentTokenType('ID')

            # ===============解析默认值=========test=====
            if self.currentTokenType() == 'ASSIGN':
                self.eatCurrentTokenType('ASSIGN')
                default_values[params[-1]] = self.expr()
            # ===============解析默认值=========test=====

            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')
        self.eatCurrentTokenType('RPAREN')  # )
        self.eatCurrentTokenType('LBRACE')  # {
        body = []

        # super {}
        while self.currentTokenType() != 'RBRACE':
            if self.currentTokenValue() == "super":
                super_node = self.super_statement()
                body.append(super_node)
            else:
                stmt = self.statement()
                body.append(stmt)
        node = FunctionDeclarationNode("init", params, body, default_values, vararg_name=vararg_name)

        return node

    def module_method_call(self):
        print("module_method_call: ")
        # 往函数调用方向凑 模块.方法(参数)
        name = self.currentTokenValue()  # 模块名称
        self.eatCurrentTokenType('ID')

        name += self.currentTokenType()  # .
        self.eatCurrentTokenType('ID')

        name += self.currentTokenValue()  # 方法名称
        self.eatCurrentTokenType('ID')
        # print("name: ", name)
        self.eatCurrentTokenType('LPAREN')  # (

        named_arg_values = {}
        # 解析函数参数
        args = []
        if self.currentTokenType() != 'RPAREN':  # 解析第一个参数
            # =====================解析命名参数==============test=====
            # add(b=1, c=2);
            if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'ASSIGN':
                while self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'ASSIGN':
                    format_param = self.currentTokenValue()  # add(b = 1, c = 2); 中的b
                    self.eatCurrentTokenType('ID')  # add(b = 1, c = 2); 中的b
                    self.eatCurrentTokenType('ASSIGN')  # add(b = 1, c = 2); 中的=
                    named_arg_values[format_param] = self.expr()  # add(b = 1, c = 2); 中的1
                    # 最后一个参数的判断
                    if self.currentTokenType() == 'COMMA':
                        self.eatCurrentTokenType('COMMA')  # ,
                print("passin_arg_values: ", named_arg_values)
            # ==================解析命名参数===============================================
            else:
                # ===================原来的解析方式=======位置参数=================================
                # 函数参数可以是任意表达式，比如1+2, add(), true and true, 1>2, "hello"等
                args.append(self.expr())
                while self.currentTokenType() == 'COMMA':  # 解析多个参数
                    self.eatCurrentTokenType('COMMA')  # ,
                    args.append(self.expr())
                # ===================原来的解析方式========================================
        # 原来这两行代码是和else一个dent的，现在是测试
        self.eatCurrentTokenType('RPAREN')  # )
        self.eatCurrentTokenType('END')  # ;
        return FunctionCallNode(name, args, named_arg_values)

    def import_module_statement(self):
        """
        解析 import 语句:
        1. import Math;                    # 导入整个模块
        2. import { pi, x } from Math;    # 选择性导入
        3. import Math as m;              # 带别名导入
        """

        self.eatCurrentTokenType(Tokens.KEYWORD)  # import

        # 情况1: import { pi, x } from Math
        if self.currentTokenType() == Tokens.LBRACE:
            self.eatCurrentTokenType(Tokens.LBRACE)  # {

            import_elements = []
            while self.currentTokenType() != Tokens.RBRACE:
                element = self.currentTokenValue()  # 元素名称
                self.eatCurrentTokenType(Tokens.ID)
                import_elements.append(element)
                if self.currentTokenType() == Tokens.COMMA:
                    self.eatCurrentTokenType(Tokens.COMMA)
            self.eatCurrentTokenType(Tokens.RBRACE)  # }

            # 必须有 from 关键字
            self.eatCurrentTokenType(Tokens.KEYWORD)  # from

            # 模块名称
            is_builtin_module  = True
            module_name = self.currentTokenValue()
            if self.currentTokenType() == Tokens.ID:
                self.eatCurrentTokenType(Tokens.ID)  # 模块名
                is_builtin_module = True # 内置模块
            elif self.currentTokenType() == Tokens.STRING:
                self.eatCurrentTokenType(Tokens.STRING)
                is_builtin_module = False # 第三方模块

            if self.currentTokenType() == Tokens.END:
                self.eatCurrentTokenType(Tokens.END)  # ;
            return ImportModuleNode(module_name, import_elements, import_whole_module=False,alias=None,is_builtin_module=is_builtin_module)

        # 情况2: import Math 或 import Math as m
        elif self.currentTokenType() == Tokens.ID:
            module_name = self.currentTokenValue()
            self.eatCurrentTokenType(Tokens.ID)  # 模块名

            alias = None
            # 检查是否有别名
            if self.currentTokenType() == Tokens.KEYWORD and self.currentTokenValue() == "as":
                self.eatCurrentTokenType(Tokens.KEYWORD)  # as
                alias = self.currentTokenValue()  # 别名
                self.eatCurrentTokenType(Tokens.ID)

            if self.currentTokenType() == "END":
                self.eatCurrentTokenType("END")  # ;
            return ImportModuleNode(module_name, [], import_whole_module=True, alias=alias)
        # import "xx/mod.fight"
        elif self.currentTokenType() == Tokens.STRING:
            module_path = self.currentTokenValue()
            self.eatCurrentTokenType(Tokens.STRING)

            alias = None
            # 支持 import "path" as Alias 形式
            if self.currentTokenType() == Tokens.KEYWORD and self.currentTokenValue() == "as":
                self.eatCurrentTokenType(Tokens.KEYWORD)  # as
                alias = self.currentTokenValue()
                self.eatCurrentTokenType(Tokens.ID)

            if self.currentTokenType() == Tokens.END:
                self.eatCurrentTokenType(Tokens.END)  # ;
            return ImportModuleNode(module_path, [], import_whole_module=True, alias=alias,is_builtin_module=False)

    def package_statement(self):
        self.eatCurrentTokenType('KEYWORD')  # package
        package_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 包名
        self.eatCurrentTokenType("LBRACE")  # {
        statements = []
        while self.currentTokenType() != "RBRACE":
            statements.append(self.statement())
        self.eatCurrentTokenType("RBRACE")  # }
        # 不需要 ;
        return PackageDeclarationNode(package_name, statements)

    def const_statement(self):
        self.eatCurrentTokenType('KEYWORD')  # const
        const_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 变量名
        self.eatCurrentTokenType('ASSIGN')  # =
        const_value = self.expr()
        if self.currentTokenType() == "END":
            self.eatCurrentTokenType('END')  # ;
        return AssignmentNode(const_name, const_value, True)

    def factor(self):
        """
            factor 是最小的组成部分，可以是:
                 (1)一个数字 2 1.2
                 (2)一个变量 x
                 (3) 一个括号括起来的表达式 (1+2)
                 (4) 布尔值 true False
                 (5) 字符串 "hello world"
                 (6) 数组 [1,2,3]
                 (7) 对象 {name: "value"}
                 (3)一个括号括起来的表达式 (1+2)
                 (8) 函数调用 add(1,2)
                 (9) not 表达式:  not true
                 (10) 一元负号运算符: -x, -add(), -(1+2)
        """
        # 处理一元负号运算符: -x, -add(), -(1+2)
        if self.currentTokenType() == 'MINUS':
            self.eatCurrentTokenType('MINUS')  # 消耗 -
            operand = self.factor()  # 递归解析操作数
            return UnaryOpNode('minus', operand)  # 创建一元运算符节点
        
        token = self.currentTokenType()
        if token == 'NUMBER':
            # 解析数字: 字符串形式
            node = NumberNode(self.currentTokenValue())
            self.eatCurrentTokenType('NUMBER')
            # print("node: ", node)
            return node
            # 解析函数调用表达式
        elif token == 'ID':
            # py{...} 作为表达式
            if self.currentTokenValue() == "py" and self.peekNextTokenType() == 'LBRACE':
                return self.parse_py_exec()
            # pyFn{...} 作为函数值
            if self.currentTokenValue() == "pyFn" and self.peekNextTokenType() == 'LBRACE':
                return self.parse_py_fn()
            # 判断是否为函数调用
            if self.peekNextTokenType() == 'LPAREN':
                return self.function_call_expr()  # 调用函数解析
            # 解析列表索引表达式
            elif self.peekNextTokenType() == 'LBRACKET':
                return self.index_expr()

            # 解析对象索引表达式  obj{expr}
            elif self.peekNextTokenType() == 'LBRACE':
                # 尝试解析结构体赋值
                if self.tokens[self.pos + 3][0] == "COLON":
                    return self.struct_assign_expr()
                # 尝试解析对象索引表达式  obj{expr}
                return self.object_index_expr()
            # 一个大坑: 对于模块调用方法,第一个token是Id, 那么对其的处理
            # 必须是在 elif token = "ID"分支下
            # 模块调用方法 比如 let z = module.add(1,2);
            elif self.peekNextTokenType() == "DOT":
                if self.tokens[self.pos + 2][0] == "ID":  # ID
                    if self.tokens[self.pos + 3][0] == "LPAREN":  # LPAREN
                        return self.module_method_call_expr()
                    elif self.tokens[self.pos + 3][0] == "LBRACE":  # 模块.结构体{...}
                        # 调用模块里面的结构体类型并实例化  比如 bigJ.Book{...}
                        return self.module_struct_instantiation()
                    elif self.tokens[self.pos + 3][0] == "COLON" and self.tokens[self.pos + 4][0] == "COLON":  # 模块.枚举::值
                        # 访问模块里面的枚举值  比如 bigJ.Color::RED
                        return self.module_enum_access_expr()
                    else:
                        # 调用模块里面的变量或者常量  比如 @log(Util.pi);
                        return self.module_expr()  # 进入module_expr的时候还是ID,也就是模块名称

            # 解析获取对象属性的表达式  let z = p->Age;  @log(p->Age);这样的操作
            elif self.peekNextTokenType() == 'MINUS' and self.tokens[self.pos + 2][0] == 'GT':
                # if self.tokens[self.pos + 3][0] != 'LPAREN':  # 说明是获取对象的属性
                # return self.get_member_expr()  老名字
                return self.get_member_expr_or_method_call_expr()

            # 解析结构体对象访问属性的   p::x
            elif self.peekNextTokenType() == 'COLON' and self.tokens[self.pos + 2][0] == 'COLON':
                return self.struct_access_expr()
            # 函数组合
            elif self.peekNextTokenType() == Tokens.COMBINE:
                return self.parseFunctionCombination()
            # 检查是否是宏调用（先检查是否有宏定义，再按需处理）
            # 简单处理：返回变量节点，让Evaluator处理宏展开
            node = VariableNode(self.currentTokenValue())
            self.eatCurrentTokenType('ID')
            return node
        # 最小表达式：(1+2)这样的表达式, 递归解析嵌套括号
        elif token == 'LPAREN':
            self.eatCurrentTokenType('LPAREN')
            node = self.expr()
            self.eatCurrentTokenType('RPAREN')
            return node
        elif token == 'BOOL':
            node = BooleanNode(self.currentTokenValue())
            self.eatCurrentTokenType('BOOL')
            return node
        elif token == 'STRING':
            # ""->xxx()这种;
            if self.peekNextTokenType() == "MINUS" and self.tokens[self.pos + 2][0] == "GT":
                return self.str_expr_method_call()

            node = StringNode(self.currentTokenValue())
            self.eatCurrentTokenType('STRING')
            return node

        # 列表生成器
        elif self.currentTokenValue() == "generator" and self.peekNextTokenType() == "LBRACKET":
            return self.parse_list_generator()

        # 数组解析
        elif token == 'LBRACKET':  # [1,2,3]

            lst_node = self.parse_array()

            # []->reverse()->combine()这样的连续调用
            if self.currentTokenType() == "MINUS" and self.peekNextTokenType() == "GT":
                print("enter")
                return self.list_expr_method_call(lst_node)
            else:
                return lst_node

        elif token == 'LBRACE':  # {name: "value"}
            obj = self.parse_object()
            # {}->reverse()->combine()这样的连续调用
            if self.currentTokenType() == "MINUS" and self.peekNextTokenType() == "GT":
                # 解析对象方法调用表达式
                return self.get_member_expr_or_method_call_expr({"name": "anonymous", "val": obj})
            return obj

        # set集合
        elif self.currentTokenValue() == 'set' and self.peekNextTokenType() == "LT":
            return self.parse_set()

            # 解析逻辑表达式
        elif token == '!':
            return self.logical_expr()

        # 一下形式的lambda表达式:  let z = def(x,y){ x+y }
        elif self.currentTokenValue() == 'def':
            if self.peekNextTokenType() == 'LPAREN':
                # 返回FunctionDeclarationNode 即可
                return self.anonymous_function_declaration()

        # 真的lambda表达式：  let z = lambda x,y:x+y;
        elif self.currentTokenValue() == 'lambda':
            if self.peekNextTokenType() == 'ID':
                # 返回FunctionDeclarationNode 即可
                return self.real_lambda_function_declaration()

        # 箭头函数
        # let z = <<x,y>> =>{};
        elif self.currentTokenType() == 'LT' and self.peekNextTokenType() == "LT":  # <
            return self.arrow_function_declaration()


        # 实例化对象  let z = new 类名();  右侧的: new 类名() 算作表达式
        elif self.currentTokenValue() == "new":
            return self.evaluate_new_expr()


        elif self.currentTokenValue() == 'this':
            # body里面的: ReturnNode(value=ThisNode())
            return self.parse_this()

        # if () x : y 这样的表达式
        elif self.currentTokenValue() == 'if':
            return self.if_expr()

        # match表达式
        elif self.currentTokenValue() == 'match':
            return self.match_expr()

        # let x= enum::Color::RED;
        elif self.currentTokenValue() == "enum" and self.peekNextTokenType() == "COLON":
            return self.enum_access_expr()

        # abs
        elif self.currentTokenValue() == "|":
            return self.abs_expr()

        # super 作为表达式（在方法体内使用）
        elif self.currentTokenValue() == "super":
            return self.super_statement()
        else:
            raise SyntaxError(
                f"Unexpected token: {token}, value = {self.currentTokenValue()}, next_token = {self.peekNextTokenValue()}")

    def parse_py_exec(self):
        """
            解析 py{...} 表达式
            内容部分是一个普通表达式，其求值结果应当是 *Python 代码字符串*
        """
        self.eatCurrentTokenType('ID')  # py
        self.eatCurrentTokenType('LBRACE')
        code_expr = self.expr()
        self.eatCurrentTokenType('RBRACE')
        return PyExecNode(code_expr)

    def parse_py_fn(self):
        """
            解析 pyFn{...} 表达式
            内容部分是一个普通表达式，其求值结果应当是 *Python 代码字符串*，
            但不会立即执行，而是包装为可调用的 Python 函数作为值返回
        """
        self.eatCurrentTokenType('ID')  # pyFn
        self.eatCurrentTokenType('LBRACE')
        code_expr = self.expr()
        self.eatCurrentTokenType('RBRACE')
        return PyFnNode(code_expr)

    def list_expr_method_call(self, lst_node):
        """
            []->reverse()->combine()这样的连续调用

        """
        return self.get_member_expr_or_method_call_expr({"name": "anonymous", "val": lst_node})

    def str_expr_method_call(self):
        # ""->xxx()这种;
        val = self.currentTokenValue()
        self.eatCurrentTokenType('STRING')  # "
        return self.get_member_expr_or_method_call_expr({"name": "anonymous", "val": val})

    def abs_expr(self):
        # abs(x)
        print("entered abs_expr")
        self.eatCurrentTokenType("ABSOLUTE")  # |
        expr = self.expr()
        self.eatCurrentTokenType("ABSOLUTE")  # |
        return AbsNode(expr)

    def parse_list_generator(self):
        # generator([x+1; 1 to 10];
        self.eatCurrentTokenType('KEYWORD')  # generator
        self.eatCurrentTokenType('LBRACKET')  # [
        # 解析列表生成器的表达式
        gen_expr = self.expr()
        self.eatCurrentTokenType("END")

        iter_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 迭代器变量名
        self.eatCurrentTokenType("ASSIGN")  # =

        start = self.expr()
        self.eatCurrentTokenType("KEYWORD")  # to
        end = self.expr()

        # step
        if self.currentTokenValue() == "step":
            self.eatCurrentTokenType("KEYWORD")  # step
            step = self.expr()
        else:
            step = 1
        self.eatCurrentTokenType("RBRACKET")

        return ListGeneratorNode(gen_expr, iter_name, start, end, step)
    def parseFunctionCombination(self):
        """
            组合为：函数组合节点
            进来时第一个token是ID
            e.g
                let comb = getVal & add & double;
        """
        combinations = []
        combinations.append(self.currentTokenValue()) # 第一个函数名
        self.eatCurrentTokenType(Tokens.ID)
        
        # 处理 & 连接的其他函数
        while self.pos < len(self.tokens) and self.currentTokenType() == Tokens.COMBINE:
            self.eatCurrentTokenType(Tokens.COMBINE)
            if self.pos < len(self.tokens) and self.currentTokenType() == Tokens.ID:
                combinations.append(self.currentTokenValue())
                self.eatCurrentTokenType(Tokens.ID)
            else:
                raise SyntaxError(f"Unexpected token: {self.currentTokenType() if self.pos < len(self.tokens) else 'EOF'}, expected type: ID")
        return FunctionCombinationNode(fns=combinations)

    def struct_access_assign_statement(self):
        """
            结构体属性赋值语句:
                p::x = 99;
        """
        instance_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')
        self.eatCurrentTokenType('COLON')
        self.eatCurrentTokenType('COLON')
        field_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')
        self.eatCurrentTokenType('ASSIGN')
        value_expr = self.expr()
        if self.currentTokenType() == 'END':
            self.eatCurrentTokenType('END')
        return StructAccessAssignNode(instance_name, field_name, value_expr)

    def struct_access_expr(self):
        # 进来的时候是ID
        # 解析结构体对象访问属性的   p::x
        struct_instance_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 实例名
        self.eatCurrentTokenType('COLON')  # :
        self.eatCurrentTokenType('COLON')  # :
        struct_field_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 字段名
        return StructAccessNode(struct_instance_name, struct_field_name)

    def struct_assign_expr(self):  # 看作表达式
        # 例子:  Point { x: 1， y: 2}
        # 解析结构体赋值表达式
        struct_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 结构体名
        self.eatCurrentTokenType('LBRACE')  # {
        struct_fields_values = {}
        while self.currentTokenType() != 'RBRACE':
            field_name = self.currentTokenValue()
            self.eatCurrentTokenType('ID')  # 字段名
            self.eatCurrentTokenType('COLON')  # :
            field_value = self.expr()  # 字段值
            struct_fields_values[field_name] = field_value
            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')  # ,
        self.eatCurrentTokenType('RBRACE')  # }
        return StructAssignNode(struct_name, struct_fields_values)

    def combine_expr(self):
        # 函数组合表达式
        # let z = f & g & i:
        # 特点：除了第一个id, 剩下的都是  一个 & 一个 id,
        funcs = []
        funcs.append(self.currentTokenValue())  # 第一个函数名
        self.eatCurrentTokenType('ID')
        while self.currentTokenType() == "COMBINE":
            self.eatCurrentTokenType("COMBINE")
            funcs.append(self.currentTokenValue())
            self.eatCurrentTokenType("ID")
        return CombineNode(funcs)

    def parse_set(self):
        # let z = set<1,2>;
        self.eatCurrentTokenType('KEYWORD')  # set
        self.eatCurrentTokenType('LT')  # <
        set_values = []
        while self.currentTokenType() != 'GT':
            set_values.append(self.expr())
            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')
        self.eatCurrentTokenType('GT')  # >
        # print("set_values: ", set_values)

        return SetNode(set_values)

    def match_expr(self):
        """
           let z = match(x){
                1 => "one",
                2,3 => "two or three",
                1-10 => "range 1-10",
                else => "other"
            }
        """
        global case
        self.eatCurrentTokenType('KEYWORD')  # match
        self.eatCurrentTokenType('LPAREN')  # (
        expr = self.expr()  # 被匹配的表达式
        self.eatCurrentTokenType('RPAREN')  # )
        self.eatCurrentTokenType('LBRACE')  # {

        case_value_dict = {}  # 解析case的value
        else_expr = None  # 解析else的表达式

        while self.currentTokenType() != 'RBRACE':
            if self.currentTokenValue() == 'else':
                self.eatCurrentTokenType('KEYWORD')  # else
                self.eatCurrentTokenType('ASSIGN')  # =
                self.eatCurrentTokenType('GT')  # >
                else_expr = self.expr()
                # else 分支通常作为最后一个分支，不需要逗号
                continue

            # 解析一个或多个 case 表达式，例如：1,2,3 => "x"
            cases = []
            single_case = self.expr()
            cases.append(single_case)
            # 同一分支内多个 case 之间用逗号分隔
            while self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')
                # 如果遇到 else 留给外层循环处理
                if self.currentTokenValue() == 'else':
                    break
                cases.append(self.expr())

            self.eatCurrentTokenType('ASSIGN')  # =
            self.eatCurrentTokenType('GT')  # >
            expr_if_match = self.expr()

            # 一个分支里的多个 case 共用同一个结果表达式
            for case in cases:
                case_value_dict[case] = expr_if_match

            # 分支之间用逗号分隔，最后一个分支后可以省略逗号
            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')  # ,
        self.eatCurrentTokenType('RBRACE')  # }
        return MatchExprNode(expr, case_value_dict, else_expr)

    def if_expr(self):
        # if(condi) x : y
        self.eatCurrentTokenType('KEYWORD')  # if
        self.eatCurrentTokenType('LPAREN')  # (
        condition = self.expr()
        self.eatCurrentTokenType('RPAREN')  # )
        expr_if_true = self.expr()
        self.eatCurrentTokenType('COLON')  # :
        expr_if_false = self.expr()
        return IfExprNode(condition, expr_if_true, expr_if_false)

    def parse_this(self):
        self.eatCurrentTokenType('KEYWORD')  # 'this'
        
        # 检查是否有 -> 符号，如果有则解析 this->member
        if self.currentTokenType() == 'MINUS' and self.peekNextTokenType() == 'GT':
            self.eatCurrentTokenType('MINUS')  # -
            self.eatCurrentTokenType('GT')  # >
            member_name = self.currentTokenValue()
            self.eatCurrentTokenType('ID')
            
            # 检查是否是方法调用
            if self.currentTokenType() == 'LPAREN':
                self.eatCurrentTokenType('LPAREN')
                args = []
                while self.currentTokenType() != 'RPAREN':
                    args.append(self.expr())
                    if self.currentTokenType() == 'COMMA':
                        self.eatCurrentTokenType('COMMA')
                self.eatCurrentTokenType('RPAREN')
                return CallClassInnerMethod(member_name, args)
            else:
                # 这是属性访问
                return GetMemberNodeByThis(member_name)
        
        return ThisNode()

    def parseComment(self):
        """
            #
                多行
                注释
            #
            #单行注释#
        """
        self.eatCurrentTokenType("COMMENT")  # #
        comment_content = ""
        while self.pos < len(self.tokens) and self.tokens[self.pos][0] != Tokens.COMMENT:
            comment_content += self.currentTokenValue()
            self.pos += 1
        self.eatCurrentTokenType("COMMENT")
        return CommentNode(comment_content)

    def get_member_expr_or_method_call_expr(self, expr_method_call_instance=None):

        # 考虑外界传进来一个匿名的对象： anonymous
        if expr_method_call_instance is not None:
            instance_or_class_name = expr_method_call_instance["name"]
        else:
            instance_or_class_name = self.currentTokenValue()
            self.eatCurrentTokenType('ID')

        # 原来的代码:
        # instance_or_class_name = self.currentTokenValue()
        # self.eatCurrentTokenType('ID')

        self.eatCurrentTokenType('MINUS')
        self.eatCurrentTokenType('GT')
        member_or_method_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')

        if self.currentTokenType() == 'LPAREN':
            # 这是一个方法调用
            self.eatCurrentTokenType('LPAREN')
            args = []
            while self.currentTokenType() != 'RPAREN':
                args.append(self.expr()) # 解析参数
                if self.currentTokenType() == 'COMMA':
                    self.eatCurrentTokenType('COMMA')
            self.eatCurrentTokenType('RPAREN')

            # ======================= 连续调用出现=================
            serial_call = []
            if self.currentTokenType() == 'MINUS' and self.peekNextTokenType() == 'GT':
                if expr_method_call_instance is not None:
                    methodCallNode = MethodCallNode(instance_or_class_name, member_or_method_name, args,
                                                      extra=expr_method_call_instance["val"])
                    serial_call.append(methodCallNode)
                else:
                    serial_call.append(MethodCallNode(instance_or_class_name, member_or_method_name, args))
                # while self.currentTokenType() != 'END':
                while self.currentTokenType() == 'MINUS' and self.tokens[self.pos + 1][0] == 'GT':
                    if expr_method_call_instance is not None:
                        serial_call.append(self.single_method_call_expr(instance_or_class_name,
                                                                        extra=expr_method_call_instance["val"]))
                    else:
                        serial_call.append(self.single_method_call_expr(instance_or_class_name))
                if expr_method_call_instance is not None:
                    return SerialCall(instance_or_class_name, serial_call, extra=expr_method_call_instance["val"])
                else:
                    return SerialCall(instance_or_class_name, serial_call)
            # ======================= 连续调用出现=================
            if expr_method_call_instance is not None:
                return MethodCallNode(instance_or_class_name, member_or_method_name, args,
                                      extra=expr_method_call_instance["val"])
            else:
                return MethodCallNode(instance_or_class_name, member_or_method_name, args)
        else:
            # 这是一个属性访问，可能是实例属性或静态属性
            return GetMemberNode(instance_or_class_name, member_or_method_name)
        # ========================version 2 ===end===========================================================================

    def single_method_call_expr(self, instance_or_class_name, extra=None):

        # 干掉 -> 符号
        if self.currentTokenType() == 'MINUS':
            self.eatCurrentTokenType('MINUS')
        if self.currentTokenType() == 'GT':
            self.eatCurrentTokenType('GT')
        # 从 -> 开始
        member_or_method_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')

        if self.currentTokenType() == 'LPAREN':
            # 这是一个方法调用
            self.eatCurrentTokenType('LPAREN')
            args = []
            while self.currentTokenType() != 'RPAREN':
                args.append(self.expr())
                if self.currentTokenType() == 'COMMA':
                    self.eatCurrentTokenType('COMMA')
            self.eatCurrentTokenType('RPAREN')
            return MethodCallNode(instance_or_class_name, member_or_method_name, args, extra=extra)
        else:
            # 这是一个属性访问，可能是实例属性或静态属性
            return GetMemberNode(instance_or_class_name, member_or_method_name)

    def evaluate_new_expr(self):
        # let z = new 类名(); 或 let c = new bigJ.Cal();
        object_name = self.tokens[self.pos - 2][1]
        self.eatCurrentTokenType('KEYWORD')  # new
        
        # 检查是否是模块类访问 (bigJ.Cal)
        if self.peekNextTokenType() == 'DOT':
            # 模块类实例化: new bigJ.Cal()
            module_name = self.currentTokenValue()
            self.eatCurrentTokenType('ID')  # 模块名
            self.eatCurrentTokenType('DOT')  # .
            class_name = self.currentTokenValue()
            self.eatCurrentTokenType('ID')  # 类名
            self.eatCurrentTokenType('LPAREN')  # (
            args = []
            if self.currentTokenType() != 'RPAREN':  # 解析第一个参数
                # 函数参数可以是任意表达式，比如1+2, add(), true and true, 1>2, "hello"等
                args.append(self.expr())
                while self.currentTokenType() == 'COMMA':  # 解析多个参数
                    self.eatCurrentTokenType('COMMA')  # ,
                    args.append(self.expr())
            self.eatCurrentTokenType('RPAREN')  # )
            return ModuleClassInstantiationNode(object_name, module_name, class_name, args)
        else:
            # 普通类实例化: new Cal()
            class_name = self.currentTokenValue()
            self.eatCurrentTokenType('ID')  # 类名
            self.eatCurrentTokenType('LPAREN')  # (
            args = []
            if self.currentTokenType() != 'RPAREN':  # 解析第一个参数
                # 函数参数可以是任意表达式，比如1+2, add(), true and true, 1>2, "hello"等
                args.append(self.expr())
                while self.currentTokenType() == 'COMMA':  # 解析多个参数
                    self.eatCurrentTokenType('COMMA')  # ,
                    args.append(self.expr())
            self.eatCurrentTokenType('RPAREN')  # )
            return NewObjectNode(object_name, class_name, args)

    # Parser.py 中的 module_expr 方法
    def module_expr(self):
        """
        解析模块成员访问: Math.pi

        返回一个特殊的访问节点，而不是字符串拼接
        """
        module_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # Math
        self.eatCurrentTokenType('DOT')  # .
        member_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # pi

        #  返回嵌套访问节点
        return ObjectIndexNode(
            object_name=module_name,
            key_expr=StringNode(member_name)
        )

    def module_struct_instantiation(self):
        """
        解析通过模块访问的结构体实例化: bigJ.Book{"title", 99}
        
        支持两种格式：
        1. 完整格式：bigJ.Book{title: "Fight", price: 99}
        2. 简写格式：bigJ.Book{"Fight", 99}
        """
        module_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 模块名
        self.eatCurrentTokenType('DOT')  # .
        struct_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 结构体名
        self.eatCurrentTokenType('LBRACE')  # {
        
        struct_fields_values = {}
        
        # 检查是否为空结构体 {}
        if self.currentTokenType() == 'RBRACE':
            self.eatCurrentTokenType('RBRACE')
            return ModuleStructAssignNode(module_name, struct_name, struct_fields_values)
        
        # 检查是完整格式（带字段名）还是简写格式（只有值）
        # 通过查看第二个token判断：如果是 COLON 则为完整格式
        is_full_format = False
        if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'COLON':
            is_full_format = True
        
        if is_full_format:
            # 完整格式：{title: "Fight", price: 99}
            while self.currentTokenType() != 'RBRACE':
                field_name = self.currentTokenValue()
                self.eatCurrentTokenType('ID')  # 字段名
                self.eatCurrentTokenType('COLON')  # :
                field_value = self.expr()  # 字段值
                struct_fields_values[field_name] = field_value
                if self.currentTokenType() == 'COMMA':
                    self.eatCurrentTokenType('COMMA')  # ,
        else:
            # 简写格式：{"Fight", 99}
            # 暂时存储值，后续在求值阶段根据字段顺序匹配
            field_values = []
            while self.currentTokenType() != 'RBRACE':
                field_values.append(self.expr())
                if self.currentTokenType() == 'COMMA':
                    self.eatCurrentTokenType('COMMA')
            # 用特殊键标记这是简写格式
            struct_fields_values['__short_format__'] = field_values
        
        self.eatCurrentTokenType('RBRACE')  # }
        return ModuleStructAssignNode(module_name, struct_name, struct_fields_values)

    def module_enum_access_expr(self):
        """
        解析通过模块访问的枚举值: bigJ.Color::RED
        类似于 enum::Color::RED，但是枚举名前面是模块名
        """
        module_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 模块名
        self.eatCurrentTokenType('DOT')  # .
        enum_name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 枚举名
        self.eatCurrentTokenType('COLON')  # :
        self.eatCurrentTokenType('COLON')  # :
        enum_property = self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 枚举值
        return ModuleEnumAccessNode(module_name, enum_name, enum_property)

    def module_method_call_expr(self):
        # print("called module_method_call_expr")
        # let z = 模块.add(1,2);
        name = self.currentTokenValue()  # 模块名称
        self.eatCurrentTokenType('ID')
        name += self.currentTokenValue()
        self.eatCurrentTokenType('DOT')  # .
        name += self.currentTokenValue()
        self.eatCurrentTokenType('ID')  # 方法名
        self.eatCurrentTokenType('LPAREN')  # (

        # 解析函数参数，支持位置参数 + 命名参数
        args = []
        named_arg_values = {}
        seen_named = False

        if self.currentTokenType() != 'RPAREN':  # 至少有一个参数
            while True:
                # 命名参数: 形如 x = expr
                if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'ASSIGN':
                    seen_named = True
                    param_name = self.currentTokenValue()
                    self.eatCurrentTokenType('ID')
                    self.eatCurrentTokenType('ASSIGN')
                    named_arg_values[param_name] = self.expr()
                else:
                    # 一旦出现过命名参数，后面就不允许再出现位置参数
                    if seen_named:
                        raise SyntaxError("Positional arguments cannot follow named arguments")
                    args.append(self.expr())

                if self.currentTokenType() != 'COMMA':
                    break
                self.eatCurrentTokenType('COMMA')  # ,

        self.eatCurrentTokenType('RPAREN')  # )
        return FunctionCallNode(name, args, named_arg_values)

    def arrow_function_declaration(self):
        # let z = <<x = 1,y = 2>> =>{    //code   };
        arrow_func_name = self.tokens[self.pos - 2][1]  # 箭头函数名称
        self.eatCurrentTokenType('LT')  # <
        self.eatCurrentTokenType('LT')  # <

        default_values = {}
        # 可变参数名
        vararg_name = None

        params = []
        while self.currentTokenType() != 'GT':
            # 检查是否是可变参数 ...args
            if self.currentTokenType() == 'ELLIPSIS':
                self.eatCurrentTokenType('ELLIPSIS')  # ...
                vararg_name = self.currentTokenValue()
                self.eatCurrentTokenType('ID')  # 参数名
                if self.currentTokenType() == 'COMMA':
                    raise SyntaxError("Variadic parameter must be the last parameter")
                break
            
            # 解析参数
            params.append(self.currentTokenValue())  # 参数名称
            self.eatCurrentTokenType('ID')

            # ===============解析默认值=========test=====
            # # 检查是否有默认值
            if self.currentTokenType() == 'ASSIGN':
                self.eatCurrentTokenType('ASSIGN')  # '='
                default_values[params[-1]] = self.expr()  # 解析默认值
                # print("解析到的默认值： ", default_values[params[-1]])
            # ===============解析默认值=========test=====

            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')

        self.eatCurrentTokenType('GT')  # >
        self.eatCurrentTokenType('GT')  # >
        self.eatCurrentTokenType('ASSIGN')  # =
        self.eatCurrentTokenType('GT')  # >
        self.eatCurrentTokenType('LBRACE')  # {

        body = []
        while self.currentTokenType() != 'RBRACE':  # }
            body.append(self.statement())
        self.eatCurrentTokenType('RBRACE')  # }
        # ; 不需要处理
        return FunctionDeclarationNode(arrow_func_name, params, body, default_values, vararg_name=vararg_name)

    def real_lambda_function_declaration(self):
        # let z = lambda x,y: x+y; 这种形式里面的z就是函数名
        lambda_name = self.tokens[self.pos - 2][1]  # lambda函数名称
        self.eatCurrentTokenType('KEYWORD')  # lambda关键字
        # 解析参数
        params = []
        while self.currentTokenType() != 'COLON':  # :
            # 解析参数
            params.append(self.currentTokenValue())  # 参数名
            self.eatCurrentTokenType('ID')  # 参数名
            if self.currentTokenType() == 'COMMA':  # ,
                self.eatCurrentTokenType('COMMA')

        self.eatCurrentTokenType('COLON')  # :
        # 解析函数体
        body = []
        expr = self.expr()
        body.append(expr)
        # 处理末尾的分号???  不需要，因为assignment语句处理了
        # if self.currentTokenType() == 'END':
        #     self.eatCurrentTokenType('END')
        return FunctionDeclarationNode(lambda_name, params, body)

    # let x = def(x,y){ x+y }类型的表达式
    def anonymous_function_declaration(self, passin_name=None):
        # let add = def(x = 1,y = 10){ return x+y; }
        lambda_name = self.tokens[self.pos - 2][1]

        # if passin_name is not None:
        #     lambda_name = passin_name
        # # 解析函数名: 名称有问题，应该设置为一个不会重复的str(数字)
        # # print(" self.tokens[self.pos - 2][1]: ", self.tokens[self.pos - 2][1])
        # # lambda_name = str(uuid.uuid4())  # 随机生成一个uuid作为函数名
        # print("lambda_name: ", lambda_name)

        self.eatCurrentTokenType('KEYWORD')  # def
        self.eatCurrentTokenType("LPAREN")  # (

        # =============解析默认参数和命名参数====================================
        # 默认值
        default_values = {}
        # 可变参数名
        vararg_name = None

        # 解析参数
        params = []
        while self.currentTokenType() != 'RPAREN':
            # 检查是否是可变参数 ...args
            if self.currentTokenType() == 'ELLIPSIS':
                self.eatCurrentTokenType('ELLIPSIS')  # ...
                vararg_name = self.currentTokenValue()
                self.eatCurrentTokenType('ID')  # 参数名
                if self.currentTokenType() == 'COMMA':
                    raise SyntaxError("Variadic parameter must be the last parameter")
                break
            
            # 解析参数
            params.append(self.currentTokenValue())  # 参数名称
            self.eatCurrentTokenType('ID')
            # print("params[-1]: ", params[-1])

            # ===============解析默认值=========test=====
            if self.currentTokenType() == 'ASSIGN':  # 有默认值 x = 1,
                self.eatCurrentTokenType('ASSIGN')
                default_values[params[-1]] = self.expr()

            # ===============解析默认值=========test=====
            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')

        self.eatCurrentTokenType('RPAREN')  # )
        self.eatCurrentTokenType('LBRACE')  # {
        body = []
        while self.currentTokenType() != 'RBRACE':
            body.append(self.statement())
        self.eatCurrentTokenType('RBRACE')  # }
        # self.eatCurrentTokenType('END')  # ;
        return FunctionDeclarationNode(lambda_name, params, body, default_values, func_type="anonymous", vararg_name=vararg_name)

    def class_method_declaration(self):
        """
            解析类方法声明语句

            class Person{
               methods{
                    static def xxx(){}
               }

            }
        """
        method_annotation = None
        if self.currentTokenValue() == "@":
            method_annotation = self.parse_annotation()
            print("method_annotation: ", method_annotation)

        is_static = False
        if self.currentTokenValue() == "static":
            is_static = True
            self.eatCurrentTokenType("KEYWORD")  # static
        self.eatCurrentTokenType('KEYWORD')  # 'function'  'def'

        name = self.currentTokenValue()  # 函数名

        self.eatCurrentTokenType('ID')  # 函数名
        self.eatCurrentTokenType('LPAREN')  # (

        # 默认值
        default_values = {}
        # 可变参数名
        vararg_name = None

        params = []
        while self.currentTokenType() != 'RPAREN':
            # 检查是否是可变参数 ...args
            if self.currentTokenType() == 'ELLIPSIS':
                self.eatCurrentTokenType('ELLIPSIS')  # ...
                vararg_name = self.currentTokenValue()
                self.eatCurrentTokenType('ID')  # 参数名
                if self.currentTokenType() == 'COMMA':
                    raise SyntaxError("Variadic parameter must be the last parameter")
                break
            
            # 解析参数
            params.append(self.currentTokenValue())
            self.eatCurrentTokenType('ID')

            # ===============解析默认值=========test=====
            if self.currentTokenType() == 'ASSIGN':
                self.eatCurrentTokenType('ASSIGN')
                default_values[params[-1]] = self.expr()
            # ===============解析默认值=========test=====

            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')
        self.eatCurrentTokenType('RPAREN')  # )
        self.eatCurrentTokenType('LBRACE')  # {
        body = []
        while self.currentTokenType() != 'RBRACE':
            body.append(self.statement())
        self.eatCurrentTokenType('RBRACE')

        return FunctionDeclarationNode(name, params, body, default_values, is_static, tag="class_method",
                                       annotations=method_annotation, vararg_name=vararg_name)

    def function_declaration(self):
        """
            参数解析：目前支持传入数字、字符串、布尔值、数组、对象、函数，但是不支持传入函数
        """

        self.eatCurrentTokenType('KEYWORD')  # 'function'  'def'
        name = self.currentTokenValue()  # 函数名
        self.eatCurrentTokenType('ID')  # 函数名
        self.eatCurrentTokenType('LPAREN')  # (
        # 默认值
        default_values = {}
        # 可变参数名
        vararg_name = None

        params = []
        while self.currentTokenType() != 'RPAREN':
            # 检查是否是可变参数 ...args
            if self.currentTokenType() == 'ELLIPSIS':
                self.eatCurrentTokenType('ELLIPSIS')  # ...
                vararg_name = self.currentTokenValue()
                self.eatCurrentTokenType('ID')  # 参数名
                # 可变参数必须是最后一个参数
                if self.currentTokenType() == 'COMMA':
                    raise SyntaxError("Variadic parameter must be the last parameter")
                break
            
            # 解析参数
            params.append(self.currentTokenValue())
            self.eatCurrentTokenType('ID')

            # ===============解析默认值=========test=====
            if self.currentTokenType() == 'ASSIGN':
                self.eatCurrentTokenType('ASSIGN')
                default_values[params[-1]] = self.expr()
            # ===============解析默认值=========test=====

            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')
        self.eatCurrentTokenType('RPAREN')  # )

        body = []
        if self.currentTokenType() == Tokens.LBRACE:
            self.eatCurrentTokenType('LBRACE')  # {
            while self.currentTokenType() != 'RBRACE':
                body.append(self.statement())
            self.eatCurrentTokenType('RBRACE')
            return FunctionDeclarationNode(name, params, body, default_values, vararg_name=vararg_name)
        else:
            if self.currentTokenType() == Tokens.ASSIGN:
                self.eatCurrentTokenType(Tokens.ASSIGN) # =
                self.eatCurrentTokenType(Tokens.GT)  # >
            else:
                raise SyntaxError("Expected '{' or '=>' after function name")
            # 支持一句话函数 def add(x) => x+1;
            body.append(self.statement())
            return FunctionDeclarationNode(name, params, body, default_values, vararg_name=vararg_name)


    def for_in_statement(self):
        """
            1, for in解析
                for(ele in []){}
            2, for(idx in 1..10){}
        """
        self.eatCurrentTokenType('KEYWORD')  # for
        self.eatCurrentTokenType("LPAREN")

        var_name = self.currentTokenValue()  # 变量名
        self.eatCurrentTokenType('ID')  # 变量名

        # 第二类 for : 语法
        # for (idx : 55 to getNumber()){
        #
        # }
        if self.currentTokenType() == 'COLON':
            self.eatCurrentTokenType('COLON')  # :
            start_value = self.expr()
            self.eatCurrentTokenType('KEYWORD')  # to
            end_value = self.expr()
            self.eatCurrentTokenType("RPAREN")  # )
            self.eatCurrentTokenType("LBRACE")  # {
            # block statements
            block_statements = []  # 存放if语句块中的语句
            while self.currentTokenType() != 'RBRACE':
                block_statements.append(self.statement())
            self.eatCurrentTokenType("RBRACE")  # }
            return ForRangeNumberNode(var_name, start_value, end_value, block_statements)

        # for in语法
        if self.currentTokenValue() == 'in':
            self.eatCurrentTokenType('KEYWORD')  # in
            iterable_obj = self.expr()
            self.eatCurrentTokenType("RPAREN")  # )
            self.eatCurrentTokenType('LBRACE')  # {
            # block statements
            block_statements = []  # 存放if语句块中的语句
            while self.currentTokenType() != 'RBRACE':
                block_statements.append(self.statement())
            self.eatCurrentTokenType("RBRACE")  # }
            return ForInNode(var_name, iterable_obj, block_statements)

    def elif_statement(self):
        """
            解析得到的结构：
                [{condition: expr, elif_statements: [stmt,stmt},{}]
        """
        elif_statements = []
        if self.currentTokenValue() == 'elif':
            # 解析elif语句, 可以有多个elif语句
            while self.currentTokenValue() == 'elif':
                self.eatCurrentTokenType('KEYWORD')  # elif
                self.eatCurrentTokenType("LPAREN")  # (
                # 条件
                elif_condition = self.expr()
                self.eatCurrentTokenType("RPAREN")  # )
                self.eatCurrentTokenType("LBRACE")  # {
                # block statements
                elif_block_statements = []  # 存放elif语句块中的语句
                while self.currentTokenType() != 'RBRACE':
                    elif_block_statements.append(self.statement())
                self.eatCurrentTokenType("RBRACE")  # }

                # [{condition: expr, elif_statements: [stmt,stmt},{}]
                part = {'condition': elif_condition, 'elif_statements': elif_block_statements}
                elif_statements.append(part)
        return elif_statements

    def else_statement(self):
        # 解析else语句
        else_statements = []
        if self.currentTokenType() == 'KEYWORD' and self.currentTokenValue() == 'else':
            self.eatCurrentTokenType('KEYWORD')  # else
            self.eatCurrentTokenType("LBRACE")  # {
            while self.currentTokenType() != 'RBRACE':
                else_statements.append(self.statement())
            self.eatCurrentTokenType("RBRACE")  # }
        return else_statements

    """
               if(){

               }elif(){

               }else(){

               }
           """

    def if_statement(self):

        elif_statements = []
        else_statements = []

        self.eatCurrentTokenType('KEYWORD')  # if
        self.eatCurrentTokenType("LPAREN")  # (
        # 条件
        condition = self.expr()
        self.eatCurrentTokenType("RPAREN")  # )
        self.eatCurrentTokenType("LBRACE")  # {

        # block statements
        block_statements = []  # 存放if语句块中的语句
        while self.currentTokenType() != 'RBRACE':
            stmt = self.statement()
            block_statements.append(stmt)

        self.eatCurrentTokenType("RBRACE")  # }

        # 解析elif和else语句
        if self.currentTokenValue() == 'elif':
            # print("进入elif语句")
            # 解析elif语句, 可以有多个elif语句
            elif_statements = self.elif_statement()

        if self.currentTokenValue() == 'else':
            # 解析else语句
            else_statements = self.else_statement()
        return IfStatementNode(condition, block_statements, elif_statements, else_statements)

    def break_statement(self):
        self.eatCurrentTokenType('KEYWORD')  # break
        if self.currentTokenType() == 'END':
            self.eatCurrentTokenType("END")  # ;
        return BreakNode()

    def return_statement(self):
        self.eatCurrentTokenType('KEYWORD')  # return
        return_value = self.expr()
        if self.currentTokenType() == 'END':
            self.eatCurrentTokenType("END")  # ;
        return ReturnNode(return_value)

    def loop_statement(self):
        self.eatCurrentTokenType('KEYWORD')  # loop
        self.eatCurrentTokenType("LPAREN")  # (
        # 条件
        condition = self.expr()
        self.eatCurrentTokenType("RPAREN")  # )
        self.eatCurrentTokenType("LBRACE")  # {
        # block statements
        block_statements = []  # 存放if语句块中的语句
        while self.currentTokenType() != 'RBRACE':
            block_statements.append(self.statement())
        self.eatCurrentTokenType("RBRACE")  # }
        return LoopNode(condition, block_statements)

    def let_statement(self):
        """
                let 语句得到的节点就是： name = value;
        """
        # pos会自动移动到下一个token  let是keyword类型
        self.eatCurrentTokenType('KEYWORD')  # let
        name = self.currentTokenValue()  # 变量名
        self.eatCurrentTokenType('ID')
        self.eatCurrentTokenType('ASSIGN')
        value = self.expr()

        # =====================================
        if isinstance(value, FunctionDeclarationNode):
            value.tag = "assignment_value"  # 表示是作为赋值语句的值而已

        # 如果value是作为参数解析传递，应该做一个标记
        if self.currentTokenType() == 'END':
            self.eatCurrentTokenType('END')
        return AssignmentNode(name, value)

    """
        解析赋值语句
    """

    def assignment(self):
        name = self.currentTokenValue()
        self.eatCurrentTokenType('ID')
        self.eatCurrentTokenType('ASSIGN')
        value = self.expr()
        if self.currentTokenType() == 'END':
            self.eatCurrentTokenType('END')
        return AssignmentNode(name, value)

    """
        解析函数调用语句
    """

    def function_call_statement(self):
        # print("function_call_statement")
        self.eatCurrentTokenType('FUNCTION_CALL_PREFIX')  # @
        # 完成
        name = self.currentTokenValue()  # 函数名,ID
        self.eatCurrentTokenType('ID')  # 函数名

        # 尝试解析 @util.add();这样的调用
        if self.currentTokenType() == 'DOT':
            name += '.'
            self.eatCurrentTokenType('DOT')
            name += self.currentTokenValue()
            self.eatCurrentTokenType('ID')

        self.eatCurrentTokenType('LPAREN')  # (

        named_arg_values = {}
        # 解析函数参数
        args = []
        if self.currentTokenType() != 'RPAREN':  # 解析第一个参数
            # =====================解析命名参数==============test=====
            # add(b=1, c=2);
            if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'ASSIGN':
                while self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'ASSIGN':
                    format_param = self.currentTokenValue()  # add(b = 1, c = 2); 中的b
                    self.eatCurrentTokenType('ID')  # add(b = 1, c = 2); 中的b
                    self.eatCurrentTokenType('ASSIGN')  # add(b = 1, c = 2); 中的=
                    named_arg_values[format_param] = self.expr()  # add(b = 1, c = 2); 中的1
                    # 最后一个参数的判断
                    if self.currentTokenType() == 'COMMA':
                        self.eatCurrentTokenType('COMMA')  # ,
                print("passin_arg_values: ", named_arg_values)
            # ==================解析命名参数===============================================
            else:
                # ===================原来的解析方式=======位置参数=================================
                # 函数参数可以是任意表达式，比如1+2, add(), true and true, 1>2, "hello"等
                args.append(self.expr())
                while self.currentTokenType() == 'COMMA':  # 解析多个参数
                    self.eatCurrentTokenType('COMMA')  # ,
                    args.append(self.expr())
                # ===================原来的解析方式========================================
        # 原来这两行代码是和else一个dent的，现在是测试
        self.eatCurrentTokenType('RPAREN')  # )
        self.eatCurrentTokenType('END')  # ;
        return FunctionCallNode(name, args, named_arg_values)

    def function_call_expr(self):
        expr = self.parse_single_function_call()

        # 解析连续的函数调用
        while self.currentTokenType() == 'LPAREN':
            expr = self.parse_single_function_call(expr)

        return expr

    def parse_single_function_call(self, func_expr=None):
        if func_expr is None:
            name = self.currentTokenValue()  # 函数名,ID
            self.eatCurrentTokenType('ID')  # 函数名
        else:
            name = func_expr

        self.eatCurrentTokenType('LPAREN')  # (

        # 解析函数参数，支持位置参数 + 命名参数
        args = []
        named_arg_values = {}
        seen_named = False

        if self.currentTokenType() != 'RPAREN':  # 至少有一个参数
            while True:
                # 命名参数: 形如 x = expr
                if self.currentTokenType() == 'ID' and self.peekNextTokenType() == 'ASSIGN':
                    seen_named = True
                    param_name = self.currentTokenValue()
                    self.eatCurrentTokenType('ID')
                    self.eatCurrentTokenType('ASSIGN')
                    named_arg_values[param_name] = self.expr()
                else:
                    # 一旦出现过命名参数，后面就不允许再出现位置参数
                    if seen_named:
                        raise SyntaxError("Positional arguments cannot follow named arguments")
                    args.append(self.expr())

                if self.currentTokenType() != 'COMMA':
                    break
                self.eatCurrentTokenType('COMMA')  # ,

        self.eatCurrentTokenType('RPAREN')  # )

        # ====================增加的代码=================
        if self.currentTokenType() == 'END':
            self.eatCurrentTokenType('END')

        return FunctionCallNode(name, args, named_arg_values)

    def arithmetic_expr(self):
        """解析加减法表达式，如 a + b、a - b（优先级介于比较运算和乘除法之间）"""
        node = self.term()  # 先解析乘除法
        while self.currentTokenType() in ("PLUS", "MINUS"):
            op = self.currentTokenType()
            self.eatCurrentTokenType(op)
            node = BinaryOpNode(node, op, self.term())
        return node

    def comparison_expr(self):
        """解析比较表达式，如 >, <, == 等"""
        node = self.arithmetic_expr()  # 先解析加减法
        comparison_operators = ("GT", "LT", "GE", "LE", "EQ", "NEQ")
        while self.currentTokenType() in comparison_operators:
            op = self.currentTokenType()
            self.eatCurrentTokenType(op)
            right_node = self.arithmetic_expr()
            node = BinaryOpNode(node, op, right_node)  # 创建比较运算的节点
        return node

    # term就是解析乘法和除法的表达式，比factor优先级高
    # 先调用

    # 返回node 原名叫做expr
    def expr(self):
        # expr要么返回BinaryOpNode, 要么是logical_expr()
        # 调用逻辑表达式解析，这样可以处理AND和OR运算符
        return self.logical_expr()

    """
        解析乘除法
        term优先级比expr高，所以先解析term, 再解析expr
    """

    def term(self):
        """
            在BNF（巴科斯范式）中，term 是表达式解析中的一个中间层级，
            位于 factor 和 expr 之间。term 通常用于表示乘法和除法运算的表达式部分。
            比如：3 * 4  ,而3和4是factor，*是operator
        """
        node = self.factor()  # 先解析factor
        # 放在这里的比expr中的优先级高，所以先解析term
        operators = ("MUL", "DIV", "FLOOR_DIV", "POW", "MOD",  # 乘法和除法运算符
                     "EQ", "NEQ",  # 比较运算符
                     "LT", "GT", "GE", "LE", "NEQ", "EQ"  # 比较运算符
                     )
        while self.currentTokenType() in operators:
            op = self.currentTokenType()  # 获取操作符的类型
            self.eatCurrentTokenType(op)
            node: Node = BinaryOpNode(node, op, self.factor())
        return node

    def logical_expr(self):
        """解析逻辑表达式，处理and和or，AND优先级高于OR"""
        return self.logical_or_expr()
    
    def logical_and_expr(self):
        """解析逻辑与表达式，优先级较高"""
        node = self.not_expr()  # 先解析 not 表达式
        while self.currentTokenType() == 'AND':
            op = self.currentTokenType()  # 获取操作符的类型
            self.eatCurrentTokenType(op)
            right_node = self.not_expr()  # 右侧为 not 表达式
            node = BinaryOpNode(node, op, right_node)  # 形成新的节点
        return node
    
    def logical_or_expr(self):
        """解析逻辑或表达式，优先级较低"""
        node = self.logical_and_expr()  # 先解析 and 表达式
        while self.currentTokenType() == 'OR':
            op = self.currentTokenType()  # 获取操作符的类型
            self.eatCurrentTokenType(op)
            right_node = self.logical_and_expr()  # 右侧为 and 表达式
            node = BinaryOpNode(node, op, right_node)  # 形成新的节点
        return node

    def not_expr(self):
        """解析not表达式"""
        if self.currentTokenType() == 'NOT':
            self.eatCurrentTokenType('NOT')
            operand = self.not_expr()  # 递归解析
            return UnaryOpNode('NOT', operand)  # 创建 UnaryOpNode
        return self.comparison_expr()  # 否则解析比较表达式

    def currentTokenType(self):
        try:
            return self.tokens[self.pos][0]
        except IndexError:
            return None

    def currentTokenValue(self):
        # 获取下一个token的value
        if self.pos <= len(self.tokens) - 1:
            return self.tokens[self.pos][1]
        else:
            return None

    def peekNextTokenType(self):
        # tokens的格式是【(token_type, token_value),(token_type, token_value),...】
        # token_type是字符串, token_value是字符串
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1][0]
        else:
            # 已经到达末尾，返回特殊标记
            return 'EOF'  # End Of File
    def peekNextTokenValue(self):
        # tokens的格式是【(token_type, token_value),(token_type, token_value),...】
        # token_type是字符串, token_value是字符串
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1][1]
        else:
            # 已经到达末尾，返回特殊标记
            return None
    # 判断是不是指定的token_type, 如果是, 则移动pos指针, 如果不是, 则报错
    def eatCurrentTokenType(self, token_type):
        # tokens的格式是【(token_type, token_value),(token_type, token_value),...】
        if self.tokens[self.pos][0] == token_type:
            self.pos += 1
        else:
            print(f"当前token: {self.tokens[self.pos]} 下一个:{self.tokens[self.pos+1]}, 再下一个:{self.tokens[self.pos+2]}")
            raise SyntaxError(f"Expected {token_type} but got {self.tokens[self.pos][0]}={self.tokens[self.pos][1]}")

    def parse_array(self):
        # 回溯
        self.eatCurrentTokenType('LBRACKET')
        # 解析数组元素
        elements = []

        while self.currentTokenType() != 'RBRACKET':
            # elements.append(self.factor())  这个是原来的，factor()只能解析单个元素
            # 数组元素可以是任意表达式，比如1+2, add(), true and true, 1>2, "hello"等
            elements.append(self.expr())
            if self.currentTokenType() == 'COMMA':
                self.eatCurrentTokenType('COMMA')
        self.eatCurrentTokenType('RBRACKET')
        return ListNode(elements)

    def parse_object(self):
        self.eatCurrentTokenType('LBRACE')
        # 解析对象属性
        properties_values = {}
        while self.currentTokenType() != 'RBRACE':
            # 解析属性名
            property_name = self.currentTokenValue()
            # ==================这里限制了key可以的类型=========================
            # self.eatCurrentTokenType('ID')  # 比如"name"
            self.pos += 1  # 跳过ID,从而支持任意类型的key, 建议是ID类型、数字类型、字符串类型
            self.eatCurrentTokenType('COLON')  # :
            # ==================这里限制了value可以的类型==================
            # 解析属性值
            # property_value = self.factor()  # 这个是原来的，factor()只能解析单个元素
            property_value = self.expr()
            properties_values[property_name] = property_value
            if self.currentTokenType() == 'COMMA':  # ,
                self.eatCurrentTokenType('COMMA')
        self.eatCurrentTokenType('RBRACE')

        return ObjectNode(properties_values)

    def index_expr(self):
        node = self.currentTokenValue()  # 解析列表名
        self.eatCurrentTokenType('ID')  # 解析列表名

        while True:
            # 解析列表索引: id[expr] 或者 id[expr1][expr2] 或者切片 id[expr1:expr2]
            if self.currentTokenType() == 'LBRACKET':
                indexes = []
                while self.currentTokenType() == 'LBRACKET':
                    self.eatCurrentTokenType('LBRACKET')  # [
                    start_index = self.expr()  # 解析start_index
                    end_index = None
                    if self.currentTokenType() == 'COLON':  # 解析end_index
                        self.eatCurrentTokenType('COLON')
                        end_index = self.expr()
                    self.eatCurrentTokenType('RBRACKET')  # ]
                    indexes.append((start_index, end_index))

                if len(indexes) == 1:
                    node = ListIndexNode(node, indexes[0][0], indexes[0][1])
                else:
                    node = MultiListIndexNode(node, indexes)

            # 解析属性访问
            elif self.currentTokenType() == 'LBRACE':
                self.eatCurrentTokenType('LBRACE')  # {
                property_name = self.expr()
                self.eatCurrentTokenType('RBRACE')  # }
                node = ObjectIndexNode(node, property_name)

            # 处理链式方法调用
            elif self.currentTokenType() == 'MINUS' and self.peekNextTokenType() == 'GT':
                # 将当前的 node 作为匿名对象传递，支持任意长度的链式调用
                return self.get_member_expr_or_method_call_expr({
                    "name": "anonymous",
                    "val": node
                })
            else:
                break
        return node
    def index_expr2(self):
        node = self.currentTokenValue()  # 解析列表名
        self.eatCurrentTokenType('ID')  # 解析列表名

        while True:
            # 解析列表索引: id[expr] 或者 id[expr1][expr2] 或者切片 id[expr1:expr2]
            if self.currentTokenType() == 'LBRACKET':
                indexes = []
                while self.currentTokenType() == 'LBRACKET':
                    self.eatCurrentTokenType('LBRACKET')  # [
                    start_index = self.expr()  # 解析start_index
                    end_index = None
                    if self.currentTokenType() == 'COLON':  # 解析end_index
                        self.eatCurrentTokenType('COLON')
                        end_index = self.expr()
                    self.eatCurrentTokenType('RBRACKET')  # ]
                    indexes.append((start_index, end_index))

                if len(indexes) == 1:
                    node = ListIndexNode(node, indexes[0][0], indexes[0][1])
                else:
                    node = MultiListIndexNode(node, indexes)

            # 解析属性访问
            elif self.currentTokenType() == 'LBRACE':
                self.eatCurrentTokenType('LBRACE')  # {
                property_name = self.expr()
                self.eatCurrentTokenType('RBRACE')  # }
                node = ObjectIndexNode(node, property_name)

            else:
                break

        return node

    def object_index_expr(self):
        return self.index_expr()  # 直接调用index_expr来处理所有情况

    def prev_token_type(self):
        # 获取前一个token的类型
        return self.tokens[self.pos - 1][0]

    def macro_definition(self):
        """
        解析宏定义:
        1. 简单宏: macro PI => 3.14159;
        2. 参数宏: macro MAX(a, b) => if(a > b) a : b;
        3. 代码块宏: macro repeat(n, body) { ... };
        """
        self.eatCurrentTokenType("KEYWORD")  # macro
        macro_name = self.currentTokenValue()
        self.eatCurrentTokenType("ID")  # 宏名称

        params = []
        
        # 检查是否有参数列表
        if self.currentTokenType() == "LPAREN":
            self.eatCurrentTokenType("LPAREN")  # (
            while self.currentTokenType() != "RPAREN":
                params.append(self.currentTokenValue())
                self.eatCurrentTokenType("ID")
                if self.currentTokenType() == "COMMA":
                    self.eatCurrentTokenType("COMMA")
            self.eatCurrentTokenType("RPAREN")  # )

        # 检查是表达式宏还是代码块宏
        if self.currentTokenType() == "LBRACE":
            # 代码块宏: macro repeat(n) { ... };
            self.eatCurrentTokenType("LBRACE")  # {
            body_statements = []
            while self.currentTokenType() != "RBRACE":
                body_statements.append(self.statement())
            self.eatCurrentTokenType("RBRACE")  # }
            if self.currentTokenType() == "END":
                self.eatCurrentTokenType("END")  # ;
            return BlockMacroNode(macro_name, params, body_statements)
        else:
            # 表达式宏: macro PI => 3.14159;
            # 消费 => 符号（使用 ASSIGN 和 GT）
            if self.currentTokenType() == "ASSIGN":
                self.eatCurrentTokenType("ASSIGN")  # =
                if self.currentTokenType() == "GT":
                    self.eatCurrentTokenType("GT")  # >
            
            # 解析宏体表达式
            body = self.expr()
            if self.currentTokenType() == "END":
                self.eatCurrentTokenType("END")  # ;
            return MacroDefinitionNode(macro_name, params, body)


if __name__ == '__main__':
    code = """
        let book = Book{price: 10};
        printlnRed(book::price);
    """
    tokenizer = Tokenizer(code)
    tokens = tokenizer.tokenize()
    for i in tokens:
        print(i)

    parser = Parser(tokens)
    ast = parser.parse()  # 生成AST, 多个xxNode组成的列表
    for node in ast:
        print(node)
