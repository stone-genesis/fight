# Fight

一门用 Python 编写、**零第三方依赖**的解释型编程语言。语法简洁现代，同时融合了函数式与面向对象两种范式，内置宏系统、运算符重载、结构体、枚举与模块系统，并且对中文十分友好。

```text
println("Hello, Fight!");
```

---

## ✨ 特性

- 🧩 **极简语法** —— `let` 声明变量、`def` 定义函数、`{}` 代码块，尽量少写样板。
- 🔢 **完整类型** —— 整数、浮点、字符串、布尔、列表 `[]`、字典 `{}`。
- ⚙️ **现代运算符** —— 幂 `^`、整除 `//`、取余 `%`，逻辑 `and / or / not` 与 `&& / || / !`。
- 🧠 **函数式** —— 高阶函数、闭包、匿名函数、`lambda`、函数组合 `&`、递归。
- 🪄 **宏系统** —— 常量宏、参数宏、代码块宏，用宏扩展语言本身。
- 🏛️ **面向对象** —— 类、`init` 构造、继承 `extends`、接口 `implements`、`super`、静态成员。
- ➕ **运算符重载** —— 让自定义类型支持 `+ - * / ==` 等运算符。
- 📦 **结构体 & 枚举** —— `struct` / `enum`。
- 🧱 **模块系统** —— `import`、别名、选择性导入、`exports`，附带一批内置标准库。
- 🎯 **丰富控制流** —— `if/elif/else`、三元表达式、`loop`、`while`、`for-in`、`for-range`、`do-while`、`switch`、`match`。
- 🈶 **中文友好** —— 中文注释、全角括号/冒号、字符串内插 `${}`。

---

## 🚀 快速开始

### 环境要求

- Python **3.9+**
- 无需安装任何第三方依赖

### 运行

```bash
git clone <你的仓库地址>
cd <仓库名>

# 运行特性巡礼脚本
python run.py demo/showcase.fight

# 运行任意脚本
python run.py demo/macro_usage.fight

# 查看解释器内部的 词法分析 → 语法分析 → 求值 流程
python main.py
```

`run.py` 用法：`python run.py <文件路径>`

---

## 📖 语法速览

### 变量、常量与字符串内插

```text
let name = "Fight";
const VERSION = "1.0";
let pi = 3.14159;

println("你好，${name}！版本 ${VERSION}");
```

### 运算符

```text
println(2 ^ 10);     # 1024    幂
println(7 // 2);     # 3       整除
println(7 % 3);      # 1       取余
println(1 < 2 and 3 >= 3);   # True
println(not False, !True);   # True False
```

### 函数：默认参数、可变参数、命名参数、一句话函数

```text
def add(x, y) { return x + y; }
def greet(who = "World") {
    return "Hello, " + who + "!";
}
def sum_all(a, b, ...rest) {
    let total = a + b;
    for(item in rest) { total += item; }
    return total;
}
def square(x) => return x * x;   # 一句话函数

println(add(1, 2));                      # 3
println(greet());                        # Hello, World!
println(sum_all(1, 2, 3, 4, 5));         # 15
println(square(6));                      # 36
println(add(x = 3, y = 4));              # 7  命名参数
```

### 高阶函数、lambda 与函数组合

```text
def square(x) => return x * x;            # 供 apply 使用
let inc = def(x){ return x + 1; };        # 匿名函数
let twice = lambda x: x * 2;              # lambda

def apply(f, x) { return f(x); }
println(apply(square, 9));                # 81

let pipeline = inc & twice;               # 函数组合：先 inc 再 twice
println(pipeline(5));                     # 12
```

### 闭包与柯里化

```text
# 闭包：函数记住定义时的环境
def makeAdder(n) {
    return def(x) { return x + n; };
}
let add5 = makeAdder(5);
let add10 = makeAdder(10);
println(add5(3), add10(3));              # 8 13

# 闭包读写外部变量（计数器）
def makeCounter() {
    let count = 0;
    return def() {
        count = count + 1;
        return count;
    };
}
let counter = makeCounter();
counter();
counter();
println(counter());                      # 3

# 柯里化：多参数函数拆成一串单参数函数
def add(x) {
    return def(y) { return x + y; };
}
let addOne = add(1);
println(addOne(100));                     # 101

# 多层柯里化
def multiply(a) {
    return def(b) {
        return def(c) { return a * b * c; };
    };
}
let m = multiply(2);
let m2 = m(3);
println(m2(4));                           # 24
```

### 宏

```text
macro PI => 3.14159;
macro MAX(x, y) => if(x > y) x : y;
macro AREA(r) => PI * r * r;

println(MAX(10, 20));                    # 20
println(AREA(5));                        # 78.53975

macro repeat(times, body) {              # 代码块宏
    for(k: 1..times) { body; }
};
repeat(3, println("hello from macro!"));
```

### 控制流

