# lib/uidmap.ncl - UID/GID mapping module
#
# Provides identity mapping configuration with Schema pattern:
# - UID mappings
# - GID mappings
# - Default user/group
# - Passwd/group file generation
#
# Usage:
#   let uidmap = import "./lib/uidmap.ncl" in
#   uidmap.simple 1000 1000 1000 1000  # => uid/gid mapping

# ============================================
# INTERNAL: Schema Definition (hidden from public API)
# Using standard contracts for runtime validation
# ============================================

# UID/GID mapping entry contract
let MappingEntryContract =
  std.contract.from_predicate (fun val =>
    std.is_record val
    && std.record.has_field "inside_id" val
    && std.record.has_field "outside_id" val
    && std.record.has_field "count" val
  )
in

# Array of mapping entries contract
let MappingArrayContract =
  std.contract.from_predicate (fun val =>
    std.is_array val
    && std.array.all MappingEntryContract val
  )
in

let Schema = {
  uidmap | MappingArrayContract,
  gidmap | MappingArrayContract,
  uid | default = "",
  gid | default = "",
}
in

# ============================================
# PUBLIC: Identity Mapping Builders
# ============================================

# Create a simple UID mapping (same inside and outside)
let uid_map_fn = fun inside_id =>
  fun outside_id =>
    {
      inside_id = inside_id,
      outside_id = outside_id,
      count = 1,
    }
in

# Create a GID mapping
let gid_map_fn = fun inside_id =>
  fun outside_id =>
    {
      inside_id = inside_id,
      outside_id = outside_id,
      count = 1,
    }
in

# Create both UID and GID mappings
let id_map_fn = fun inside_id =>
  fun outside_id =>
    {
      uidmap = [
        {
          inside_id = inside_id,
          outside_id = outside_id,
          count = 1,
        }
      ],
      gidmap = [
        {
          inside_id = inside_id,
          outside_id = outside_id,
          count = 1,
        }
      ],
    }
in

# Map a range of IDs
let id_range_fn = fun inside_start =>
  fun outside_start =>
    fun count =>
      {
        inside_id = std.string.from inside_start,
        outside_id = std.string.from outside_start,
        count = count,
      }
in

# ============================================
# PUBLIC: Preset Mappings
# ============================================

# Map root to current user
let map_root_to_user_fn = fun user_id =>
  {
    uidmap = [
      {
        inside_id = "0",
        outside_id = user_id,
        count = 1,
      }
    ],
    gidmap = [
      {
        inside_id = "0",
        outside_id = user_id,
        count = 1,
      }
    ],
  }
in

# Map specific service user
let map_service_user_fn = fun service_name =>
  fun service_id =>
    {
      uidmap = [
        {
          inside_id = service_name,
          outside_id = std.string.from service_id,
          count = 1,
        }
      ],
      gidmap = [
        {
          inside_id = service_name,
          outside_id = std.string.from service_id,
          count = 1,
        }
      ],
    }
in

# Simple setup with numeric IDs
let simple_fn = fun inside_uid =>
  fun inside_gid =>
    fun outside_uid =>
      fun outside_gid =>
        {
          uidmap = [
            {
              inside_id = std.string.from inside_uid,
              outside_id = std.string.from outside_uid,
              count = 1,
            }
          ],
          gidmap = [
            {
              inside_id = std.string.from inside_gid,
              outside_id = std.string.from outside_gid,
              count = 1,
            }
          ],
        }
in

# ============================================
# PUBLIC: Passwd/Group Content Generation
# ============================================
let passwd_content_fn = fun username =>
  fun uid =>
    fun gid =>
      fun home =>
        fun shell =>
          let entry = "%{username}:x:%{uid}:%{gid}:%{username}:%{home}:%{shell}" in
          {
            mount = [
              {
                src_content = entry,
                dst = "/etc/passwd",
              }
            ],
          }
in

let group_content_fn = fun username =>
  fun gid =>
    let entry = "%{username}:x:%{gid}:" in
    {
      mount = [
        {
          src_content = entry,
          dst = "/etc/group",
        }
      ],
    }
in

# ============================================
# PUBLIC: Module Export
# ============================================
{
  # Module structure (following Tweag pattern)
  Module = {
    Schema | not_exported = {},
    config = {
      uid_map = uid_map_fn,
      gid_map = gid_map_fn,
      id_map = id_map_fn,
      id_range = id_range_fn,
      map_root_to_user = map_root_to_user_fn,
      map_service_user = map_service_user_fn,
      passwd_content = passwd_content_fn,
      group_content = group_content_fn,
      simple = simple_fn,
    },
  },

  # Convenience exports (direct access)
  uid_map = uid_map_fn,
  gid_map = gid_map_fn,
  id_map = id_map_fn,
  id_range = id_range_fn,
  map_root_to_user = map_root_to_user_fn,
  map_service_user = map_service_user_fn,
  passwd_content = passwd_content_fn,
  group_content = group_content_fn,
  simple = simple_fn,
}
