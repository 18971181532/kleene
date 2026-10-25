# Kleene · 线性时间正则引擎与自动机可视化工作台

> 一个**零依赖、纯 Python 标准库**实现的正则表达式引擎：把正则编译成 **Thompson NFA**，再用 **Pike 线程虚拟机**（线性时间、支持捕获组、无灾难性回溯）执行，同时提供 **子集构造 DFA** 与一个暗色 Canvas 六标签可视化工作台。

Kleene 既能像 `re` 一样作为库使用（`search/match/fullmatch/findall/split/sub`），也能通过命令行与浏览器**逐步观察一个正则表达式是如何被解析、编译、执行的**：AST 结构、NFA 状态机、DFA 子集构造、Pike VM 逐字符的活跃线程集合，以及“回溯引擎指数级 vs Kleene 线性”的真实性能对照。

---

## 为什么需要它

Python 自带的 `re`、Perl、PCRE 等主流正则引擎采用**回溯（backtracking）**。回溯引擎表达力强，但在某些写法下会触发灾难性回溯（ReDoS），时间复杂度退化为指数级：

```
模式 (a+)+b   作用于  "a"*n  （永远匹配不到结尾的 b）

回溯引擎 re :  n ≈ 20 时已经接近亚秒级，n 稍大就彻底挂起
Kleene      :  n = 200000 时毫秒级返回（线性时间）
```

Kleene 采用与 Google RE2 相同的思路：**不回溯，而是在 NFA 上同时推进所有可能的线程**。每个输入字符只做一次 ε-闭包，整体时间复杂度严格为 **O(n)**，永远不会挂起；并且通过给每个线程挂上“捕获槽（save slots）”，在保持线性的同时**支持捕获组**。

---

## 核心特性

- **完整流水线**：正则文本 → AST（递归下降）→ Thompson NFA（ε 边 + 字符边）→ Pike VM / 子集构造 DFA。
- **线性时间执行**：Pike 线程虚拟机，支持捕获组，无灾难性回溯。
- **贪婪 / 惰性 / 交替优先级**：通过 NFA split 边的顺序与线程优先级列表，精确还原 `re` 的最左匹配语义。
- **DFA 子集构造**：缓存闭包与 move，构造确定性 DFA，用于无捕获快速路径与可视化。
- **完整 API**：`search / match / fullmatch / findall / finditer / split / sub / trace / explain / nfa_graph / dfa_graph`。
- **CLI**：`kleene match/findall/groups/split/sub/explain/trace/nfa/dfa/bench/serve`，多数子命令支持 `--json`，标志位 `-f i|s|m`。
- **可视化工作台**：暗色原生 Canvas，六个标签页，无需构建（纯 HTML/CSS/JS）：
  1. **匹配 Build**：实时高亮、统计卡、捕获明细
  2. **NFA 自动机**：Thompson NFA，ε 边虚线、字符边带标签，播放滑块逐帧高亮当前活跃线程
  3. **DFA 子集构造**：节点标注其 NFA 状态子集
  4. **执行追踪 Trace**：逐字符的活跃状态集合 / 到达的 accept end
  5. **线性时间基准**：灾难性回溯与普通模式的对数坐标对照图
  6. **语法速查**：支持的语法与明确边界
- **零第三方依赖**：仅用 Python 标准库（`http.server`、`argparse`、`unittest`），兼容 Python 3.9–3.12。

---

## 支持的语法

| 语法 | 含义 |
| --- | --- |
| `a z 0` | 普通字面量 |
| `.` | 任意字符（`s` 标志下包含换行） |
| `[abc]`、`[a-z]`、`[^0-9]` | 字符类、范围、取反 |
| `\d \w \s` 与 `\D \W \S` | 数字 / 单词 / 空白 及取反 |
| `* + ? {n} {n,} {n,m}` | 量词，默认贪婪 |
| `*? +? ?? {n,m}?` | 惰性（最短）量词 |
| `ab|cd` | 交替，从左到右优先 |
| `(...)` | 捕获组（submatch） |
| `(?:...)` | 非捕获组 |
| `^ $` | 行首 / 行尾（`m` 标志逐行） |
| `\b \B` | 单词边界 / 非边界 |
| `\t \n \r \f \v \xHH \uHHHH` | 转义字符 |
| 标志 `i` / `s` / `m` | 忽略大小写 / 点号匹配换行 / 多行 |

### 明确不支持（与 RE2 一致的边界）

- **反向引用** `\1 … \9`：反向引用不属于正则语言，会破坏 NFA/DFA 模型；解析时**显式报错**。
- **Lookaround** `(?=…)` / `(?!…)`、原子组 `(?>…)`、条件表达式：暂不支持。
- **对“可为空的子表达式”再次量词化**（如 `(a?)*`、`(.*?)+`）的零宽重复计数，在极端边界下可能与 Python `re` 不同；但引擎**始终线性、不会挂起**。这与 RE2 对该类模式的立场一致。

> 除上述边界外，Kleene 在“量词作用于非空（non-nullable）子表达式”的完整实用子集上与 Python `re` 行为一致；项目内置差分对拍测试（`tests/test_fuzz.py`，固定随机种子）与近万条随机对拍验证。

---

## 安装

```bash
git clone https://github.com/18971181532/kleene.git
cd kleene
python -m pip install -e .
```

仅依赖 Python 标准库，`requires-python >= 3.9`。

---

## 命令行使用

