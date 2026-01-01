# Changelog
All notable changes to this project will be documented in this file. See [conventional commits](https://www.conventionalcommits.org/) for commit guidelines.

- - -
## [v1.4.0](https://github.com/tao3k/omni-devenv-fusion/compare/v1.3.0..v1.4.0) - 2026-01-01
#### Features
- (**docs**) add modular stress test framework specification - ([1ce76c5](https://github.com/tao3k/omni-devenv-fusion/commit/1ce76c5ab17372d4f1737b3fac1bf60f33400dc5)) - guangtao

- - -

## [v1.2.0](https://github.com/tao3k/omni-devenv-fusion/compare/f869d85de10377cea9de095d67420719a4702704..v1.2.0) - 2025-12-31
#### Features
- (**mcp**) complete dual-server architecture with Phase 3 features - ([8f64a16](https://github.com/tao3k/omni-devenv-fusion/commit/8f64a1690ed4ef812920093fe148b92c42eef0ed)) - guangtao
- (**mcp**) add delegate_to_coder bridge tool (Phase 2) - ([75f5c8f](https://github.com/tao3k/omni-devenv-fusion/commit/75f5c8fc9fc7709d97fc6148d5d8152b6ee7c1ac)) - guangtao
- (**mcp**) add micro-level tools and safety enhancements - ([207a104](https://github.com/tao3k/omni-devenv-fusion/commit/207a104b922fb8b7228134b56e315629bf69c76b)) - guangtao
- (**mcp**) add save_file tool for write capabilities (Phase 3) - ([c99444f](https://github.com/tao3k/omni-devenv-fusion/commit/c99444f544280363053d25e8f5421b0cbdfee308)) - guangtao
- (**mcp**) add list_directory_structure tool for token optimization - ([d6aff17](https://github.com/tao3k/omni-devenv-fusion/commit/d6aff17e8198be3dfdd214aca1f11feb19994af9)) - guangtao
- allow orchestrator env from json file - ([a33406e](https://github.com/tao3k/omni-devenv-fusion/commit/a33406e3793ee1e844bfd7097b518c1e9f20f11e)) - GuangTao Zhang
#### Bug Fixes
- correct dmerge import and lefthook commands path in lefthook.nix - ([fb9c84e](https://github.com/tao3k/omni-devenv-fusion/commit/fb9c84e4f5eaba7cbbdd5ef939b68b0b1007b1f1)) - guangtao
#### Documentation
- update CLAUDE.md with new tools and fix passive voice - ([2a7d657](https://github.com/tao3k/omni-devenv-fusion/commit/2a7d6573454361898df42f50c17dd29c834c9ee5)) - guangtao
- add writing standards system with internalization - ([ba7e69c](https://github.com/tao3k/omni-devenv-fusion/commit/ba7e69c103433033b899529a5b5014ccf9031ee7)) - guangtao
#### Tests
- (**mcp**) add comprehensive test suite for all MCP tools - ([83b5d3f](https://github.com/tao3k/omni-devenv-fusion/commit/83b5d3fce1d70e165fcb1de6bd969d603db283a3)) - guangtao
#### Refactoring
- (**mcp**) extract shared library mcp_core for dual-server architecture - ([5e69232](https://github.com/tao3k/omni-devenv-fusion/commit/5e692325ee1a69782b5d8f937e97455e04353b83)) - guangtao
- (**mcp**) split into dual-server architecture (Phase 1) - ([7102bc1](https://github.com/tao3k/omni-devenv-fusion/commit/7102bc1cef3c5ed6cf1841959bdeb121bebbb240)) - guangtao
#### Miscellaneous Chores
- (**mcp**) add Coder server tests and fix ast-grep commands - ([651e087](https://github.com/tao3k/omni-devenv-fusion/commit/651e087978eda5fcbcd69b624f8c20f4943772c7)) - guangtao
- (**mcp**) remove orphaned personas.py (moved to mcp_core/inference.py) - ([7ce721b](https://github.com/tao3k/omni-devenv-fusion/commit/7ce721b7373c908a0f74cd59c1669e53a2325722)) - guangtao
- follow numtide/prj-spec for project directories - ([476ff03](https://github.com/tao3k/omni-devenv-fusion/commit/476ff0397ce91aac67167183cc91bf7fd8486f49)) - guangtao
- add mcp test commands and infrastructure - ([e524acf](https://github.com/tao3k/omni-devenv-fusion/commit/e524acfbd013dd4eda643832596d42d0593b6a6e)) - guangtao
- add omnibus devenv inputs filtering example to tool-router - ([4ad856c](https://github.com/tao3k/omni-devenv-fusion/commit/4ad856cd2bdaf8cbeb23c2b360c2b4d56564b9aa)) - guangtao
- add tool-router example protocol to CLAUDE.md - ([5fb4a41](https://github.com/tao3k/omni-devenv-fusion/commit/5fb4a410121155d005ec4d50431186c2a04b4e22)) - guangtao
- add tool-router with nix edit protocol examples - ([7baed74](https://github.com/tao3k/omni-devenv-fusion/commit/7baed74dc682ac920f4dee307f80b0b8db5af5bc)) - guangtao
- add mcp debug commands to justfile - ([9ea9030](https://github.com/tao3k/omni-devenv-fusion/commit/9ea9030d6cc0404251be14d0af17d0307296c287)) - guangtao
- sync with release - ([f869d85](https://github.com/tao3k/omni-devenv-fusion/commit/f869d85de10377cea9de095d67420719a4702704)) - guangtao

- - -

## [v1.1.0](https://github.com/tao3k/omni-devenv-fusion/compare/d538b85ae40a885f5ce5dadc11e2498bfa6b8a05..v1.1.0) - 2025-12-30
#### Features
- rename repo to omni-devenv-fusion with MiniMax integration - ([a0f3c18](https://github.com/tao3k/omni-devenv-fusion/commit/a0f3c186aef0854a4fbb7ce057599fce595a1140)) - guangtao
#### Bug Fixes
- remove unsupported --no-pager flag from cog commands - ([afebf9b](https://github.com/tao3k/omni-devenv-fusion/commit/afebf9bea484b97725911650b37d10e8e4f37e9c)) - guangtao
- stage all files before commit to capture hook changes - ([c27abcf](https://github.com/tao3k/omni-devenv-fusion/commit/c27abcfbdaf4fb03e86bebb1fcbdef57c2fa7b4f)) - guangtao
#### Documentation
- improve README with full secretspec providers and acknowledgments - ([60c6699](https://github.com/tao3k/omni-devenv-fusion/commit/60c6699ed47ab887879263cac90dc7fe81ca4b52)) - guangtao
- rewrite README with Orchestrator workflow and SRE health checks - ([fa0ddd8](https://github.com/tao3k/omni-devenv-fusion/commit/fa0ddd821d9cde0d21bc56944a1c3145f35385b0)) - guangtao
- update module structure documentation - ([80e2486](https://github.com/tao3k/omni-devenv-fusion/commit/80e2486fd868a71f21658ee0db710e8628f36482)) - guangtao
- add secretspec setup documentation with 1Password integration - ([7ff15c6](https://github.com/tao3k/omni-devenv-fusion/commit/7ff15c6426efe5094369b38f327a847d248b3eb2)) - guangtao
#### Refactoring
- reorganize nix modules into modules/ directory - ([24422c9](https://github.com/tao3k/omni-devenv-fusion/commit/24422c972a382abe2bf51947e9d4232d26e88069)) - guangtao
#### Miscellaneous Chores
- stage local settings - ([1ba2b44](https://github.com/tao3k/omni-devenv-fusion/commit/1ba2b44dbc9a711a09dd3910baaf34bbf559746e)) - guangtao
- update project name references to omni-devenv-fusion - ([ccde25e](https://github.com/tao3k/omni-devenv-fusion/commit/ccde25e0b74f1be32285c5443e91b4bce51a42ef)) - guangtao
- formalize agent workflow with SRE health checks - ([7841d2d](https://github.com/tao3k/omni-devenv-fusion/commit/7841d2dc3dfdf28344174da84c5955b049070642)) - guangtao
- sync with release - ([d538b85](https://github.com/tao3k/omni-devenv-fusion/commit/d538b85ae40a885f5ce5dadc11e2498bfa6b8a05)) - guangtao

- - -

## [v1.0.0](https://github.com/tao3k/devenv-native/compare/5215ac951e138bb1d52350beedb0ff1381da9ed1..v1.0.0) - 2025-12-29
#### Features
- change claude to MINIMAX_2.0 - ([7bce13c](https://github.com/tao3k/devenv-native/commit/7bce13c9219b8707f6d36cae8615f2aec047edde)) - guangtao
- add justfile  workflow - ([acb2090](https://github.com/tao3k/devenv-native/commit/acb2090c7be92f4d01a1b4f9cc990e17108b0819)) - guangtao
- add cog - ([571d78d](https://github.com/tao3k/devenv-native/commit/571d78d6eeea60483c4619c71b1cda58449849ac)) - guangtao
- add cog - ([00b9ca7](https://github.com/tao3k/devenv-native/commit/00b9ca7a0a540dc6dd1002d074a50276da5ee217)) - guangtao
- test lefthook - ([9c2d502](https://github.com/tao3k/devenv-native/commit/9c2d502f2301d93e6c55a634bf4bc8b9e8e0d9c9)) - guangtao
#### Bug Fixes
- make the cog.toml to copy mode - ([bb1d057](https://github.com/tao3k/devenv-native/commit/bb1d0570808107f2408ea6525a8a8862cf3d3c01)) - guangtao
#### Documentation
- init README - ([3291c44](https://github.com/tao3k/devenv-native/commit/3291c4402a2fa92300066709624f243d56686c6a)) - guangtao
#### Tests
- add claude test - ([f5a7cbd](https://github.com/tao3k/devenv-native/commit/f5a7cbdde71724d3d51b14e2c647ba7c05c871c3)) - guangtao
#### Miscellaneous Chores
- (**claude**) add claude.md - ([58031b3](https://github.com/tao3k/devenv-native/commit/58031b38a249a003d45c27282882a698402ef0c5)) - guangtao
- (**version**) v0.1.0 - ([4f6723e](https://github.com/tao3k/devenv-native/commit/4f6723e48a3efc8cb8ae731be3d8770125ae4ef8)) - guangtao
- init - ([5215ac9](https://github.com/tao3k/devenv-native/commit/5215ac951e138bb1d52350beedb0ff1381da9ed1)) - guangtao

- - -

## [v0.1.0](https://github.com/tao3k/devenv-native/compare/092dd9f6e36f86f8abf0a3466988540dfe847621..v0.1.0) - 2025-12-28
#### Features
- add cog - ([1a1f3c9](https://github.com/tao3k/devenv-native/commit/1a1f3c9aeca05f7eb49171a12bacf301e01a070f)) - guangtao
- add cog - ([38fc0f3](https://github.com/tao3k/devenv-native/commit/38fc0f39858f766db037a19f0fbe52e6dbe53032)) - guangtao
- test lefthook - ([c15f6f6](https://github.com/tao3k/devenv-native/commit/c15f6f6646b3195ac2ffcd8a8a710fd7725f838c)) - guangtao
#### Tests
- add claude test - ([a572568](https://github.com/tao3k/devenv-native/commit/a5725684684aebbf9fdc4a4dab3d31a8ae3c9ae3)) - guangtao
#### Miscellaneous Chores
- (**claude**) add claude.md - ([1ceb7ee](https://github.com/tao3k/devenv-native/commit/1ceb7ee87de17765d01e3820451907f7e3d9d9a0)) - guangtao
- initial commit - ([092dd9f](https://github.com/tao3k/devenv-native/commit/092dd9f6e36f86f8abf0a3466988540dfe847621)) - guangtao

- - -

Changelog generated by [cocogitto](https://github.com/cocogitto/cocogitto).