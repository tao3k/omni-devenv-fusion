# Nickel Language Handbook (LLM Edition)

> **Purpose**: A comprehensive guide for Large Language Models to understand, write, and reason about Nickel code effectively.
> **Based on**: Nickel Lang source code analysis (2026-01-24) and stdlib documentation
> **Prerequisites**: General programming language theory knowledge (types, evaluation strategies, ASTs)

---

## 1. Language Overview

Nickel is a **statically-typed configuration language** with:

| Feature            | Description                                    |
| ------------------ | ---------------------------------------------- |
| **Evaluation**     | Call-by-need (lazy) with memoization           |
| **Type System**    | Hindley-Milner + Row Polymorphism              |
| **Paradigm**       | Functional, pure                               |
| **Primary Use**    | Configuration files, build systems             |
| **Key Innovation** | First-class contracts for runtime verification |

### Design Philosophy

Nickel combines the ergonomics of JSON with:

1. **Type safety** via static typechecking
2. **Abstraction** via functions and let-bindings
3. **Safety nets** via contracts for dynamic checking
4. **Extensibility** via row polymorphism for records

---

## 2. Evaluation Model (Critical for LLM Understanding)

### Call-by-Need (Lazy Evaluation)

Nickel uses **lazy evaluation with memoization**. Understanding this is essential:

```nickel
# This does NOT evaluate `expensive` immediately
let expensive = some_long_computation in
# Evaluates ONCE when first accessed
expensive + 1
# `expensive` is now cached, no recomputation
```

**Key states of a computation (Thunk)**:

```
Suspended → Blackholed → Evaluated
     ↓           ↓            ↓
  Not yet    Currently    Cached result
  evaluated  evaluating   stored
```

**Why Blackholed matters**: Prevents infinite recursion:

```nickel
# Without blackholing, this would loop forever
let rec loop = loop + 1 in loop
# With blackholing: Error - BlackholedError detected
```

### Merge Semantics

Nickel's core operation is **merging records**, which is:

1. **Recursive** - merges nested records
2. **Ordered** - right values override left
3. **Recursive merge** - fields named recursively are merged

```nickel
# Basic merge (right overrides left) - USE & OPERATOR
{ a = 1 } & { a = 2 }  # => { a = 2 }

# Deep merge - & is recursive by default
{ outer = { inner = 1 } } & { outer = { new = 2 } }
# => { outer = { inner = 1, new = 2 } }
```

**IMPORTANT**: The `&` operator is the ONLY merge operator. There is NO `@@` operator!

---

## 3. Type System

### Row Polymorphism

Nickel uses **structural typing with rows** instead of nominal types:

```nickel
# Type of record with at least `name` field
# { name: String | Row }

# Extensible: can add more fields
let x : { name: String | Dyn } = { name = "Nick", extra = 42 } in
x
```

**Row variables** enable parametric polymorphism:

```nickel
# `r` is a row variable - can be any extra fields
let add_field : forall r. { field: Number | r } -> { field: Number | r } =
  fun rec => rec # in
add_field { field = 1, other = 2 }
```

### Unification with Late Binding

Type variables use **delayed constraint resolution**:

1. Type expressions contain `UnifVar` (unification variables)
2. `UnifTable` acts as union-find structure
3. Resolution occurs lazily (better error messages)

```nickel
# Type inferred as `forall a. a -> a` (identity)
let id = fun x => x in id

# Type inferred as `Number` after unification
let x = 1 in x + 1
```

---

## 4. Syntax & AST Architecture

### Dual AST Pattern

Nickel uses **two AST representations**:

| Parser AST                 | Mainline AST                   |
| -------------------------- | ------------------------------ |
| Lightweight                | Full evaluation representation |
| Parse-time only            | Lazy evaluation support        |
| No evaluation dependencies | Contains thunk info            |

**Conversion happens via `FromMainline`/`ToMainline` traits**.

### Arena Allocation

All AST nodes use **arena allocation** for efficiency:

```rust
pub struct AstAlloc<'ast> {
    pub nodes: TypedArena<Node<'ast>>,
    pub strings: TypedArena<String>,
    pub types: TypeAlloc<'ast>,
    pub patterns: PatternAlloc<'ast>,
    pub records: RecordAlloc<'ast>,
}
```

This means AST nodes are **borrowed references**, not owned values.

### Key Syntax Patterns

```nickel
# Let-binding
let <ident> = <expr> in <expr>

# Function
fun <args> => <body>

# Record literal
{ <field>: <expr>, ... }

# Field access
<expr>.<field>

# Merge (recursive) - USE & OPERATOR
<expr> & <expr>

# Type annotation
<expr> : <type>

# Contract application
<expr> | <contract>

# Optional value with default
<expr> ? <default>

# Array concatenation (append element)
array @ [element]

# String concatenation
"hello" ++ " " ++ "world"
```

