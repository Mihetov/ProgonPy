from __future__ import annotations

import subprocess
import sys
import shutil
from pathlib import Path


def run() -> None:
    root = Path(__file__).resolve().parents[1]
    dist = root / "dist"
    work = root / "build" / "pyinstaller"
    
    # Базовые параметры
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", "ProgonPy",
        "--distpath", str(dist),
        "--workpath", str(work),
    ]
    
    # Скрытые импорты
    hidden_imports = [
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "gui.state.poller",
        "--hidden-import", "backend.backend_client",
        "--collect-submodules", "gui.widgets",
        "--collect-submodules", "gui.state",
        "--collect-submodules", "backend",
    ]
    cmd.extend(hidden_imports)
    
    # Добавляем Server.exe
    if sys.platform.startswith("win"):
        separator = ";"
    else:
        separator = ":"
    
    cmd.extend([
        "--add-binary", f"Server.exe{separator}.",
        "--add-data", f"Server.exe{separator}.",
    ])
    
    cmd.append(str(root / "main.py"))
    
    icon_path = root / "icon.ico"
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])
    
    print("Running PyInstaller...")
    print(" ".join(cmd))
    print("\n" + "="*80 + "\n")
    
    try:
        subprocess.run(cmd, check=True, cwd=root)
    except subprocess.CalledProcessError as e:
        print(f"\nError during build: {e}")
        sys.exit(1)

    print("\n" + "="*80)
    print("Copying additional files to distribution...")
    
    exe_dir = dist / "ProgonPy"
    
    # Копируем папку gui
    gui_src = root / "gui"
    gui_dst = exe_dir / "gui"
    
    if gui_src.exists():
        if gui_dst.exists():
            shutil.rmtree(gui_dst)
        shutil.copytree(gui_src, gui_dst)
        print(f"✅ GUI folder copied to: {gui_dst}")
        file_count = sum(1 for _ in gui_dst.rglob("*") if _.is_file())
        print(f"   Copied {file_count} files")
    else:
        print(f"⚠️  GUI source folder not found: {gui_src}")
    
    # Копируем Server.exe (на случай если --add-binary не сработал)
    server_src = root / "Server.exe"
    server_dst = exe_dir / "Server.exe"
    
    if server_src.exists():
        shutil.copy2(server_src, server_dst)
        print(f"✅ Server.exe copied to: {server_dst}")
    else:
        print(f"⚠️  Server.exe not found in source: {server_src}")
    
    print("\n✅ Build completed successfully!")
    print(f"📁 Executable folder: {exe_dir}")
    print(f"🚀 Run: {exe_dir / 'ProgonPy.exe'}")
    print("\n📋 Distribution contents:")
    for item in sorted(exe_dir.iterdir()):
        if item.is_dir():
            print(f"   📁 {item.name}/")
        else:
            size = item.stat().st_size / 1024 / 1024
            print(f"   📄 {item.name} ({size:.2f} MB)")


if __name__ == "__main__":
    run()