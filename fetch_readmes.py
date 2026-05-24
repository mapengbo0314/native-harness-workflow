import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

repos = [
    ("hjasanchez", "agentic-engineering", "main", "README.md"),
    ("nikhilsitaram", "claude-caliper", "main", "README.md"),
    ("celesteanders", "harness", "main", "docs/best-practices.md"),
    ("Chachamaru127", "claude-code-harness", "main", "README.md"),
    ("Chachamaru127", "harness-mem", "main", "README.md"),
    ("SethGammon", "Citadel", "main", "README.md"),
    ("ruvnet", "ruflo", "main", "README.md")
]

results = {}
for owner, repo, branch, path in repos:
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            text = response.read().decode('utf-8')
            results[f"{owner}/{repo}"] = text[:1000] # Get first 1000 chars for brevity
    except Exception as e:
        # try master branch
        try:
            url_master = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{path}"
            req = urllib.request.Request(url_master)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                text = response.read().decode('utf-8')
                results[f"{owner}/{repo}"] = text[:1000]
        except Exception as e2:
            results[f"{owner}/{repo}"] = f"Error: {e2}"

print(json.dumps(results, indent=2))