---

## 5. Contracts (Runtime Verification)

Contracts are **first-class runtime predicates**:

```nickel
# Define a contract using std.contract.custom
let Positive = std.contract.custom (fun _label val =>
  if val > 0 then 'Ok val else 'Error { message = "must be positive" }
) in

# Apply contract
5 | Positive  # => 5
(-3) | Positive  # => Error!

# Record contracts with inline contracts
let ConfigContract = {
  port : Number | std.number.Nat,
  host : String
} in

{ port = 8080, host = "localhost" } | ConfigContract
```

### Contract vs Type

| Aspect      | Types        | Contracts  |
| ----------- | ------------ | ---------- |
| When        | Compile-time | Runtime    |
| Enforcement | Typechecker  | Evaluation |
| Coverage    | Partial      | Full       |
| Performance | Free         | Has cost   |

**Best practice**: Use types for static guarantees, contracts for complex invariants.

---

## 6. Standard Library (std)

**IMPORTANT**: Use `std.` prefix, NOT `builtin.`. There is no `builtin` module!

### std.array - Array Operations

```nickel
# Transform: apply function to each element
std.array.map : forall a b. (a -> b) -> Array a -> Array b
std.array.map (fun x => x + 1) [1, 2, 3]  # => [2, 3, 4]

# Filter: keep elements satisfying predicate
std.array.filter : forall a. (a -> Bool) -> Array a -> Array a
std.array.filter (fun x => x > 1) [1, 2, 3]  # => [2, 3]

# Fold: reduce array to single value
std.array.fold_left : forall a b. (a -> b -> a) -> a -> Array b -> a
std.array.fold_left (fun acc x => acc + x) 0 [1, 2, 3]  # => 6

std.array.fold_right : forall a b. (a -> b -> b) -> b -> Array a -> Array a -> b
std.array.fold_right (fun x acc => x + acc) 0 [1, 2, 3]  # => 6

# Combine arrays
std.array.concat : forall a. Array a -> Array a -> Array a
[1, 2] @ [3, 4]  # => [1, 2, 3, 4]

# Flatten nested arrays
std.array.flatten : forall a. Array (Array a) -> Array a
std.array.flatten [[1, 2], [3, 4]]  # => [1, 2, 3, 4]

# Check conditions
std.array.all : forall a. (a -> Bool) -> Array a -> Bool
std.array.all (fun x => x > 0) [1, 2, 3]  # => true

std.array.any : forall a. (a -> Bool) -> Array a -> Bool
std.array.any (fun x => x < 0) [1, 2, 3]  # => false

# Element checks
std.array.elem : Dyn -> Array Dyn -> Bool
std.array.elem 3 [1, 2, 3, 4]  # => true

# Array length
std.array.length : forall a. Array a -> Number
std.array.length [1, 2, 3]  # => 3

# First/last element
std.array.first : forall a. Array a -> a
std.array.last : forall a. Array a -> a

# Slice array
std.array.slice : forall a. Number -> Number -> Array a -> Array a
std.array.slice 1 3 [0, 1, 2, 3, 4]  # => [1, 2]

# Generate array
std.array.replicate : Number -> a -> Array a
std.array.replicate 3 "x"  # => ["x", "x", "x"]

std.array.range : Number -> Number -> Array Number
std.array.range 0 5  # => [0, 1, 2, 3, 4]

# Sort and partition
std.array.sort : forall a. (a -> a -> [| 'Lesser, 'Equal, 'Greater |]) -> Array a -> Array a
std.array.partition : forall a. (a -> Bool) -> Array a -> { right : Array a, wrong : Array a }
```

### std.record - Record Operations

```nickel
# Map over record fields
std.record.map : forall a b. (String -> a -> b) -> { _ : a } -> { _ : b }
std.record.map (fun key value => value * 2) { a = 1, b = 2 }  # => { a = 2, b = 4 }

# Get field names/values
std.record.fields : forall a. { _ : a } -> Array String
std.record.values : forall a. { _ : a } -> Array a

# Check/remove fields
std.record.has_field : forall a. String -> { _ : a } -> Bool
std.record.remove : forall a. String -> { _ : a } -> { _ : a }

# Get field value (field must exist)
std.record.get : forall a. String -> { _ : a } -> a
std.record.get "name" { name = "Nick" }  # => "Nick"

# Get field or default
std.record.get_or : forall a. String -> a -> { _ : a } -> a
std.record.get_or "port" 8080 { host = "localhost" }  # => 8080

# Insert/update field
std.record.insert : forall a. String -> a -> { _ : a } -> { _ : a }
std.record.update : forall a. String -> a -> { _ : a } -> { _ : a }

# Filter fields by predicate
std.record.filter : forall a. (String -> a -> Bool) -> { _ : a } -> { _ : a }
std.record.filter (fun _ v => v > 0) { a = 1, b = -2 }  # => { a = 1 }

# Convert to/from array
std.record.to_array : forall a. { _ : a } -> Array { field : String, value : a }
std.record.from_array : forall a. Array { field : String, value : a } -> { _ : a }
```

