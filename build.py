#!/usr/bin/env python3
"""
Nuitka build script for Nabzram
This script builds the FastAPI application with Nuitka compiler
"""

import importlib.util
import platform
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and stream the result in real time"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, text=True)
    if result.returncode != 0:
        print(f"Error: {result.returncode}")
        sys.exit(1)
    return result


def build_frontend():
    """Build the React frontend"""
    print("Building React frontend...")
    ui_dir = Path("ui")

    # Install dependencies if node_modules doesn't exist
    if not (ui_dir / "node_modules").exists():
        print("Installing frontend dependencies...")
        run_command(["bun", "install"], cwd=ui_dir)

    # Build the frontend
    run_command(["bun", "run", "build"], cwd=ui_dir)
    print("Frontend build completed!")


def build_with_nuitka():
    """Build the Python application with Nuitka"""
    print("Building with Nuitka...")

    # Nuitka command
    nuitka_cmd = [
        "python",
        "-m",
        "nuitka",
        "--standalone",  # Create standalone executable
        "--onefile",  # Create one file executable
        "--include-data-dir=ui/dist=ui/dist",
        "--include-data-files=assets/icon.png=assets/icon.png",
        "--disable-console",
        "--enable-plugin=pywebview",
        "--enable-plugin=upx",
        "--show-progress",
        "--follow-imports",  # Follow all imports automatically
        "--output-filename=nabzram",  # Output filename
        "--output-dir=dist",  # Output directory
        "--remove-output",  # Remove build directory after completion
        "--assume-yes-for-downloads",  # Assume yes for downloads
        "main.py",  # Main script
    ]

    # Platform-specific options (GUI backend handled by pywebview + runtime, icons here)
    system = platform.system().lower()
    if system == "windows":
        # Windows: CEF backend (used at runtime), disable console and set ICO icon
        nuitka_cmd.extend(
            [
                "--windows-console-mode=disable",
                "--windows-icon-from-ico=assets/icon.ico",
            ]
        )
    elif system == "darwin":
        # macOS: Cocoa backend (runtime), create app bundle and set ICNS icon
        nuitka_cmd.extend(
            [
                "--macos-create-app-bundle",
                "--macos-bundle-name=Nabzram",
                "--macos-bundle-identifier=com.nabzram.app",
                "--macos-app-icon=assets/icon.icns",
            ]
        )
    else:
        # Linux: GTK backend (runtime) and PNG icon
        nuitka_cmd.extend(
            [
                "--linux-icon=assets/icon.png",
            ]
        )

    # Run Nuitka
    run_command(nuitka_cmd)
    print("Nuitka build completed!")


def main():
    """Main build function"""
    print("Starting Nabzram build process...")

    # Check if Nuitka is installed
    if importlib.util.find_spec("nuitka") is None:
        print("Nuitka not found. Installing...")
        run_command([sys.executable, "-m", "pip", "install", "nuitka"])
    else:
        print("✓ Nuitka is installed")

    # Build frontend first
    build_frontend()

    # Build with Nuitka
    build_with_nuitka()

    print("Build completed successfully!")
    print("Executable location: dist/nabzram")


if __name__ == "__main__":
    main()
