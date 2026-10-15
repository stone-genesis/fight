"""Fight 语言脚本运行器：python run.py <file.fight>"""
import sys
import traceback

from interpreter.Tokenizer import Tokenizer
from interpreter.Parser import Parser
from interpreter.Evaluator import Evaluator


def run(path: str) -> None:
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    tokens = Tokenizer(code).tokenize()
    ast = Parser(tokens).parse()
    evaluator = Evaluator()
    for node in ast:
        evaluator.evaluate(node)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python run.py <file.fight>")
        sys.exit(1)
    try:
        run(sys.argv[1])
        print("\n================= 执行完成 =================")
    except Exception as e:
        print(f"\n================= 发生错误 =================")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        traceback.print_exc()
        sys.exit(1)