### std.string - String Operations

```nickel
# Join/split strings
std.string.join : String -> Array String -> String
std.string.join ", " ["a", "b", "c"]  # => "a, b, c"

std.string.split : String -> String -> Array String
std.string.split "," "1,2,3"  # => ["1", "2", "3"]

# String manipulation
std.string.trim : String -> String
std.string.contains : String -> String -> Bool
std.string.uppercase : String -> String
std.string.lowercase : String -> String

# Replace
std.string.replace : String -> String -> String -> String
std.string.replace "old" "new" "hello old world"  # => "hello new world"

std.string.replace_regex : String -> String -> String -> String

# Match and convert
std.string.is_match : String -> String -> Bool
std.string.to_number : String -> Number | null

# String length
std.string.length : String -> Number
```

### std.number - Number Operations

```nickel
std.number.min : Number -> Number -> Number
std.number.max : Number -> Number -> Number
std.number.floor : Number -> Number
std.number.ceil : Number -> Number
std.number.round : Number -> Number
std.number.abs : Number -> Number
std.number.div : Number -> Number -> Number  # Integer division
```

### std.contract - Contract Operations

```nickel
# Custom contract
std.contract.custom : (Label -> Dyn -> [| 'Ok Dyn, 'Error { message : String } |]) -> Contract

# From predicate
std.contract.from_predicate : (Dyn -> Bool) -> Contract

# Combinators
std.contract.any_of : Array Contract -> Contract
std.contract.all_of : Array Contract -> Contract
std.contract.not : Contract -> Contract

# Common contracts
std.number.Nat          # Non-negative number
std.number.PosNat       # Positive number
std.string.NonEmpty     # Non-empty string
```

### std.enum - Enum Operations

```nickel
std.enum.is_enum_tag : Dyn -> Bool
```

### Serialization Formats

Nickel supports **multiple export formats**:

```bash
nickel export --format json config.ncl > config.json
nickel export --format yaml config.ncl > config.yaml
nickel export --format toml config.ncl > config.toml
```

**Validation**: Exports reject functions, unevaluated terms, and non-serializable values.

---

## 7. CLI & REPL Commands

### CLI Subcommands

```bash
nickel eval <file.ncl>           # Evaluate and print
nickel typecheck <file.ncl>      # Typecheck only
nickel export <file.ncl>         # Export to JSON/YAML/TOML
nickel query <file.ncl>          # Query fields
nickel repl                       # Interactive REPL
nickel pprint_ast <file.ncl>     # Pretty-print AST
```

### REPL Commands (inside REPL)

```nickel
# REPL special commands
:type <expr>                      # Show type
:query <expr>                     # Query fields
:reset                            # Clear environment
:quit                             # Exit
```

---

## 8. Common Patterns for LLM Code Generation

### Pattern 1: Default Configuration

```nickel
let defaults = {
  port = 8080,
  host = "localhost",
  debug = false,
} in

let user_config = { port = 9090 } in

# Merge with defaults - USE & OPERATOR
defaults & user_config
# => { port = 9090, host = "localhost", debug = false }
```

### Pattern 2: Contract for Validation

```nickel
# Use std.contract.custom or inline contracts
let Port = std.number.Nat | std.contract.from_predicate (fun n => n < 65536) in
{ port = 8080 | Port } & { host = "localhost" }
```

### Pattern 3: Optional Values with Default

```nickel
# Use ? operator for optional values with defaults
let config = {
  port = 8080 ? 8080,  # if port is provided, use it; else default
  host = "localhost",
} in config

# Or use std.record.get_or for record fields
let opts = { host = "example.com" } in
{
  host = opts.host,
  port = std.record.get_or "port" 8080 opts,
}
```

### Pattern 4: Extensible Record Type

```nickel
# Function accepting any record with `name: String`
let greet : forall r. { name: String | r } -> String =
  fun person => "Hello, %{person.name}" in

greet { name = "World", extra = 123 }
```

### Pattern 5: Using stdlib for Data Transformation

```nickel
# Transform an array of records
let users = [{ name = "Alice", age = 30 }, { name = "Bob", age = 25 }] in
std.array.map (fun u => u & { age = u.age + 1 }) users
# => [{ name = "Alice", age = 31 }, { name = "Bob", age = 26 }]

# Filter and collect
let adults = std.array.filter (fun u => u.age >= 18) users in
std.string.join ", " (std.array.map (fun u => u.name) adults)
# => "Alice, Bob"

# Build a record from array
let pairs = [{ field = "a", value = 1 }, { field = "b", value = 2 }] in
std.record.from_array pairs
# => { a = 1, b = 2 }
```

