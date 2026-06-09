<!-- harness:start -->
**Graph-first:** Prefer the `codegraph` MCP (start with `codegraph_context`) over Grep/Glob/`find` for code search and navigation. Use text search only for non-indexed content (e.g. UI strings).

**Project ops:** Before building, testing, or deploying, call the `domain` MCP's `domain_ops` tool (e.g. `domain_ops("deploy")`) for THIS repo's real commands — stack, environments, test, deploy, infra, references — instead of guessing. For product/business judgment calls, consult `domain_ops("business")`. Authored in the plugin's `domain/domain.json`.
<!-- harness:end -->
