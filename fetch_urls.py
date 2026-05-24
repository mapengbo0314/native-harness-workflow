import urllib.request
import urllib.error
import json
import re

urls = [
    "https://github.com/hjasanchez/agentic-engineering",
    "https://www.reddit.com/r/ClaudeCode/comments/1rx60cf/show_off_your_own_harness_setups_here/",
    "https://github.com/nikhilsitaram/claude-caliper",
    "https://github.com/celesteanders/harness/blob/main/docs/best-practices.md",
    "https://github.com/Chachamaru127/claude-code-harness",
    "https://github.com/Chachamaru127/harness-mem",
    "https://github.com/SethGammon/Citadel",
    "https://langfuse.com/",
    "https://github.com/ruvnet/ruflo",
    "https://x.com/SethGammon/status/2034257777263084017"
]

results = {}
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

for url in urls:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            # Extract content: for github repos, usually readme is in an article tag or text
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            title = title_match.group(1) if title_match else "No title"
            
            # Very basic text extraction (just grabbing snippet to understand the repo)
            text_content = re.sub(r'<[^>]+>', ' ', html)
            text_content = re.sub(r'\s+', ' ', text_content)
            
            # try to find the "About" or "Readme"
            readme_start = text_content.find("README.md")
            if readme_start != -1:
                snippet = text_content[readme_start:readme_start+1500]
            else:
                snippet = text_content[:1500]
                
            results[url] = {"status": "success", "title": title, "snippet": snippet[:500]}
    except Exception as e:
         results[url] = {"status": "error", "error": str(e)}

print(json.dumps(results, indent=2))
