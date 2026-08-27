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

# Run the scanner and show its real output
result = subprocess.run(
    [sys.executable, str(scanner)],
    capture_output=True,
    text=True
)

print("\n===== SCANNER STDOUT =====")
print(result.stdout)

print("===== SCANNER STDERR =====")
print(result.stderr)

# Make Railway fail only after printing the real error
result.check_returncode()