```bash
# 查找所有匹配（输出 span 与匹配文本）
kleene match '(\d{4})-(\d{2})-(\d{2})' 'today is 2026-10-25 ok'
# 9:19  '2026-10-25'

# 查看捕获组
kleene groups '(\d{4})-(\d{2})-(\d{2})' 'today is 2026-10-25 ok'
# [9, 19]  ('2026', '10', '25')

# 枚举所有匹配
kleene findall '\w+' 'hello world 42'

# 替换（支持 \1 与 \g<0> 引用）
kleene sub '(\d+)' '[\1]' 'a1 b22'

# 分割
kleene split '\s+' 'a  b c'

# 整体匹配 / 前缀匹配
kleene fullmatch '\d+' '42'

# 查看 AST 与 NFA/DFA 统计（--json 输出结构）
kleene explain '(a|b)+c?\d+'

# 逐字符执行追踪（Pike VM 线程）
kleene trace 'a+b?' 'aab'

# 导出 NFA / DFA 图（JSON）
kleene nfa 'ab'
kleene dfa 'ab'

# 线性时间基准（对照 Python re）
kleene bench

# 忽略大小写
kleene match -f i 'abc' 'xABCy'

# 直接读文件（第二个参数若为文件路径则读文件，否则当字面量）
kleene match '\d+' access.log
```

也可以不安装直接用模块方式运行：`python -m kleene.cli match 'a+' 'aaa'`。

---

## 可视化工作台

```bash
kleene serve                 # 默认 http://127.0.0.1:8856
kleene serve --port 9000     # 自定义端口
```

浏览器打开后，在顶部输入正则、标志位与文本，页面会实时：

- 高亮所有匹配、列出捕获明细；
- 渲染 Thompson NFA，点击播放或拖动滑块，逐字符点亮当前活跃的 NFA 状态（对应 Pike VM 的一组线程），ε 边以虚线、回溯边绕到下方；
- 渲染子集构造 DFA，节点标注其包含的 NFA 状态子集；
- 给出逐字符的执行追踪表；
- 在「线性时间基准」标签中，对比 `(a+)+b` 在 `a*n` 上 re（指数，n>20 后停止统计以免挂起）与 Kleene（线性）的耗时。

---

## 作为库使用

```python
from kleene import Regex

rx = Regex(r'(\d{4})-(\d{2})-(\d{2})')
m = rx.search('date 2026-10-25')
print(m.groups())          # ('2026', '10', '25')
print(m.span(1))           # (5, 9)

print(Regex(r'\d+').findall('a1 b22 c3'))     # ['1', '22', '3']
print(Regex(r'\s+').split('a  b c'))          # ['a', 'b', 'c']
print(Regex(r'\d+').sub('#', 'a1 b22'))       # 'a# b#'

# 线性时间：回溯引擎在这类模式上会指数级挂起
assert Regex('(a+)+b').search('a' * 200000) is None
```

---

## 工作原理

1. **解析（`ast.py`）**：递归下降解析器，按「交替 → 连接 → 重复 → 原子」生成 AST，同时统计捕获组编号。
2. **字符集（`charset.py`）**：用归一化、可合并的闭区间表示字符类，支持取反、并集、大小写折叠。
3. **Thompson 构造（`compiler.py` + `nfa.py`）**：每个子表达式编译成带 ε 边与字符边的小 NFA；贪婪/惰性由 split 边的发射顺序编码；捕获组用 Save 槽（`2g` 开、`2g+1` 关），整个匹配外包 group 0。
4. **Pike 虚拟机（`vm.py`）**：在每个输入位置做一次有序 ε-闭包，得到“当前所有活跃线程”。线程按优先级有序排列，各自携带捕获槽，从而同时还原贪婪/惰性与交替优先级；对每个字符只做一次状态转移，整体 **O(n)**。
5. **子集构造（`dfa.py`）**：以 NFA 状态集合为 DFA 状态，缓存闭包与 move，幂集 BFS 展开，提供确定性 `fullmatch` 与渲染图；含零宽断言的模式退回 VM。
6. **高层 API（`engine.py`）**、**CLI（`cli.py`）** 与 **本地 HTTP 服务 / 工作台（`server.py` + `web/`）**。

---

## 基准

```bash
kleene bench
```

灾难性回溯 `(a+)+b`（`a*n`，对数纵轴）：Kleene 随 n 线性增长并可延伸到 n=800、200000；Python `re` 在 n≈20 已接近亚秒级上限，之后不再统计以免挂起。普通模式 `\d+` 下两者都为线性、性能接近。

---

## 运行测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖：字符集、解析器、Thompson 编译、Pike VM（贪婪/惰性/捕获/空匹配/锚点/断言）、DFA 等价、完整引擎 API、CLI 子命令、HTTP 服务，以及与 Python `re` 的**确定性差分对拍**与线性时间回归。

---

## 目录结构

```
kleene/
├── kleene/                 # 引擎与服务包
│   ├── __init__.py         # 公共 API（Regex / compile / ParseError）
│   ├── charset.py          # 字符集：闭区间、取反、并集、大小写折叠
│   ├── ast.py              # AST 节点与递归下降解析器
│   ├── nfa.py              # NFA 状态模型、图导出与分层布局
│   ├── compiler.py         # Thompson NFA 构造（含捕获槽与断言）
│   ├── vm.py               # Pike 线程虚拟机（线性时间 + 捕获组）
│   ├── dfa.py              # NFA→DFA 子集构造
│   ├── engine.py           # 高层 API：search/findall/split/sub/...
│   ├── bench.py            # 线性时间基准（对照 Python re）
│   ├── cli.py              # 命令行入口
│   ├── __main__.py
│   ├── server.py           # 本地 HTTP 服务（JSON API + 静态资源）
│   └── web/                # 暗色 Canvas 工作台（无构建）
│       ├── index.html
│       ├── style.css
│       └── app.js
├── tests/                  # stdlib unittest 全量测试 + 差分对拍
├── examples/
│   └── extract.py          # 从日志提取时间戳/IP/邮箱/状态码示例
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## 许可证

[MIT](LICENSE) © 2026 遥か
