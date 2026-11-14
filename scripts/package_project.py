"""Produce a sanitized source snapshot; never include installed tools or .env."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "p091-delivery.zip"
DIRECTORIES = ["p091", "apps", "infra", "scripts", "tests", "fixtures", "docs", "evaluations"]
ROOT_FILES = ["README.md", "Makefile", "Dockerfile", ".dockerignore", ".gitignore", ".env.example", "pyproject.toml", "requirements.lock"]
EXCLUDED = {"node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "work", ".git"}


def main() -> None:
    paths = [ROOT / name for name in ROOT_FILES]
    for name in DIRECTORIES:
        paths.extend(path for path in (ROOT / name).rglob("*") if path.is_file())
    paths = sorted({path for path in paths if not set(path.relative_to(ROOT).parts) & EXCLUDED
                    and ".generated." not in path.name and path.suffix not in {".pyc", ".db"}
                    and (not path.name.startswith(".env") or path.name == ".env.example")})
    # Generated local credentials must not occur anywhere in the source snapshot.
    secrets = []
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                if any(part in key for part in ["PASSWORD", "SECRET", "TOKEN", "QDRANT_KEY"]) and len(value) >= 20:
                    secrets.append(value.encode())
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise SystemExit("Source snapshot refuses symlinks or external files")
        raw = path.read_bytes()
        if any(secret in raw for secret in secrets):
            raise SystemExit(f"Generated credential found in {path.relative_to(ROOT)}; archive stopped")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, Path("p091") / path.relative_to(ROOT))
    with zipfile.ZipFile(OUT) as archive:
        if archive.testzip() is not None:
            raise SystemExit("Archive integrity check failed")
    manifest = {"archive": OUT.name, "file_count": len(paths), "size_bytes": OUT.stat().st_size,
        "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(), "generated_secret_scan": "PASS", "zip_integrity": "PASS",
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
    (OUT.with_suffix(".manifest.json")).write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({key: value for key, value in manifest.items() if key != "source_sha256"}, indent=2))


if __name__ == "__main__":
    main()
