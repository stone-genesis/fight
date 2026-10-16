# -*- coding: utf-8 -*-
"""Fight language regression test suite.

Run from project root:
    python -m unittest tests.test_language -v
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interpreter.Tokenizer import Tokenizer
from interpreter.Parser import Parser
from interpreter.Evaluator import Evaluator


def run_fight(code):
    tokens = Tokenizer(code).tokenize()
    ast = Parser(tokens).parse()
    ev = Evaluator()
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        for node in ast:
            ev.evaluate(node)
        return out.getvalue()
    finally:
        sys.stdout = old


def run_fight_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return run_fight(f.read())


class FeatureTests(unittest.TestCase):
    def check(self, code, expected):
        self.assertEqual(run_fight(code).strip(), expected)

    def test_arithmetic(self):
        self.check('println(2 ^ 10, 7 // 2, 7 % 3, 7.5 / 2.5);', "1024 3 1 3.0")

    def test_string_interp(self):
        self.check('let w = "Fight"; println("hi ${w}!");', "hi Fight!")

    def test_logic(self):
        self.check('println(1 < 2 and 3 >= 3, True or False, not False, !True);', "True True True False")

    def test_list_dict_destruct(self):
        self.check(
            'let m = [1,2,3]; m->append(4); let d = {a: 1}; d{"b"} = 2; '
            'let [x, _, y] = [10, 20, 30]; let {p, q} = {p: 5, q: 6}; '
            'println(m->length(), d{"b"}, x, y, p, q);',
            "4 2 10 30 5 6",
        )

    def test_functions(self):
        self.check(
            'def f(a, b = 5, ...rest) { let s = a + b; for(r in rest){ s += r; } return s; } '
            'println(f(1), f(1, 2), f(1, 2, 3, 4));',
            "6 3 10",
        )

    def test_named_args(self):
        self.check('def f(a, b) { return a * 10 + b; } println(f(b = 3, a = 4));', "43")

    def test_one_line_fn(self):
        self.check('def sq(x) => return x * x; println(sq(5));', "25")

    def test_lambda_anonymous(self):
        self.check('let l = lambda x: x + 1; let a = def(x){ return x * 10; }; println(l(5), a(5));', "6 50")

    def test_recursion(self):
        self.check('def fib(n){ if(n < 2){ return n; } return fib(n-1) + fib(n-2); } println(fib(10));', "55")

    def test_higher_order(self):
        self.check('def sq(x){ return x * x; } def ap(f, v){ return f(v); } println(ap(sq, 6));', "36")

    def test_function_combination(self):
        self.check('def a(x) => return x + 1; def b(x) => return x * 2; let p = a & b; println(p(5));', "12")

    def test_macro(self):
        self.check('macro PI => 3.14; macro MAX(x, y) => if(x > y) x : y; println(PI, MAX(3, 5));', "3.14 5")

    def test_for_range(self):
        self.check('for(i: 1..3){ print(i); } println();', "123")

    def test_for_range_step(self):
        self.check('for(i: 1..5 step 2){ print(i); } println();', "135")

    def test_for_range_step_desc(self):
        self.check('for(i: 10..1 step 3){ print(i); } println();', "10741")

    def test_for_range_step_var(self):
        self.check('let s = 2; for(i: 0..6 step s){ print(i); } println();', "0246")

    def test_for_range_float_step(self):
        self.check('for(i: 0.0..1.0 step 0.5){ println(i); }', "0.0\n0.5\n1.0")

    def test_for_range_dotdot(self):
        self.check('for(i: 0..5){ print(i); } println();', "012345")

    def test_for_range_dotdot_desc(self):
        self.check('for(i: 5..1){ print(i); } println();', "54321")

    def test_while_loop(self):
        self.check('let n = 0; while(n < 3){ n += 1; } println(n);', "3")

    def test_while_break(self):
        self.check('let n = 0; while(n < 10){ n += 1; if(n == 3){ break; } } println(n);', "3")

    def test_for_in(self):
        self.check('for(v in ["a", "b"]){ print(v); } println();', "ab")

    def test_loop(self):
        self.check('let n = 0; loop(n < 3){ n += 1; } println(n);', "3")

    def test_struct_enum(self):
        self.check('struct P { x, y } let p = P{x: 1, y: 2}; p::x = 9; enum C { R, G } println(p::x, enum::C::G);', "9 G")

    def test_class_inheritance(self):
        self.check(
            'class A { fields { X = "a"; } methods { def W(){ return this->X; } } init(){} } '
            'class B extends A { init(){} } let b = new B(); println(b->W());',
            "a",
        )

    def test_operator_overload(self):
        self.check(
            'class N { fields { V = 0; } operators { def plus(o){ return new N(this->V + o->V); } } '
            'methods { def ToString(){ return "N(" + this->V + ")"; } } init(v){ this->V = v; } } '
            'println(new N(2) + new N(3));',
            "N(5)",
        )

    def test_switch_match(self):
        self.check('let w = match(3){ 1 => "one", 2, 3 => "two", else => "other" }; println(w);', "two")

    def test_comments_and_fullwidth(self):
        self.check('println("A"); # comment with fullwidth punctuation\nlet z = （1 + 2）;\nprintln(z);', "A\n3")

    def test_return_in_for(self):
        self.check('def f(){ for(i: 1..5){ if(i == 4){ return i; } } return 0; } println(f());', "4")

    def test_return_in_loop(self):
        self.check('def f(){ let n = 0; loop(n < 10){ n += 1; if(n == 5){ return n; } } return 0; } println(f());', "5")

    def test_elif_return(self):
        self.check(
            'def f(n){ if(n == 1){ return "one"; } elif(n == 2){ return "two"; } else { return "other"; } } '
            'println(f(2));',
            "two",
        )


class ClosureTests(unittest.TestCase):
    def check(self, code, expected):
        self.assertEqual(run_fight(code).strip(), expected)

    def test_return_closure(self):
        self.check('def compose(f, g){ return def(x){ return f(g(x)); }; } def d(x){ return x * 2; } def e(x){ return x + 1; } let c = compose(d, e); println(c(5));', "12")

    def test_closure_factory(self):
        self.check('def makeAdder(n){ return def(x){ return x + n; }; } let add5 = makeAdder(5); let add100 = makeAdder(100); println(add5(10), add100(10));', "15 110")

    def test_nested_closure(self):
        self.check('def outer(a){ return def(b){ return def(c){ return a + b + c; }; }; } let g = outer(1); let f = g(2); println(f(3));', "6")

    def test_closure_write(self):
        self.check('let count = 0; def next(){ count = count + 1; return count; } next(); next(); println(count);', "2")

    def test_closure_accumulate(self):
        self.check('let total = 0; def add(n){ total = total + n; } add(5); add(10); println(total);', "15")

    def test_shadowing(self):
        self.check('let x = 10; def f(){ let x = 20; return x; } println(f(), x);', "20 10")

    def test_param_pass_by_value(self):
        self.check('def f(x){ x = 999; return x; } let a = 1; println(f(a), a);', "999 1")

    def test_map_closure(self):
        self.check('def mk(k){ return def(x){ return x * k; }; } let nums = [1, 2, 3]; println(nums->map(mk(10)));', "[10, 20, 30]")


class ChainedAccessTests(unittest.TestCase):
    def check(self, code, expected):
        self.assertEqual(run_fight(code).strip(), expected)

    def test_currying_call(self):
        self.check('def add(x){ return def(y){ return x + y; }; } println(add(1)(2));', "3")

    def test_func_return_list_index(self):
        self.check('def getList(){ return [10, 20, 30]; } println(getList()[1]);', "20")

    def test_index_then_call(self):
        self.check('def makeFns(){ return [def(x){ return x+1; }, def(x){ return x*2; }]; } println(makeFns()[1](5));', "10")

    def test_func_return_obj_index(self):
        self.check('def getObj(){ return {name: "Fight", age: 3}; } println(getObj(){"name"});', "Fight")

    def test_full_chain(self):
        self.check('def make(){ return [def(x){ return {result: x * 10}; }]; } println(make()[0](5){"result"});', "50")

    def test_nested_dict_chain(self):
        self.check('def getData(){ return {user: {profile: {id: 42}}}; } println(getData(){"user"}{"profile"}{"id"});', "42")


class ModuleTests(unittest.TestCase):
    def check(self, code, expected):
        self.assertEqual(run_fight(code).strip(), expected)

    def test_import_math(self):
        self.check('import math; println(math.sqrt(16), math.pow(2, 3));', "4.0 8.0")

    def test_import_json(self):
        self.check('import json; println(json.parse(\'{"a": 1}\'));', "{'a': 1}")


class SmokeTests(unittest.TestCase):
    def test_showcase_runs(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        run_fight_file(os.path.join(root, "demo", "showcase.fight"))


if __name__ == "__main__":
    unittest.main(verbosity=2)