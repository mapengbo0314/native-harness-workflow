import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from harness.minting_engine import atomic_swap_directory
print("Found swap function")
