
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

print("="*60)
print("Housing Agent Production Runner")
print("="*60)

scanner = ROOT / "housing_agent_SCANNER.py"

if not scanner.exists():
    raise FileNotFoundError(f"Scanner not found: {scanner}")

subprocess.run([sys.executable, str(scanner)], check=True)
