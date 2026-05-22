import re

with open("tests/integration/test_dynamic_manifest.py", "r") as f:
    content = f.read()

# The issue is that hooks["UserPromptSubmit"] is a list of objects that have "hooks" lists.
# Actually, the generated structure is:
# "UserPromptSubmit": [
#   {
#     "hooks": [
#       {
#         "type": "command",
#         "command": "python3 -m src.hooks.prompt_interceptor"
#       }
#     ]
#   }
# ]

content = content.replace('hooks["UserPromptSubmit"][0]["type"] == "command"', 'hooks["UserPromptSubmit"][0]["hooks"][0]["type"] == "command"')
content = content.replace('hooks["UserPromptSubmit"][0]["command"]', 'hooks["UserPromptSubmit"][0]["hooks"][0]["command"]')

content = content.replace('hooks["PreToolUse"][0]["type"] == "command"', 'hooks["PreToolUse"][0]["hooks"][0]["type"] == "command"')
content = content.replace('hooks["PreToolUse"][0]["command"]', 'hooks["PreToolUse"][0]["hooks"][0]["command"]')

content = content.replace('hooks["Stop"][0]["type"] == "command"', 'hooks["Stop"][0]["hooks"][0]["type"] == "command"')
content = content.replace('hooks["Stop"][0]["command"]', 'hooks["Stop"][0]["hooks"][0]["command"]')

content = content.replace('hooks["PostToolUse"][0]["command"]', 'hooks["PostToolUse"][0]["hooks"][0]["command"]')

content = content.replace('hooks["PreCompact"][0]["command"]', 'hooks["PreCompact"][0]["hooks"][0]["command"]')

with open("tests/integration/test_dynamic_manifest.py", "w") as f:
    f.write(content)
print("Updated test file.")
