from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run() -> None:
    root = Path(__file__).resolve().parents[1]
    dist = root / "dist"
    work = root / "build" / "pyinstaller"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "ProgonPy",
        "--collect-submodules",
        "gui.widgets",
        "--collect-submodules",
        "gui.state",
        "--add-data",
        f"Server.exe{';' if sys.platform.startswith('win') else ':'}.",
        "--distpath",
        str(dist),
        "--workpath",
        str(work),
        str(root / "main.py"),
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=root)

    print("\nBuild completed.")
    print(f"Executable folder: {dist / 'ProgonPy'}")


if __name__ == "__main__":
    run()
