import re
import os

files_to_update = [
    "src/harness/init/discovery_engine.py"
]

for file_path in files_to_update:
    if not os.path.exists(file_path):
        continue
    with open(file_path, "r") as f:
        content = f.read()

    # Replace function definitions
    content = re.sub(r'def deep_audit_discovery\(project_path: str, query_llm_fn=None, llm_provider=None, api_key=None, \*\*kwargs\) -> dict:',
                     r'def deep_audit_discovery(project_path: str, query_llm_fn=None, cli_name=None, **kwargs) -> dict:', content)
    content = re.sub(r'def detect_tech_stack\(project_path: str, query_llm_fn=None, llm_provider=None, api_key=None\) -> dict:',
                     r'def detect_tech_stack(project_path: str, query_llm_fn=None, cli_name=None) -> dict:', content)
    content = re.sub(r'def generate_onboarding_domain_doc\(project_path: str, domain_summary: str, query_llm_fn=None, llm_provider=None, api_key=None, context_str="", boilerplate_dir: str = None\):',
                     r'def generate_onboarding_domain_doc(project_path: str, domain_summary: str, query_llm_fn=None, cli_name=None, context_str="", boilerplate_dir: str = None):', content)
    content = re.sub(r'def generate_grilling_questions\(project_path: str, query_llm_fn, llm_provider: str, api_key: str, model: str = None\) -> list\[dict\]:',
                     r'def generate_grilling_questions(project_path: str, query_llm_fn, cli_name: str, model: str = None) -> list[dict]:', content)
    content = re.sub(r'def synthesize_grilled_context\(project_path: str, qa_pairs: list\[tuple\], query_llm_fn, llm_provider: str, api_key: str, model: str = None\) -> str:',
                     r'def synthesize_grilled_context(project_path: str, qa_pairs: list[tuple], query_llm_fn, cli_name: str, model: str = None) -> str:', content)
                     
    # Replace internal checks and calls
    content = re.sub(r'if not query_llm_fn or not llm_provider or not api_key:',
                     r'if not query_llm_fn or not cli_name:', content)
    content = re.sub(r'if query_llm_fn and llm_provider and api_key:',
                     r'if query_llm_fn and cli_name:', content)
                     
    # Replace query_llm_fn calls
    content = re.sub(r'query_llm_fn\(prompt, llm_provider, api_key, model\)',
                     r'query_llm_fn(prompt, cli_name, model=model)', content)
    content = re.sub(r'query_llm_fn\(full_prompt, llm_provider, api_key, model\)',
                     r'query_llm_fn(full_prompt, cli_name, model=model)', content)
    content = re.sub(r'query_llm_fn\(prompt, llm_provider, api_key\)',
                     r'query_llm_fn(prompt, cli_name)', content)
                     
    # Replace calls to these functions themselves
    content = re.sub(r'deep_audit_discovery\(project_path, query_llm_fn, llm_provider, api_key\)',
                     r'deep_audit_discovery(project_path, query_llm_fn, cli_name)', content)
    content = re.sub(r'detect_tech_stack\(project_path, query_llm_fn, llm_provider, api_key\)',
                     r'detect_tech_stack(project_path, query_llm_fn, cli_name)', content)

    with open(file_path, "w") as f:
        f.write(content)

print("Done")
