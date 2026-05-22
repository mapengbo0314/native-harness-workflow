import os
import argparse
import re
from pathlib import Path
from collections import defaultdict
from google import genai

FALLBACK_CHARS_PER_TOKEN = 4
MIN_OVERLAP_LINE_LENGTH = 20

def count_tokens(text: str, model: str = "gemini-1.5-flash") -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return max(1, len(text) // FALLBACK_CHARS_PER_TOKEN)
    client = genai.Client(api_key=api_key)
    try:
        return client.models.count_tokens(model=model, contents=text).total_tokens
    except Exception: return max(1, len(text) // FALLBACK_CHARS_PER_TOKEN)

def test_static(target_dir: Path):
    print(f"--- Static Analysis: {target_dir} ---")
    md_files = list(target_dir.rglob("*.md"))
    results = []
    line_map = defaultdict(list)
    
    for f in md_files:
        try:
            content = f.read_text()
        except Exception as e:
            print(f"Error reading {f}: {e}")
            continue
            
        results.append({"file": str(f), "tokens": count_tokens(content)})
        
        # Simple overlap check: find common lines > MIN_OVERLAP_LINE_LENGTH
        lines = [l.strip() for l in content.splitlines() if len(l.strip()) > MIN_OVERLAP_LINE_LENGTH]
        for l in lines:
            line_map[l].append(str(f))
            
    overlaps = {l: files for l, files in line_map.items() if len(files) > 1}
    print(f"Found {len(overlaps)} redundant string patterns across {len(md_files)} files.")
    return overlaps

def test_goldfish(doc_path: Path):
    print(f"--- Goldfish Simulation: {doc_path} ---")
    try:
        doc_content = doc_path.read_text()
    except Exception as e:
        print(f"Error reading {doc_path}: {e}")
        return 0
        
    # Simulate loading referenced files
    referenced_tokens = 0
    # Basic regex parsing to find markdown links pointing to local files
    links = re.findall(r"\[.*?\]\((.*?\.md)\)", doc_content)
    for link in links:
        # Resolve path relative to the doc_path
        ref_path = doc_path.parent / link
        if ref_path.exists() and ref_path.is_file():
            try:
                ref_content = ref_path.read_text()
                referenced_tokens += count_tokens(ref_content)
            except Exception as e:
                print(f"Error reading referenced file {ref_path}: {e}")
                
    total_payload = count_tokens(doc_content) + referenced_tokens
    print(f"Goldfish Payload: {total_payload} tokens")
    return total_payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-static", type=str)
    parser.add_argument("--test-goldfish", type=str)
    args = parser.parse_args()
    if args.test_static:
        test_static(Path(args.test_static))
    if args.test_goldfish:
        test_goldfish(Path(args.test_goldfish))
