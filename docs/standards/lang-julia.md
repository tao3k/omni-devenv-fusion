# Julia Language Standards

> **Philosophy**: Multiple dispatch, type stability, performance by default.

## 1. Core Principles

### 1.1 Type Stability (Critical for Performance)
```julia
# ✅ Correct: Type-stable function
function process_data(arr::AbstractVector{Float64})::Float64
    sum(arr) / length(arr)
end

# ❌ Wrong: Type-unstable (returns Any)
function bad_sum(arr)
    s = 0  # Starts as Int
    for x in arr
        s += x
    end
    return s
end
```

### 1.2 Multiple Dispatch
```julia
# ✅ Correct: Extend for new types
process_data(x::String) = parse(Float64, x)
process_data(x::AbstractVector) = mean(x)

# Dispatch based on all argument types
```

### 1.3 Type Annotations
```julia
# Recommended for public APIs
function calculate_metric(data::Vector{Float64}; normalize::Bool=true)::Float64
    ...
end
```

## 2. Forbidden Patterns (Anti-Patterns)

| Pattern | Why | Correct Alternative |
|---------|-----|---------------------|
| `Any` type annotation | Loses dispatch power | Specific types |
| Global variables | Performance killer | Pass as arguments |
| `println` in libraries | Side effects | Return values |
| `using.*` in modules | Namespace pollution | `import` or `using X: a, b` |

## 3. Project Conventions

### 3.1 Package Structure
```
Julia/
├── src/              # Main module code
│   └── MyPackage.jl
├── test/
│   └── runtests.jl
├── docs/             # Documenter.jl
└── Project.toml      # Dependencies
```

### 3.2 Module Pattern
```julia
module MyPackage

import JSON3  # Explicit import
import ..Utilities: helper_function  # Relative import

export process_data, calculate_metric

include("core.jl")
include("utils.jl")

end
```

### 3.3 Performance Tips
```julia
# ✅ Correct: Pre-allocate output
function transform!(output::Vector{Float64}, input::Vector{Float64})
    @inbounds for i in eachindex(input, output)
        output[i] = input[i] * 2
    end
    return output
end

# Use @views to avoid copying
data_view = @view large_array[1:100]
```

## 4. Tool-Specific Notes

### 4.1 Package Management
- Use `]add PackageName` in REPL
- Or `Pkg.add("PackageName")` in scripts
- `Project.toml` for dependencies (not Manifest.toml committed)

### 4.2 Testing
```julia
using Test

@testset "Core functionality" begin
    @test process_data([1.0, 2.0, 3.0]) ≈ 2.0
end
```

### 4.3 Revise Workflow (Development)
```julia
# For iterative development
using Revise
using MyPackage  # Changes auto-reload
```

## 5. Related Documentation

| Document | Purpose |
|----------|---------|
| `Julia/Project.toml` | Package dependencies |
| `Julia/test/runtests.jl` | Test suite |
| `Julia/docs/` | Documentation |
