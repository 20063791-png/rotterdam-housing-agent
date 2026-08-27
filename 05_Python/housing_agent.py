from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

print("=" * 60)
print("Housing Agent Production Runner")
print("=" * 60)

scanner = ROOT / "housing_agent_SCANNER.py"

print(f"Running: {scanner}")

if not scanner.exists():
    raise FileNotFoundError(f"Scanner not found: {scanner}")

result = subprocess.run(
    [sys.executable, str(scanner)],
    capture_output=True,
    text=True
)

print("-" * 60)
print("STDOUT")
print("-" * 60)
print(result.stdout)

print("-" * 60)
print("STDERR")
print("-" * 60)
print(result.stderr)

result.check_returncode()
