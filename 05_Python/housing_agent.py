from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

print("=" * 60)
print("Housing Agent Production Runner")
print("=" * 60)

scanner = ROOT / "housing_agent_SCANNER.py"

if not scanner.exists():
    raise FileNotFoundError(f"Scanner not found: {scanner}")

print(f"Running: {scanner}")
print("-" * 60)

result = subprocess.run(
    [sys.executable, str(scanner)],
    cwd=str(ROOT),
    capture_output=True,
    text=True
)

print("STDOUT")
print("-" * 60)
print(result.stdout)

if result.stderr:
    print("STDERR")
    print("-" * 60)
    print(result.stderr)

print("-" * 60)
print(f"Exit code: {result.returncode}")

result.check_returncode()
