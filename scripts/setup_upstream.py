"""Download the fixed official Liu checkout locally, without publishing it."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "external" / "liu-inventory"
URL = "https://github.com/xiaotianliu01/Multi-Agent-Deep-Reinforcement-Learning-on-Multi-Echelon-Inventory-Management.git"
REVISION = "a7e5a3e83e21565a5799483bc534e39635ec65dd"


def main():
    if TARGET.exists():
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=TARGET, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=TARGET, text=True)
        if revision != REVISION or dirty.strip():
            raise SystemExit("Existing upstream checkout differs; inspect it manually. No files were reset.")
        print(f"Already present at the expected revision: {TARGET}")
        return
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", URL, str(TARGET)], check=True)
    subprocess.run(["git", "checkout", "--detach", REVISION], cwd=TARGET, check=True)
    print(f"Downloaded official source to {TARGET}")


if __name__ == "__main__":
    main()
