# Omni-Edit vs Omni-AST: 技术职责对比

> 基于代码库的结构分析，`omni-edit` 和 `omni-ast` 是 Omni-Dev Fusion 架构中两个职责截然不同但紧密协作的 Rust Crate。

简单来说：**`omni-ast` 是"眼睛和大脑"（负责理解代码结构），而 `omni-edit` 是"手术刀"（负责精准修改文本）。**

---

## 1. Omni-AST (Abstract Syntax Tree Engine)

**定位：代码结构分析与理解引擎**

它的核心任务是**"读懂"**代码，而不是把代码看作一堆字符。它利用 AST（抽象语法树）来解析代码的语法结构。

### 核心职责

- **解析 (Parsing)**：使用 `tree-sitter` 将源代码解析为语法树。
- **提取 (Extraction)**：识别并提取函数、类、导入（Imports）、装饰器等高层语义结构。
- **定位 (Navigation)**：回答"`User` 类定义在哪里？"或者"`main` 函数的结束行是多少？"这类问题。
- **多语言支持**：通过 `lang.rs` 和适配器（如 `python.rs`）支持不同编程语言的语法差异。

### 输入与输出

| 类型         | 描述                                                                                                |
| ------------ | --------------------------------------------------------------------------------------------------- |
| **输入**     | 源代码字符串                                                                                        |
| **输出**     | 结构化数据（如 `FunctionItem`, `ClassItem`），包含名称、参数、文档字符串、字节范围（Byte Ranges）等 |
| **底层技术** | `tree-sitter`                                                                                       |

### 核心模块

```
packages/rust/crates/omni-ast/src/
├── lib.rs           # 主入口和公共 API
├── lang.rs          # 语言检测和选择
├── extractor.rs     # 符号提取器 (TagExtractor)
├── patterns.rs      # ast-grep 模式定义
├── types.rs         # SymbolKind, Symbol, SearchMatch 等类型
└── error.rs         # 错误处理
```

---

## 2. Omni-Edit (Text Editing Engine)

**定位：原子化文本操作与编辑引擎**

它的核心任务是**"修改"**文本，确保编辑操作是安全、原子（Atomic）且可逆的。它并不关心文本是 Python 代码还是小说，它只关心行号、字节偏移和字符串替换。

### 核心职责

- **缓冲区管理 (Buffer Management)**：高效地加载和操作内存中的文本内容。
- **原子操作 (Atomic Operations)**：支持事务性的编辑（Transaction），例如"同时修改第10行和第50行，要么都成功，要么都失败"。
- **差异计算 (Diffing)**：生成 Unified Diff 补丁，用于展示修改预览。
- **应用补丁 (Applying Edits)**：执行具体的 Insert, Delete, Replace 操作。

### 输入与输出

| 类型         | 描述                                                                       |
| ------------ | -------------------------------------------------------------------------- |
| **输入**     | 源代码字符串 + 编辑指令（如 `Replace(start=10, end=20, text="new_code")`） |
| **输出**     | 修改后的新代码字符串、Diff 文本                                            |
| **底层技术** | 自定义的 Rope 或行向量结构（用于高效文本处理），类似于文本编辑器的后端逻辑 |

### 核心模块

```
packages/rust/crates/omni-edit/src/
├── lib.rs           # 主入口和公共 API
├── editor.rs        # StructuralEditor 核心实现
├── batch.rs         # 批量编辑引擎 (The Ouroboros)
├── types.rs         # EditConfig, EditLocation, EditResult
├── capture.rs       # 变量捕获替换 ($NAME, $$$)
├── diff.rs          # Unified Diff 生成
└── error.rs         # EditError
```

---

## 核心区别对比表

| 特性           | omni-ast (理解层)                 | omni-edit (操作层)                 |
| -------------- | --------------------------------- | ---------------------------------- |
| **视角**       | **结构视角** (函数、类、变量)     | **文本视角** (行、列、字节、字符)  |
| **能力**       | Read-Only (主要负责分析和查询)    | Read/Write (主要负责增删改)        |
| **典型操作**   | "找到函数 `run` 的起始和结束位置" | "将第 5 行到第 10 行替换为 `pass`" |
| **错误类型**   | 解析错误 (Syntax Error)           | 越界错误 (Index Out of Bounds)     |
| **依赖**       | `tree-sitter`                     | `similar` (用于 Diff), 标准库 I/O  |
| **Rust Crate** | `packages/rust/crates/omni-ast`   | `packages/rust/crates/omni-edit`   |

---

## 它们如何协作？ (The Workflow)

在 **Structural Refactoring** 场景中，两者是这样配合的：

### 场景：将所有 `print(x)` 改成 `logger.info(x)`

1. **用户指令**："把所有 `print(x)` 改成 `logger.info(x)`"

2. **Step 1 (`omni-ast`)**：
   - Agent 调用 `omni-ast`
   - `omni-ast` 解析代码，找到所有 `print` 函数调用的 AST 节点
   - 返回位置信息列表：
     ```
     [{start_byte: 100, end_byte: 110, content: "print(a)"}, ...]
     ```

3. **Step 2 (Python 逻辑层)**：
   - Python 层的 Skill 接收到位置信息
   - 生成替换文本 `logger.info(a)`
   - 构建 `BatchEdit` 请求

4. **Step 3 (`omni-edit`)**：
   - Agent 将源代码和 `BatchEdit` 请求传给 `omni-edit`
   - `omni-edit` 检查修改是否冲突（例如重叠的范围）
   - `omni-edit` 执行替换，生成最终的代码字符串

### 时序图

```
┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────┐
│  User   │     │ Python Skill │     │  omni-ast   │     │ omni-   │
│         │     │              │     │             │     │ edit    │
└────┬────┘     └──────┬───────┘     └──────┬──────┘     └────┬────┘
     │                 │                     │                 │
     │ "print→logger"  │                     │                 │
     │────────────────>│                     │                 │
     │                 │  find_calls("print")│                 │
     │                 │────────────────────>│                 │
     │                 │  [{pos, content}]   │                 │
     │                 │<────────────────────│                 │
     │                 │  build_batch_edit() │                 │
     │                 │          │          │                 │
     │                 │          ▼          │                 │
     │                 │  apply_edits(src,   │                 │
     │                 │              batch) │                 │
     │                 │───────────────────────────────────────>
     │                 │                 │      new_src + diff │
     │                 │<───────────────────────────────────────
     │                 │                     │                 │
     │  new_code       │                     │                 │
     │<────────────────│                     │                 │
```

---

## 总结

| 问题                       | 答案                                      |
| -------------------------- | ----------------------------------------- |
| `omni-ast` 回答什么问题？  | **Where** - "改哪里？"（找到目标位置）    |
| `omni-edit` 回答什么问题？ | **How** - "怎么改？"（执行具体操作）      |
| 两者关系？                 | `omni-ast` 提供坐标，`omni-edit` 执行修改 |

**`omni-ast` 告诉我们改哪里，`omni-edit` 负责怎么改。**