### Pattern 6: Compose Configurations

```nickel
let base_config = {
  host = "localhost",
  port = 8080,
} in

let network_config = {
  timeout = 30,
  retries = 3,
} in

# Combine using &
base_config & network_config
# => { host = "localhost", port = 8080, timeout = 30, retries = 3 }
```

---

## 9. Error Handling

### Common Errors

| Error                   | Cause                              | Solution                            |
| ----------------------- | ---------------------------------- | ----------------------------------- |
| `BlackholedError`       | Infinite recursion in lazy eval    | Break cycle                         |
| `TypeError`             | Type mismatch                      | Add annotation or fix types         |
| `ContractFail`          | Contract violation                 | Check runtime values                |
| `InfiniteRecursion`     | Non-terminating computation        | Optimize or add base case           |
| `Unbound identifier`    | Using `builtin.` instead of `std.` | Use `std.array`, `std.record`, etc. |
| `Unexpected token '@@'` | Using wrong merge operator         | Use `&` instead                     |

### Debugging Tips

```nickel
# There is no built-in print, but you can use contracts for debugging
let debug = fun x =>
  std.contract.custom (fun label value =>
    std.contract.check Number label value
    |> match {
      'Ok _ => 'Ok value,
      'Error e => 'Error e,
    }
  ) in

# Or use type annotations to force evaluation
let force_eval = fun x : Number => x in
```

---

## 10. Type System Details for LLM Reasoning

### Type Inference Algorithm

1. **Walk AST** generating constraints
2. **Collect unification variables** (`UnifVar`)
3. **Run union-find** on type variables
4. **Resolve constraints** to concrete types

### Subtyping with Rows

```
{ a: Number | r } <: { a: Number }    # Subtype has fewer fields
{ a: Number, b: String | r } <: { a: Number }  # OK if b extra
```

### Type Annotations

```nickel
# Explicit type annotation
let x : Number = 5 in x

# Function type
let add : Number -> Number -> Number =
  fun a => fun b => a + b in

# Record type
let person : { name: String, age: Number } =
  { name = "Nick", age = 1 } in
```

---

## 11. Mental Model Summary

When writing Nickel, think:

1. **Values are lazy** - computation defers until needed
2. **Records are extensible** - types can have extra fields
3. **Merge is recursive** - `&` merges deeply (ONLY use `&`, never `@@`)
4. **Contracts validate** - runtime safety net
5. **Types check statically** - compile-time guarantees
6. **Use stdlib** - always use `std.` prefix for standard library functions

### Quick Reference

```nickel
# Core operations
let x = expr in body          # Binding
fun args => body              # Function
{ field: value }              # Record
rec.field                     # Access
a & b                         # Recursive merge (USE & ONLY)
expr ? default                # Optional with default
array @ [element]             # Append to array
"a" ++ "b"                   # String concatenation
expr : Type                   # Annotation
expr | Contract               # Contract check

# Standard library (ALWAYS use std. prefix)
std.array.map f arr
std.record.get field rec
std.string.join sep parts
std.contract.custom ...
```

---

## 12. When to Use Nickel

**Good for**:

- Configuration files
- Build system configurations
- Data templates with validation
- Multi-format export (JSON/YAML/TOML)

**Not ideal for**:

- General-purpose programming
- Performance-critical code
- Imperative algorithms

---

## 13. File Extension & Tooling

| Artifact         | Extension                 |
| ---------------- | ------------------------- |
| Source files     | `.ncl`                    |
| REPL output      | Plain text/JSON/YAML/TOML |
| Type annotations | Inline with `:`           |

---

## 14. Common Mistakes to Avoid

| Mistake                       | Correct Approach                   |
| ----------------------------- | ---------------------------------- |
| Using `builtin.` prefix       | Use `std.` (e.g., `std.array.map`) |
| Using `@@` for merge          | Use `&`                            |
| Using `++` for array concat   | Use `@` (e.g., `arr @ [x]`)        |
| Using `builtin.string.concat` | Use `++` for strings               |
| Using `builtin.fold`          | Use `std.array.fold_left`          |
| Using `default` contract      | Use `?` operator                   |

---

## Summary

Nickel is a pragmatic configuration language that brings static types and contracts to configuration management. Key takeaways:

1. **Lazy evaluation** with memoization enables recursive definitions
2. **Row polymorphism** provides extensible structural typing
3. **Contracts** offer runtime verification for complex invariants
4. **Merge with `&`** is the core composition operator
5. **Use `std.` prefix** for all standard library functions
6. **Multiple export formats** make it versatile for different tools

This handbook should enable any LLM to write, understand, and debug Nickel code effectively.
