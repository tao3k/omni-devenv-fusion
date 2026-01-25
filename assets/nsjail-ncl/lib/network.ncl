# lib/network.ncl - Network configuration module
#
# Provides network isolation options with Schema pattern:
# - clone_newnet: New network namespace
# - clone_newuser: New user namespace
# - user_net: User-mode networking (pasta-like)
# - macvlan: MACVLAN networking
#
# Usage:
#   let network = import "./lib/network.ncl" in
#   network.pasta  # => user-mode networking config

# ============================================
# INTERNAL: Schema Definition (hidden from public API)
# Using standard contracts for runtime validation
# ============================================

# Boolean contract
let BoolContract = std.contract.from_predicate (fun val => std.is_bool val) in

# String contract
let StringContract = std.contract.from_predicate (fun val => std.is_string val) in

# Number contract
let NumberContract = std.contract.from_predicate (fun val => std.is_number val) in

# UserNet record contract
let UserNetContract =
  std.contract.from_predicate (fun val =>
    std.is_record val
    && std.record.has_field "enable" val
    && std.is_bool val.enable
  )
in

let Schema = {
  clone_newnet | BoolContract | default = false,
  clone_newuser | BoolContract | default = false,
  clone_newpid | BoolContract | default = false,
  clone_newns | BoolContract | default = false,
  user_net | UserNetContract,
  macvlan_iface | StringContract | default = "",
  macvlan_vs_ip | StringContract | default = "",
  macvlan_vs_nm | StringContract | default = "",
  macvlan_vs_gw | StringContract | default = "",
}
in

# ============================================
# PUBLIC: Network Isolation Options
# ============================================

# Enable new network namespace (full isolation)
let network_namespace = {
  clone_newnet = true,
  clone_newuser = true,
  clone_newpid = true,
  clone_newns = true,
}
in

# Disable networking (no network access)
let no_network = {
  clone_newnet = false,
  clone_newuser = false,
}
in

# ============================================
# PUBLIC: User-Mode Networking (pasta-like)
# ============================================
let user_net_fn = fun opts =>
  let ipaddr = std.record.get_or "ipaddr" "172.17.0.1" opts in
  let ipv6addr = std.record.get_or "ipv6addr" "" opts in
  let keep_addr = std.record.get_or "keep_addr" 0 opts in
  {
    clone_newnet = false,
    user_net = {
      enable = true,
      inet4_addr = ipaddr,
      inet6_addr = ipv6addr,
      keep_addr = keep_addr,
    },
  }
in

let user_net_default = {
  clone_newnet = false,
  user_net = {
    enable = true,
    inet4_addr = "172.17.0.1",
    inet6_addr = "",
    keep_addr = 0,
  },
}
in

# ============================================
# PUBLIC: MACVLAN Networking
# ============================================
let macvlan_fn = fun opts =>
  {
    macvlan_iface = opts.iface,
    macvlan_vs_ip = opts.ip,
    macvlan_vs_nm = opts.netmask,
    macvlan_vs_gw = opts.gateway,
  }
in

# ============================================
# PUBLIC: DNS Configuration
# ============================================
let dns_fn = fun nameservers =>
  let content = std.string.join "\n" nameservers ++ "\n" in
  {
    mount = [
      {
        src_content = content,
        dst = "/etc/resolv.conf",
      }
    ],
  }
in

let dns_google = dns_fn ["nameserver 8.8.8.8", "nameserver 8.8.4.4"] in
let dns_cloudflare = dns_fn ["nameserver 1.1.1.1", "nameserver 1.0.0.1"] in

# ============================================
# PUBLIC: Preset Network Configurations
# ============================================

# Full isolation (new network namespace)
let isolated = network_namespace in

# No networking (most restrictive)
let disabled = no_network in

# User-mode networking (pasta)
let pasta = user_net_default in

# MACVLAN (shared physical network)
let macvlan_shared_fn = fun iface =>
  fun ip =>
    macvlan_fn { iface = iface, ip = ip, netmask = "255.255.255.0", gateway = "" }
in

# ============================================
# PUBLIC: Module Export
# ============================================
{
  # Module structure (following Tweag pattern)
  Module = {
    Schema | not_exported = {},
    config = {
      network_namespace = network_namespace,
      no_network = no_network,
      user_net = user_net_fn,
      user_net_default = user_net_default,
      macvlan = macvlan_fn,
      dns = dns_fn,
      dns_google = dns_google,
      dns_cloudflare = dns_cloudflare,
      isolated = isolated,
      disabled = disabled,
      pasta = pasta,
      macvlan_shared = macvlan_shared_fn,
    },
  },

  # Convenience exports (direct access)
  network_namespace = network_namespace,
  no_network = no_network,
  user_net = user_net_fn,
  user_net_default = user_net_default,
  macvlan = macvlan_fn,
  dns = dns_fn,
  dns_google = dns_google,
  dns_cloudflare = dns_cloudflare,
  isolated = isolated,
  disabled = disabled,
  pasta = pasta,
  macvlan_shared = macvlan_shared_fn,
}
