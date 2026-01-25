# lib/module.ncl - Nickel Module System for nsjail-configs
#
# Following the Tweag module pattern:
# { Module = { Schema | not_exported = {}, config | Schema } }
#
# Usage:
#   let Module = import "./lib/module.ncl" in
#   let config = Module.merge module1 module2 & { custom = "value" }
#   config
{
  merge = fun left => fun right => left.config & right.config,
  compose_all = fun modules => std.array.fold_left (fun acc => fun mod => acc & mod.config) {} modules,
}
