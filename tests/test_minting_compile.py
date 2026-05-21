import sys
try:
    import harness.minting_engine
    print("Syntax OK")
except Exception as e:
    print(f"Error: {e}")
