import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from harness.minting_engine import synthesize_domain_sme_agent
with open("ONBOARDING_DOMAIN.md", "r") as f:
    content = f.read()
res = synthesize_domain_sme_agent(os.getcwd(), content, ".harness_tmp", "1", "gemini-2.5-pro", "gemini")
print("Result:", res)
