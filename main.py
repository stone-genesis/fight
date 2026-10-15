from interpreter.Parser import Parser
from interpreter.Evaluator import Evaluator
from interpreter.Tokenizer import Tokenizer

if __name__ == '__main__':
    # 读取测试文件
    code = """
           def testIf(x){
                if(x==1){
                    return 1;
                }else{
                    return 2;
                }
           }
           print(testIf(3));
    """
    # 测试： ReadText,Exists
    print("=================tokenizer======================\n")
    # 词法分析
    tokenizer = Tokenizer(code)
    tokens = tokenizer.tokenize()
    for i in tokens:
        print(i)
    print("=================parser========================\n")
    # 语法分析
    parser = Parser(tokens)
    ast = parser.parse()  # 生成AST, 多个xxNode组成的列表
    print("AST: ")
    for node in ast:
        print(node)
    # 求值器
    evaluator = Evaluator()
    print("=================evaluator=====================\n")
    try:
        for node in ast:
            r = evaluator.evaluate(node)
        
        print("\n=================执行完成=====================")
    except Exception as e:
        print(f"\n=================发生错误=====================")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        import traceback
        traceback.print_exc()