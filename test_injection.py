import re

def inject_harness_block(content: str) -> str:
    injection_block = """<!-- harness:start -->
**Graph-first:** Prefer the `codegraph` MCP (start with `codegraph_context`) over Grep/Glob/`find` for code search and navigation. Use text search only for non-indexed content (e.g. UI strings).
<!-- harness:end -->"""
    
    pattern = r"<!-- harness:start -->.*?<!-- harness:end -->"
    if re.search(pattern, content, flags=re.DOTALL):
        return re.sub(pattern, injection_block, content, flags=re.DOTALL)
    else:
        if content and not content.endswith('\n'):
            content += '\n'
        if content and not content.endswith('\n\n'):
            content += '\n'
        return content + injection_block + "\n"

print(inject_harness_block("Hello world"))
print("---")
print(inject_harness_block("Hello world\n<!-- harness:start -->old stuff<!-- harness:end -->\nFooter"))
