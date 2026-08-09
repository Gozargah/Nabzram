"""Privilege elevation helpers for installing and running privileged commands."""

from __future__ import annotations

import logging
import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def can_write_path(path: str) -> bool:
    """Return True if the current user can create or overwrite path."""
    target = Path(path)
    if target.exists():
        return os.access(target, os.W_OK)

    parent = target.parent
    while not parent.exists():
        parent = parent.parent
        if parent == parent.parent:
            break
    return bool(parent.exists() and os.access(parent, os.W_OK))


def install_file(source: str, dest: str) -> None:
    """Copy source to dest, prompting for administrator rights when required."""
    dest_path = Path(dest)
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        if platform.system() != "Windows":
            os.chmod(dest, 0o755)
        return
    except PermissionError:
        logger.info(f"Permission denied writing {dest}; retrying with elevation")
    except OSError as e:
        if getattr(e, "errno", None) != 13:
            raise
        logger.info(f"OS error writing {dest}; retrying with elevation: {e}")

    install_file_elevated(source, dest)


def install_file_elevated(source: str, dest: str) -> None:
    """Install a file to dest using an administrator prompt."""
    system = platform.system()
    dest_dir = str(Path(dest).parent)

    if system == "Linux":
        _run_elevated(["mkdir", "-p", dest_dir], check=True)
        _run_elevated(["install", "-m", "755", source, dest], check=True)
        return

    if system == "Darwin":
        script = (
            f"mkdir -p {shlex.quote(dest_dir)} && "
            f"cp {shlex.quote(source)} {shlex.quote(dest)} && "
            f"chmod 755 {shlex.quote(dest)}"
        )
        _run_osascript_admin(script)
        return

    if system == "Windows":
        _run_windows_elevated_copy(source, dest)
        return

    msg = f"Elevated install is not supported on {system}"
    raise RuntimeError(msg)


def popen_elevated(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
) -> subprocess.Popen:
    """Start a long-running process with administrator privileges."""
    system = platform.system()

    if system == "Linux":
        cmd = _linux_elevated_command(argv, env)
        return subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
        )

    if system == "Darwin":
        cmd = _darwin_elevated_command(argv, env)
        return subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
        )

    if system == "Windows":
        return _windows_popen_elevated(argv, env=env, stdout=stdout, stderr=stderr)

    msg = f"Elevated process start is not supported on {system}"
    raise RuntimeError(msg)


def _linux_elevated_command(argv: list[str], env: dict[str, str] | None) -> list[str]:
    """Build an elevated argv for Linux (sudo -n, then pkexec)."""
    if env:
        env_argv = ["env", *[f"{key}={value}" for key, value in env.items()], *argv]
    else:
        env_argv = list(argv)

    # Prefer non-interactive sudo when credentials are already cached.
    try:
        probe = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=3,
            check=False,
        )
        if probe.returncode == 0:
            return ["sudo", "-n", *env_argv]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    if shutil.which("pkexec"):
        return ["pkexec", *env_argv]

    if shutil.which("sudo"):
        return ["sudo", *env_argv]

    msg = "Neither pkexec nor sudo is available for elevation"
    raise RuntimeError(msg)


def _darwin_elevated_command(argv: list[str], env: dict[str, str] | None) -> list[str]:
    """Build an osascript command that runs argv as administrator."""
    env_exports = ""
    if env:
        env_exports = " ".join(f"export {shlex.quote(k)}={shlex.quote(v)};" for k, v in env.items())
    quoted = " ".join(shlex.quote(part) for part in argv)
    shell = f"{env_exports} exec {quoted}"
    return [
        "osascript",
        "-e",
        f"do shell script {shlex.quote(shell)} with administrator privileges",
    ]


def _run_elevated(argv: list[str], *, check: bool = False, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a short elevated command on Linux."""
    cmd = _linux_elevated_command(argv, env=None)
    logger.info(f"Running elevated command: {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        msg = f"Elevated command failed ({result.returncode}): {detail or argv}"
        raise RuntimeError(msg)
    return result


def _run_osascript_admin(shell_script: str, timeout: int = 120) -> None:
    """Run a shell script with macOS administrator privileges."""
    cmd = [
        "osascript",
        "-e",
        f"do shell script {shlex.quote(shell_script)} with administrator privileges",
    ]
    logger.info("Running elevated macOS install via osascript")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        msg = f"Elevated macOS command failed: {detail or shell_script}"
        raise RuntimeError(msg)


def _run_windows_elevated_copy(source: str, dest: str) -> None:
    """Copy a file with a UAC prompt on Windows."""
    dest_dir = str(Path(dest).parent)
    ps_script = (
        f"$destDir = '{_ps_escape(dest_dir)}'; "
        f"New-Item -ItemType Directory -Force -Path $destDir | Out-Null; "
        f"Copy-Item -Force -Path '{_ps_escape(source)}' -Destination '{_ps_escape(dest)}'"
    )
    _run_windows_elevated_powershell(ps_script)


def _windows_popen_elevated(
    argv: list[str],
    *,
    env: dict[str, str] | None,
    stdout,
    stderr,
) -> subprocess.Popen:
    """Start an elevated Windows process via PowerShell Start-Process -Verb RunAs."""
    # Start-Process -Verb RunAs cannot attach our stdout pipes to the elevated
    # child easily, so we wrap through powershell and still keep a waitable host
    # process. Logs may be limited on Windows elevated TUN starts.
    arg_list = ",".join(f"'{_ps_escape(a)}'" for a in argv[1:])
    env_block = ""
    if env:
        assignments = "; ".join(f"$env:{k} = '{_ps_escape(v)}'" for k, v in env.items())
        env_block = f"{assignments}; "

    ps_script = (
        f"{env_block}"
        f"$p = Start-Process -FilePath '{_ps_escape(argv[0])}' "
        f"-ArgumentList @({arg_list}) -Verb RunAs -PassThru -WindowStyle Hidden; "
        f"Wait-Process -Id $p.Id; exit $p.ExitCode"
    )
    return subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_script,
        ],
        stdout=stdout,
        stderr=stderr,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _run_windows_elevated_powershell(ps_script: str, timeout: int = 180) -> None:
    """Run a PowerShell snippet elevated and wait for completion."""
    wrapper = (
        f"$p = Start-Process -FilePath 'powershell' "
        f"-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-Command',"
        f"'{_ps_escape(ps_script)}') "
        f"-Verb RunAs -PassThru -WindowStyle Hidden -Wait; "
        f"if ($null -ne $p) {{ exit $p.ExitCode }} else {{ exit 1 }}"
    )
    logger.info("Running elevated Windows PowerShell command")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            wrapper,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        msg = f"Elevated Windows command failed: {detail or 'UAC prompt cancelled or command failed'}"
        raise RuntimeError(msg)


def _ps_escape(value: str) -> str:
    """Escape a string for inclusion in a single-quoted PowerShell literal."""
    return value.replace("'", "''")


def is_elevated_available() -> bool:
    """Return whether an elevation mechanism appears available on this OS."""
    system = platform.system()
    if system == "Linux":
        return bool(shutil.which("pkexec") or shutil.which("sudo"))
    if system == "Darwin":
        return True
    if system == "Windows":
        return True
    return False
