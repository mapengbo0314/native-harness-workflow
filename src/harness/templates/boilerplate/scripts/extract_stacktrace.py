#!/usr/bin/env python3
import sys
import re
from collections import deque

def extract_trace(file_path):
    # Heuristic for finding common stack trace patterns
    patterns = [
        r"Traceback \(most recent call last\):", # Python
        r"panic: ",                            # Go
        r"AssertionError",                      # Generic
        r"panicked at",                         # Rust
        r"stack backtrace:",                   # Rust
        r"Exception in thread",                 # Java/Kotlin
        r"\w+Exception:",                       # Java/Kotlin/Generic
        r"(TypeError|ReferenceError|SyntaxError|Error):" # TS/JS/Generic
    ]
    node_pattern = r"^\s*at "
    
    last_lines = deque(maxlen=40)
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line_content = line.rstrip()
                
                # Check for standard patterns
                if any(re.search(p, line_content) for p in patterns):
                    trace = [line_content]
                    for _ in range(99):
                        try:
                            trace.append(next(f).rstrip())
                        except StopIteration:
                            break
                    return "\n".join(trace)
                
                # Node.js specific: if we see 'at ', take the previous line too if it looks like an error
                if re.search(node_pattern, line_content):
                    trace = []
                    if last_lines:
                        # Include previous line as it often contains the error message
                        trace.append(last_lines[-1])
                    trace.append(line_content)
                    for _ in range(98):
                        try:
                            trace.append(next(f).rstrip())
                        except StopIteration:
                            break
                    return "\n".join(trace)
                
                last_lines.append(line_content)
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except Exception as e:
        return f"Error reading file: {e}"
            
    return "\n".join(last_lines)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <logfile>")
        sys.exit(1)
    print(extract_trace(sys.argv[1]))