```text
# if / elif / else
let score = 86;
if(score >= 90) { println("A"); }
elif(score >= 80) { println("B"); }
else { println("C"); }

# 三元表达式
let age = 20;
let stage = if(age >= 18) "adult" : "minor";

# for-range（支持 step 和小数步长） / for-in / loop / while / do-while
for(i: 1..5) { println("i = ${i}"); }

for(i: 1..5 step 2) { println("i = ${i}"); }   # 1 3 5

let fruits = ["apple", "banana"];
for(f in fruits) { println(f); }

let n = 0;
loop(n < 3) { n += 1; }

let m = 0;
while(m < 3) { m += 1; }

do { n -= 1; } while(n > 0)

# switch / match
switch(2) {
    case (1) { println("one"); }
    default  { println("other"); }
}
let word = match(3) { 1 => "one", 2, 3 => "two or three", else => "other" };
```

### 数据结构与解构

```text
let nums = [1, 2, 3];
nums->append(4);
println(nums->length());                  # 4
println(nums[0]);                         # 1

let user = {name: "Alice", age: 25};
println(user{"name"});                    # Alice
user{"age"} = 26;

let [first, _, second] = [10, 20, 30];    # 列表解构
let {x, y} = {x: 3, y: 4};                # 字典解构
```

### 结构体与枚举

```text
struct Point { x, y }
let p = Point{x: 10, y: 20};
println(p::x, p::y);                      # 10 20
p::x = 99;

enum Color { RED, GREEN, BLUE }
let c = enum::Color::GREEN;
println(c);                               # GREEN
```

### 类：字段、构造、方法、继承、运算符重载

```text
class Vector {
    fields {
        X = 0;
        Y = 0;
    }
    operators {
        def plus(other) { return new Vector(this->X + other->X, this->Y + other->Y); }
        def multiply(k) { return new Vector(this->X * k, this->Y * k); }
    }
    methods {
        def ToString() { return "Vector(${this->X}, ${this->Y})"; }
    }
    init(x, y) { this->X = x; this->Y = y; }
}

let v1 = new Vector(3, 4);
let v2 = new Vector(1, 2);
println(v1 + v2);                          # Vector(4, 6)
println(v1 * 2);                           # Vector(6, 8)

class Animal {
    fields { Name = "animal"; }
    methods { def Speak() { return "..." + this->Name; } }
    init() {}
}
class Dog extends Animal {
    init() { super(); this->Name = "dog"; }
}
let dog = new Dog();
println(dog->Speak());                     # ...dog
```

### 接口、注解与异常

```text
interface Shape {
    Area();
    PI = 3.14;
}

@annotation(id = 1, tag = "demo")
def annotated(a) { return a; }

try {
    let x = 1 / 0;
} catch(ZeroDivisionError) {
    println("捕获到除零错误");
} finally {
    println("清理");
}
```

### 模块系统

```text
import math;                 # 导入整个内置模块
println(math.sqrt(16));      # 4.0

import math as m;            # 别名导入
println(m.pow(2, 3));        # 8.0

import json;
let obj = json.parse('{"name": "Alice"}');
println(json.stringify(obj));
```

自定义模块：在文件末尾用 `exports` 声明导出内容，然后 `import` 使用。

```text
# utils.fight
def helper() { return 100; }
let version = "1.0";
exports = ["helper", "version"]
```

```text
# 主文件
import "utils.fight" as utils;
println(utils.helper());
```

---

## 📚 内置标准库

`interpreter/builtin/` 下自带的模块，均可直接 `import`：

| 模块 | 说明 |
|------|------|
| `math` | 数学函数：`sqrt` `pow` `factorial` `sin/cos/tan` `log` `gcd` `lcm` `pi` 等 |
| `json` | JSON 解析与生成：`parse` `stringify` `getVal` `setVal` `keys` 等 |
| `list` | 列表高阶函数：`any` `none` `all` `filter` |
| `random` | 随机数 |
| `time` | 时间相关 |
| `file` / `folder` | 文件与目录操作 |
| `stack` / `queue` | 栈与队列 |
| `uuid` | 唯一标识符 |
| `reflect` | 运行时反射（类型检查、字段/方法元数据） |
| `platform` | 平台信息 |

---

## 🗂 项目结构

```
.
├── main.py                 # 演示入口：词法分析 → 语法分析 → 求值
├── run.py                  # 脚本运行器：python run.py <file.fight>
├── interpreter/            # 解释器核心
│   ├── Tokenizer.py        #   词法分析器
│   ├── Parser.py           #   语法分析器（生成 AST）
│   ├── Evaluator.py        #   求值器
│   ├── Node.py / Nodes.py  #   节点定义
│   ├── OOP.py              #   面向对象相关
│   ├── ClassNodes.py       #   类相关节点
│   ├── MacroNodes.py       #   宏相关节点
│   ├── ModuleNodes.py      #   模块相关节点
│   ├── builtin/            #   内置标准库（*.fight）
│   └── utils/              #   运行时工具类
├── tests/                  # 单元测试（python -m unittest tests.test_language）
└── demo/                   # 示例脚本（showcase.fight 特性巡礼 + 各特性示例）
```

---

## 🧪 测试

```bash
# 运行特性巡礼
python run.py demo/showcase.fight

<<<<<<< HEAD
# 运行单元测试（48 个用例）
=======
# 运行单元测试（42 个用例）
>>>>>>> 57ab2c9642067e05831b53e52f0bdb3eee2b3b51
python -m unittest tests.test_language -v
```

`demo/` 目录下有递归、继承、运算符重载、函数组合、注解、宏等 20 余个示例。

---

## 📄 License

（请在仓库中添加你选择的许可证文件，例如 `LICENSE`）
