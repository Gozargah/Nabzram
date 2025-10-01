"""Common utilities for ops modules."""

import logging
import os
import platform
import subprocess
from typing import Any, Dict
from uuid import UUID

from pydantic import ValidationError

# only for Windows
try:
    import ctypes
    import winreg
except ImportError:
    pass

logger = logging.getLogger(__name__)


def to_uuid(value: Any) -> UUID:
    """Convert value to UUID."""
    return value if isinstance(value, UUID) else UUID(str(value))


def error_reply(message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create error response."""
    return {"success": False, "message": message, "data": data or {}}


def validation_error_reply(e: ValidationError) -> Dict[str, Any]:
    """Create validation error response from ValidationError."""
    err_msg = ""
    for error in e.errors():
        err_msg += f"{', '.join(error['loc'])}: {error['msg']}\n"
    err_msg = err_msg.strip()
    return error_reply(err_msg)


def set_socks_system_proxy(ip_address, port):
    os_name = platform.system()
    proxy_str = f"{ip_address}:{port}"
    protocol = "socks"

    logging.info(f"Setting system SOCKS proxy on {os_name} -> {proxy_str}")

    # --- Windows ---
    if os_name == "Windows":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0,
                winreg.KEY_WRITE,
            )
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"socks={proxy_str}")
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
            winreg.CloseKey(key)

            # Notify system
            ctypes.windll.Wininet.InternetSetOptionW(0, 39, 0, 0)
            ctypes.windll.Wininet.InternetSetOptionW(0, 37, 0, 0)

            logging.info("Windows SOCKS proxy applied.")
        except Exception as e:
            logging.error(f"Failed to set Windows proxy: {e}")

    # --- macOS ---
    elif os_name == "Darwin":
        try:
            services = subprocess.check_output(["networksetup", "-listallnetworkservices"]).decode().splitlines()
            for service in services:
                if not service.strip() or service.startswith("*"):
                    continue
                subprocess.run(
                    [
                        "networksetup",
                        "-setsocksfirewallproxy",
                        service,
                        ip_address,
                        str(port),
                    ],
                    check=True,
                )
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxystate", service, "on"],
                    check=True,
                )
            logging.info("macOS SOCKS proxy applied.")
        except Exception as e:
            logging.error(f"Failed to set macOS proxy: {e}")

    # --- Linux ---
    elif os_name == "Linux":
        proxy_url = f"{protocol}://{ip_address}:{port}"
        os.environ["ALL_PROXY"] = proxy_url
        os.environ["all_proxy"] = proxy_url

        # KDE
        if subprocess.getstatusoutput("which kwriteconfig5")[0] == 0:
            try:
                subprocess.run(
                    [
                        "kwriteconfig5",
                        "--file",
                        "kioslaverc",
                        "--group",
                        "Proxy Settings",
                        "--key",
                        "ProxyType",
                        "1",
                    ],
                    check=True,
                )
                subprocess.run(
                    [
                        "kwriteconfig5",
                        "--file",
                        "kioslaverc",
                        "--group",
                        "Proxy Settings",
                        "--key",
                        "SocksProxy",
                        proxy_str,
                    ],
                    check=True,
                )
                subprocess.run(
                    [
                        "qdbus",
                        "org.kde.kioslave.kssld5",
                        "/KSSL",
                        "reparseSlaveConfiguration",
                    ],
                    check=False,
                )
                logging.info("Linux KDE SOCKS proxy applied.")
                return
            except Exception as e:
                logging.warning(f"KDE proxy setup failed: {e}")

        # GNOME
        if subprocess.getstatusoutput("which gsettings")[0] == 0:
            try:
                subprocess.run(
                    ["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"],
                    check=True,
                )
                subprocess.run(
                    [
                        "gsettings",
                        "set",
                        "org.gnome.system.proxy.socks",
                        "host",
                        ip_address,
                    ],
                    check=True,
                )
                subprocess.run(
                    [
                        "gsettings",
                        "set",
                        "org.gnome.system.proxy.socks",
                        "port",
                        str(port),
                    ],
                    check=True,
                )
                logging.info("Linux GNOME SOCKS proxy applied.")
                return
            except Exception as e:
                logging.warning(f"GSettings setup failed: {e}")

        logging.warning("No GUI proxy manager found, only environment variables set.")

    else:
        logging.warning(f"Unsupported OS: {os_name}")


def clear_socks_system_proxy():
    os_name = platform.system()
    logging.info(f"Clearing system SOCKS proxy on {os_name}")

    # --- Windows ---
    if os_name == "Windows":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0,
                winreg.KEY_WRITE,
            )
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            try:
                winreg.DeleteValue(key, "ProxyServer")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)

            ctypes.windll.Wininet.InternetSetOptionW(0, 39, 0, 0)
            ctypes.windll.Wininet.InternetSetOptionW(0, 37, 0, 0)
            logging.info("Windows proxy cleared.")
        except Exception as e:
            logging.error(f"Failed to clear Windows proxy: {e}")

    # --- macOS ---
    elif os_name == "Darwin":
        try:
            services = subprocess.check_output(["networksetup", "-listallnetworkservices"]).decode().splitlines()
            for service in services:
                if not service.strip() or service.startswith("*"):
                    continue
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxystate", service, "off"],
                    check=True,
                )
            logging.info("macOS proxy cleared.")
        except Exception as e:
            logging.error(f"Failed to clear macOS proxy: {e}")

    # --- Linux ---
    elif os_name == "Linux":
        os.environ.pop("ALL_PROXY", None)
        os.environ.pop("all_proxy", None)

        if subprocess.getstatusoutput("which kwriteconfig5")[0] == 0:
            try:
                subprocess.run(
                    [
                        "kwriteconfig5",
                        "--file",
                        "kioslaverc",
                        "--group",
                        "Proxy Settings",
                        "--key",
                        "ProxyType",
                        "0",
                    ],
                    check=True,
                )
                subprocess.run(
                    [
                        "kwriteconfig5",
                        "--file",
                        "kioslaverc",
                        "--group",
                        "Proxy Settings",
                        "--key",
                        "SocksProxy",
                        "",
                    ],
                    check=True,
                )
                subprocess.run(
                    [
                        "qdbus",
                        "org.kde.kioslave.kssld5",
                        "/KSSL",
                        "reparseSlaveConfiguration",
                    ],
                    check=False,
                )
                logging.info("Linux KDE proxy cleared.")
                return
            except Exception as e:
                logging.warning(f"KDE proxy clear failed: {e}")

        if subprocess.getstatusoutput("which gsettings")[0] == 0:
            try:
                subprocess.run(
                    ["gsettings", "set", "org.gnome.system.proxy", "mode", "none"],
                    check=True,
                )
                subprocess.run(
                    ["gsettings", "set", "org.gnome.system.proxy.socks", "host", ""],
                    check=True,
                )
                subprocess.run(
                    ["gsettings", "set", "org.gnome.system.proxy.socks", "port", "0"],
                    check=True,
                )
                logging.info("Linux GNOME proxy cleared.")
                return
            except Exception as e:
                logging.warning(f"GSettings clear failed: {e}")

        logging.warning("No GUI proxy manager found, only environment variables cleared.")

    else:
        logging.warning(f"Unsupported OS: {os_name}")
