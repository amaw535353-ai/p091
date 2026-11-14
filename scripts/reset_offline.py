"""Remove only the known disposable offline SQLite database, then reseed."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "work/lab.db"
if path.is_symlink():
    raise SystemExit("Refusing to remove a symbolic link")
path.unlink(missing_ok=True)
subprocess.run([sys.executable, "-m", "p091.seed"], cwd=root, check=True)
print("Disposable offline lab reset and seeded.")
