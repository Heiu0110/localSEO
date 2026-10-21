"""Cross-platform, incremental backend setup and loopback-only development runner."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def main() -> int:
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required.", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()
    virtualenv = BACKEND / ".venv"
    python = virtualenv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(virtualenv)], check=True)
    digest = hashlib.sha256((BACKEND / "requirements.txt").read_bytes()).hexdigest()
    stamp = virtualenv / ".requirements.sha256"
    if not stamp.exists() or stamp.read_text() != digest:
        subprocess.run([str(python), "-m", "pip", "install", "-r", "requirements.txt", "--cache-dir", str(ROOT / ".cache" / "pip")], cwd=BACKEND, check=True)
        stamp.write_text(digest)
    if args.run:
        command = [str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
        if not args.no_reload:
            command.append("--reload")
        return subprocess.call(command, cwd=BACKEND)
    print("Backend dependencies ready.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)
    except KeyboardInterrupt:
        raise SystemExit(0)
