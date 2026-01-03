# Changelog
All notable changes to this project will be documented in this file. See [conventional commits](https://www.conventionalcommits.org/) for commit guidelines.

- - -
## [v2.1.0](https://github.com/tao3k/omni-dev-fusion/compare/519ca61209ba79baff7840a95beabfaaaf928c1e..v2.1.0) - 2026-01-03
#### Features
- (**mcp-core**) add rich terminal output utilities for beautiful MCP server startup - ([055ecb5](https://github.com/tao3k/omni-dev-fusion/commit/055ecb5b1f5bf985656cc4e3217b55fa9206a5d3)) - guangtao
- (**mcp-server**) add test scenario loading from MD files for smart_commit - ([223bc64](https://github.com/tao3k/omni-dev-fusion/commit/223bc64cac5cb38b460dec5c4e251d12a215bed0)) - guangtao
- (**orchestrator**) increase timeout and add API key config fallback - ([a022d29](https://github.com/tao3k/omni-dev-fusion/commit/a022d29808b27c409a9538122fd5cbd7f0805183)) - guangtao
#### Documentation
- (**docs**) add rag usage guide and documentation standards - ([8b9ae1d](https://github.com/tao3k/omni-dev-fusion/commit/8b9ae1dcc301557345612a05a2e2c4d2ba2b4ee9)) - guangtao
- (**docs**) docs: rewrite README with Tri-MCP architecture and SDLC workflow - ([49daf7c](https://github.com/tao3k/omni-dev-fusion/commit/49daf7c13e0ee3305782cf85ac18bfb456f23470)) - guangtao
#### Miscellaneous Chores
- (**git-ops**) add git commit rule warning to claude.md - ([19e9cf3](https://github.com/tao3k/omni-dev-fusion/commit/19e9cf3dbe797f961e439ca14ab728ec59f613ac)) - guangtao
- migrate to GitOps + Phase 11 Authorization Flow - ([3cb339c](https://github.com/tao3k/omni-dev-fusion/commit/3cb339c7de6f9708ba0a44302afef8316afb159d)) - guangtao
- sync with release - ([519ca61](https://github.com/tao3k/omni-dev-fusion/commit/519ca61209ba79baff7840a95beabfaaaf928c1e)) - guangtao

- - -

## [v2.0.0](https://github.com/tao3k/omni-dev-fusion/compare/e5782f7f9e3fc3dd11615b87d7432a83295735d0..v2.0.0) - 2026-01-02
#### Features
- (**docs**) add documentation workflow with check_doc_sync enhancement - ([938ce63](https://github.com/tao3k/omni-dev-fusion/commit/938ce633b4b8e94b0e3f2d76df926fa4ec1de8ef)) - guangtao
- (**docs**) docs: add design philosophy and memory loading patterns - ([771cc78](https://github.com/tao3k/omni-dev-fusion/commit/771cc7875b7ea14aadf52e32852c9cf2a468990f)) - guangtao
- (**git-ops**) add GitWorkflowCache auto-load and workflow protocol in responses - ([1b60ce3](https://github.com/tao3k/omni-dev-fusion/commit/1b60ce32809efd7e7c2bc7b69cb7d03f81f4e594)) - guangtao
- (**git-workflow**) enforce authorization protocol at code level - ([adf1f64](https://github.com/tao3k/omni-dev-fusion/commit/adf1f645ac6f1da70052df25470f2222118d3d5a)) - guangtao
- (**mcp**) add start_spec gatekeeper with auto spec_path tracking - ([ba31318](https://github.com/tao3k/omni-dev-fusion/commit/ba313183df614b3cd726a42f5cde5a2eb147de8c)) - guangtao
- (**mcp**) add Actions Over Apologies principle with auto-loaded problem-solving.md - ([a5212ce](https://github.com/tao3k/omni-dev-fusion/commit/a5212ce96354016f2da4c3b8ee5106d69955cda2)) - guangtao
- (**orchestrator**) upgrade Hive to v3 Antifragile Edition with auto-healing - ([bfd29a8](https://github.com/tao3k/omni-dev-fusion/commit/bfd29a8f59bed1494b553c315f65f076023788ca)) - guangtao
- (**orchestrator**) add hive architecture for distributed multi-process execution - ([5d91418](https://github.com/tao3k/omni-dev-fusion/commit/5d9141888bbb7dccf37eae2cfc7db67d09611965)) - guangtao
#### Bug Fixes
- (**mcp-server**) remove duplicate polish_text tool definition - ([58c1a5e](https://github.com/tao3k/omni-dev-fusion/commit/58c1a5e6bce7430fda5ece97957f5ecd0f82c504)) - guangtao
- (**orchestrator**) convert test functions to use assert instead of return - ([73728ee](https://github.com/tao3k/omni-dev-fusion/commit/73728ee5839b5c181730d0345f2daa5e4527d894)) - guangtao
#### Documentation
- (**claude**) CLAUDE.md: add documentation classification and authorization rules - ([aa32423](https://github.com/tao3k/omni-dev-fusion/commit/aa324237aa455e1da4177363aa3873300b29a454)) - guangtao
- (**docs**) add vision and key differentiators to README - ([9e005c8](https://github.com/tao3k/omni-dev-fusion/commit/9e005c860ad56d3b7265f1d21b40a5bc30a477b3)) - guangtao
- (**git-workflow**) add legal binding protocol rules for authorization - ([668d10b](https://github.com/tao3k/omni-dev-fusion/commit/668d10b165d0394a2639bde7a7ca8538a29f8651)) - guangtao
- (**git-workflow**) clarify git commit ≡ just agent-commit rule - ([184cee7](https://github.com/tao3k/omni-dev-fusion/commit/184cee7c7d58c9194fe91397bd928d7311018cd6)) - guangtao
- (**mcp-server**) add start_spec Legislation Gate documentation - ([4ee3276](https://github.com/tao3k/omni-dev-fusion/commit/4ee327660b0e0164c15e472209a77283b0a7362b)) - guangtao
- (**mcp-server**) add GitWorkflowCache auto-load documentation - ([9ef48f2](https://github.com/tao3k/omni-dev-fusion/commit/9ef48f2dc3ebc90defee99a502adcbeb56e64613)) - guangtao
- (**orchestrator**) mark Phase 10 milestone complete with Antifragile Edition - ([3df20b7](https://github.com/tao3k/omni-dev-fusion/commit/3df20b7772230501b932a1a2dc329e1f1f4344c4)) - guangtao
- document Tri-MCP architecture and deprecate delegate_to_coder - ([ce7b017](https://github.com/tao3k/omni-dev-fusion/commit/ce7b0173e112254c309d559379f3780aad391664)) - guangtao
- add release process guideline - ([059cefd](https://github.com/tao3k/omni-dev-fusion/commit/059cefdc9ca0824b77ece4271ec9c4e190c32412)) - guangtao
#### Refactoring
- (**orchestrator**) split into Dual-MCP (Brain + Hands) - ([55d76ed](https://github.com/tao3k/omni-dev-fusion/commit/55d76ed53b5ad5a81714bd4049052d246be16bd0)) - guangtao
- migrate from omni-devenv-fusion to omni-dev-fusion - ([5401aca](https://github.com/tao3k/omni-dev-fusion/commit/5401aca4a0259628fa0589e8dbf4cca2bbdcb5bc)) - guangtao
- reorganize docs/ to follow four-category standard - ([1d5cb11](https://github.com/tao3k/omni-dev-fusion/commit/1d5cb114be0cf51ce11090812e38c10d97cec31c)) - guangtao
- clean up Tri-MCP architecture and fix docs paths - ([279b751](https://github.com/tao3k/omni-dev-fusion/commit/279b751730cd462fb4f4b4126e0cf88cbc8f1310)) - guangtao
#### Miscellaneous Chores
- (**nix**) add legacy mcp-server scope for old commits - ([88357ea](https://github.com/tao3k/omni-dev-fusion/commit/88357eaccc94ce219cf8aca898afe81a97b15d36)) - guangtao
- (**version**) start v1.4.0 development - ([4ed6b60](https://github.com/tao3k/omni-dev-fusion/commit/4ed6b606ff3c7011941f2f36b48f6234b7c33799)) - guangtao
- sync claude.nix with .mcp.json - ([11f7208](https://github.com/tao3k/omni-dev-fusion/commit/11f72082992657fceec3d093a5d065f5c58089a6)) - guangtao
- update files - ([2b15bae](https://github.com/tao3k/omni-dev-fusion/commit/2b15bae26bb5e7171766484a78ddb00d8bf9ea54)) - guangtao
- merge v1.3.0 release - ([e5782f7](https://github.com/tao3k/omni-dev-fusion/commit/e5782f7f9e3fc3dd11615b87d7432a83295735d0)) - guangtao
#### Style
- (**cli**) format all files with prettier and nixfmt - ([23029ec](https://github.com/tao3k/omni-dev-fusion/commit/23029eca7ba9c703d6b2c2a619b7700bd7a304d5)) - guangtao
- format documentation-workflow.md - ([bf3f8d8](https://github.com/tao3k/omni-dev-fusion/commit/bf3f8d873f95f4143696219d6499a850d324243a)) - guangtao
- format mcp-server/README.md - ([ed6b1ed](https://github.com/tao3k/omni-dev-fusion/commit/ed6b1ed60bd38307b60e4513de1acd669a74b7e2)) - guangtao
- format docs with prettier (start_spec updates) - ([dcede49](https://github.com/tao3k/omni-dev-fusion/commit/dcede495e5da1aa75b25fabce9d63fdea1e4a27f)) - guangtao

- - -

Changelog generated by [cocogitto](https://github.com/cocogitto/cocogitto).