# lib/modules.ncl - Module composition system for nsjail configurations
#
# Inspired by Nix module system design:
# - Import mechanism
# - Module composition via merge
# - Default configuration pattern
# - Conditional module inclusion

# ============================================
# Module Import
# ============================================

# Note: Nickel uses top-level imports, not dynamic imports.
# Import modules directly in your .ncl file:
#   let mode = import "./lib/mode.ncl" in
#   let mounts = import "./lib/mounts.ncl" in

# Static import helpers (for documentation purposes)
let import_lib = fun name =>
  std.contract.custom
    (fun label value =>
      'Error { message = "Use 'import \"./lib/%{name}.ncl\"' at top level instead" }
    )
    null
in

# Import an example
let import_example = fun name =>
  std.contract.custom
    (fun label value =>
      'Error { message = "Use 'import \"./examples/%{name}.ncl\"' at top level instead" }
    )
    null
in

# ============================================
# Module Composition Operators
# ============================================

# Compose two modules (left overrides right)
let compose = fun left =>
  fun right =>
    left & right
in

# Merge a list of modules
let merge_all = fun modules =>
  std.array.fold_left (fun a => fun b => a & b) {} modules
in

# ============================================
# Default Configuration Pattern
# ============================================

# Create a default configuration with optional overrides
let make_default = fun defaults =>
  fun overrides =>
    defaults & overrides
in

# ============================================
# Conditional Module Inclusion
# ============================================

# Include a module only if condition is true
let conditional = fun condition =>
  fun module =>
    if condition then module else {}
in

# Include a module with a value
let when = fun cond =>
  fun value =>
    fun module =>
      if cond then (module & { value = value }) else module
in

# ============================================
# Layer Composition
# ============================================

# Base layer (always included)
let base = fun config =>
  config
in

# Security layer
let security = fun config =>
  config
  & {
    no_new_privs = true,
    keep_caps = false,
  }
in

# Network layer
let with_network = fun config =>
  config
  & {
    clone_newnet = true,
  }
in

# ============================================
# Module Builder
# ============================================

# Build a complete nsjail config from modules
let build = fun modules =>
  merge_all modules
in

# ============================================
# Template System
# ============================================

# Create a template with placeholders
let template = fun name =>
  {
    name = name,
    mode = "ONCE",
    hostname = "NSJAIL",
    mount = [],
    envar = [],
    cap = [],
    uidmap = [],
    gidmap = [],
    rlimit_as = 0,
    rlimit_fsize = 0,
    rlimit_nofile = 64,
    time_limit = 0,
  }
in

# ============================================
# Exports
# ============================================
{
  import_lib = import_lib,
  import_example = import_example,
  compose = compose,
  merge_all = merge_all,
  make_default = make_default,
  conditional = conditional,
  when = when,
  base = base,
  security = security,
  with_network = with_network,
  build = build,
  template = template,
}
