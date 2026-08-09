"""Xray-core process management service."""

import json
import logging
import os
import platform
import subprocess
import threading
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime
from queue import Empty, Queue
from random import randint
from shutil import which
from socket import AF_INET, SOCK_STREAM, socket
from tempfile import NamedTemporaryFile
from uuid import UUID

from requests import get as http_get
from requests.exceptions import RequestException, Timeout

from app.database import db
from app.models.database import ProcessInfo
from app.services.elevation import popen_elevated

logger = logging.getLogger(__name__)


class UUIDEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles UUID objects."""

    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ProcessManager:
    """Manages xray-core processes."""

    def __init__(self) -> None:
        self.running_processes: dict[UUID, ProcessInfo] = {}
        self.process_handles: dict[UUID, subprocess.Popen] = {}
        self.log_queues: dict[UUID, Queue] = {}
        self.log_threads: dict[UUID, threading.Thread] = {}
        self.current_server_id: UUID | None = None  # Track the currently running server
        self._temp_config_paths: dict[UUID, str] = {}

    def get_effective_xray_binary(self) -> str:
        """Get the effective xray binary path from database settings or system PATH."""
        try:
            db_settings = db.get_settings()
            if db_settings.xray_binary:
                return db_settings.xray_binary
        except Exception as e:
            logger.warning(f"Failed to get xray_binary from database settings: {e}")

        # Try both "xray" and "xray.exe" for better Windows compatibility
        xray_path = which("xray") or which("xray.exe")
        if xray_path:
            return xray_path

        if platform.system() == "Linux":
            return "/usr/bin/xray"
        if platform.system() == "Windows":
            return "C:\\Program Files\\Xray\\xray.exe"
        return "/usr/bin/xray"

    def get_xray_assets_folder(self) -> str | None:
        """Get the xray assets folder from database settings."""
        try:
            db_settings = db.get_settings()
            if db_settings.xray_assets_folder:
                return db_settings.xray_assets_folder
        except Exception as e:
            logger.warning(
                f"Failed to get xray_assets_folder from database settings: {e}",
            )

        # No fallback - return None if not set in database
        return None

    def check_xray_availability(self) -> dict[str, any]:
        """Check if xray-core is available and get version info."""
        try:
            # Try to run xray version command
            xray_binary = self.get_effective_xray_binary()

            # On Windows, hide the console window
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                [xray_binary, "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
            )

            stdout, stderr = process.communicate()

            if process.returncode == 0:
                version_output = stdout.decode().strip()

                # Parse version information
                version_info = {
                    "available": True,
                    "version": None,
                    "commit": None,
                    "go_version": None,
                    "arch": None,
                }

                # Parse version string (format may vary)
                # Example output:
                # Xray 1.8.4 (Xray, Penetrates Everything.) Custom (go1.21.1 linux/amd64)
                # A more robust parser:
                import re

                lines = version_output.split("\n")
                for line in lines:
                    line = line.strip()
                    # Match version line: Xray 1.8.4 (Xray, Penetrates Everything.) 2cba2c4 (go1.24.1 linux/amd64)
                    m = re.match(
                        r"^Xray\s+([0-9]+\.[0-9]+\.[0-9]+)[^\n]*?(?:\s+([0-9a-f]{7,}))?\s*\((go[0-9.]+)\s+([^\s)]+)\)",
                        line,
                    )
                    if m:
                        version_info["version"] = m.group(1)
                        if m.group(2):
                            version_info["commit"] = m.group(2)
                        version_info["go_version"] = m.group(3)
                        version_info["arch"] = m.group(4)
                        continue

                    # Fallbacks for other lines
                    if "commit:" in line.lower():
                        version_info["commit"] = line.split(":", 1)[1].strip()
                    elif "go version" in line.lower():
                        # e.g. go version go1.24.1 linux/amd64
                        go_version_match = re.search(
                            r"go version ([^\s]+)",
                            line,
                            re.IGNORECASE,
                        )
                        if go_version_match:
                            version_info["go_version"] = go_version_match.group(1)
                        arch_match = re.search(r"(amd64|arm64|386|arm)", line)
                        if arch_match:
                            version_info["arch"] = arch_match.group(1)
                    elif "/" in line and any(arch in line for arch in ["amd64", "arm64", "386", "arm"]):
                        # Try to extract arch from e.g. linux/amd64
                        arch_match = re.search(r"(amd64|arm64|386|arm)", line)
                        if arch_match:
                            version_info["arch"] = arch_match.group(1)

                return version_info
            return {"available": False, "error": stderr.decode().strip()}

        except FileNotFoundError:
            xray_binary = self.get_effective_xray_binary()
            return {
                "available": False,
                "error": f"xray binary not found: {xray_binary}",
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def check_xray_capabilities(self) -> tuple[bool, str]:
        """Check if xray has the required capabilities to set SO_MARK on Linux.

        Returns:
            Tuple[bool, str]: (has_capabilities, error_message)
        """
        if platform.system() != "Linux":
            return True, ""  # Not needed on non-Linux systems

        try:
            xray_binary = self.get_effective_xray_binary()

            # Use getcap to check if the binary has the required capabilities
            result = subprocess.run(
                ["getcap", xray_binary],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return False, "getcap failed or binary has no capabilities"

            output = result.stdout.strip()
            if not output:
                return False, "No capabilities found"

            # Check if both cap_net_admin and cap_net_raw are present
            has_net_admin = "cap_net_admin" in output
            has_net_raw = "cap_net_raw" in output

            if has_net_admin and has_net_raw:
                logger.info("Xray has required capabilities for SO_MARK")
                return True, ""

            return False, f"Missing capabilities. Current: {output}"

        except FileNotFoundError:
            return False, "getcap command not found"
        except subprocess.TimeoutExpired:
            return False, "getcap timeout"
        except Exception as e:
            logger.exception(f"Failed to check xray capabilities: {e}")
            return False, str(e)

    def set_xray_capabilities(self, binary_path: str) -> tuple[bool, str]:
        """Set required capabilities on xray binary using setcap.

        Returns:
            Tuple[bool, str]: (success, error_message)
        """
        if platform.system() != "Linux":
            return True, ""

        # First try with sudo -n (non-interactive, uses cached credentials)
        try:
            result = subprocess.run(
                ["sudo", "-n", "setcap", "cap_net_admin,cap_net_raw+ep", binary_path],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                logger.info(f"Successfully set capabilities on {binary_path} (cached credentials)")
                return True, ""

            logger.debug(f"Sudo -n failed with return code {result.returncode}")
        except FileNotFoundError:
            logger.debug("sudo command not found")
        except subprocess.TimeoutExpired:
            logger.debug("sudo command timed out")
        except Exception as e:
            logger.debug(f"Sudo attempt failed: {e}")

        # If that fails, try with pkexec (polkit - prompts for password)
        try:
            logger.info("Cached sudo credentials not available, trying pkexec")
            result = subprocess.run(
                ["pkexec", "setcap", "cap_net_admin,cap_net_raw+ep", binary_path],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                logger.info(f"Successfully set capabilities on {binary_path} (via pkexec)")
                return True, ""

            error_msg = result.stderr or "pkexec setcap failed"
            logger.error(f"Failed to set capabilities via pkexec: {error_msg}")
            return False, error_msg

        except FileNotFoundError:
            logger.error("pkexec command not found")
            return False, "Neither sudo nor pkexec found"
        except subprocess.TimeoutExpired:
            logger.error("pkexec timed out waiting for user input")
            return False, "pkexec timed out"
        except Exception as e:
            logger.exception(f"Failed to set xray capabilities via pkexec: {e}")
            return False, str(e)

    def ensure_xray_capabilities(self) -> tuple[bool, str]:
        """Ensure xray has the required capabilities, set them if missing.

        Returns:
            Tuple[bool, str]: (has_capabilities, message)
        """
        if platform.system() != "Linux":
            return True, "Not required on this platform"

        has_caps, error = self.check_xray_capabilities()

        if has_caps:
            return True, "Xray has required capabilities"

        # Capabilities are missing, try to set them
        logger.info(f"Xray missing required capabilities: {error}")
        logger.info("Attempting to set capabilities automatically...")

        xray_binary = self.get_effective_xray_binary()
        success, set_error = self.set_xray_capabilities(xray_binary)

        if success:
            logger.info("Successfully set xray capabilities")
            return True, "Capabilities set successfully"

        error_msg = f"Failed to set capabilities: {set_error}"
        logger.error(error_msg)
        logger.error(f"Please run manually: sudo setcap cap_net_admin,cap_net_raw+ep {xray_binary}")
        return False, error_msg

    def start_single_server(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: dict,
        socks_port: int | None = None,
        http_port: int | None = None,
    ) -> tuple[bool, str | None]:
        """Start a single server (stops any currently running server first).

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)

        """
        # Stop any currently running server first
        if self.current_server_id and self.is_server_running(self.current_server_id):
            logger.info(
                f"Stopping current server {self.current_server_id} before starting new one",
            )
            self.stop_server(self.current_server_id)

        # Start the new server with port overrides
        success, error_msg = self.start_server(
            server_id,
            subscription_id,
            config,
            socks_port,
            http_port,
        )
        if success:
            self.current_server_id = server_id

        return success, error_msg

    def _apply_port_overrides(
        self,
        config: dict,
        socks_port: int | None,
        http_port: int | None,
    ) -> dict:
        """Apply global port overrides to inbound configurations at runtime."""
        if not config.get("inbounds") or (not socks_port and not http_port):
            return config
        modified_config = deepcopy(config)

        for inbound in modified_config.get("inbounds", []):
            tag = inbound.get("tag", "").lower()

            if socks_port and "socks" in tag:
                original_port = inbound.get("port")
                inbound["port"] = socks_port
                logger.info(f"Overriding SOCKS port: {original_port} -> {socks_port}")
            elif http_port and "http" in tag:
                original_port = inbound.get("port")
                inbound["port"] = http_port
                logger.info(f"Overriding HTTP port: {original_port} -> {http_port}")

        return modified_config

    def _apply_log_level_override(self, config: dict) -> dict:
        """Apply global log level override to xray configuration."""
        try:
            db_settings = db.get_settings()
            if db_settings.xray_log_level:
                modified_config = deepcopy(config)

                # Ensure log section exists
                if "log" not in modified_config:
                    modified_config["log"] = {}

                # Override the log level
                original_level = modified_config["log"].get("loglevel", "warning")
                modified_config["log"]["loglevel"] = db_settings.xray_log_level

                logger.info(
                    f"Overriding xray log level: {original_level} -> {db_settings.xray_log_level}",
                )
                return modified_config
        except Exception as e:
            logger.warning(f"Failed to apply log level override: {e}")

        return config

    def _ensure_direct_outbound(self, config: dict) -> dict:
        """Ensure that a 'direct' outbound with 'direct' tag exists in the configuration."""
        modified_config = deepcopy(config)

        # Ensure outbounds section exists
        if "outbounds" not in modified_config:
            modified_config["outbounds"] = []

        # Check if 'direct' tag already exists
        has_direct_outbound = any(
            outbound.get("tag", "").lower() == "direct" for outbound in modified_config["outbounds"]
        )

        if not has_direct_outbound:
            # Append default 'direct' outbound configuration
            direct_outbound = {
                "protocol": "freedom",
                "tag": "direct",
                "settings": {},
            }
            modified_config["outbounds"].append(direct_outbound)
            logger.info("Added missing 'direct' outbound to configuration")

        return modified_config

    def _ensure_bypass_outbound(self, config: dict) -> dict:
        """Ensure a freedom outbound tagged 'bypass' exists."""
        modified_config = deepcopy(config)
        if "outbounds" not in modified_config:
            modified_config["outbounds"] = []

        has_bypass = any(outbound.get("tag", "").lower() == "bypass" for outbound in modified_config["outbounds"])
        if not has_bypass:
            modified_config["outbounds"].append(
                {
                    "protocol": "freedom",
                    "tag": "bypass",
                    "settings": {},
                },
            )
            logger.info("Added missing 'bypass' outbound to configuration")

        return modified_config

    def _ensure_block_outbound(self, config: dict) -> dict:
        """Ensure a blackhole outbound tagged 'block' exists."""
        modified_config = deepcopy(config)
        if "outbounds" not in modified_config:
            modified_config["outbounds"] = []

        has_block = any(outbound.get("tag", "").lower() == "block" for outbound in modified_config["outbounds"])
        if not has_block:
            modified_config["outbounds"].append(
                {
                    "protocol": "blackhole",
                    "tag": "block",
                    "settings": {},
                },
            )
            logger.info("Added missing 'block' outbound to configuration")

        return modified_config

    def _resolve_proxy_outbound_tag(self, config: dict) -> str | None:
        """Pick the primary proxy outbound tag from the config."""
        outbounds = config.get("outbounds") or []
        if not outbounds:
            return None

        reserved_tags = {"direct", "bypass", "block", "blocked", "reject", "blackhole", "dns-out", "api"}
        reserved_protocols = {"freedom", "blackhole", "dns", "loopback"}

        for outbound in outbounds:
            tag = str(outbound.get("tag") or "").strip()
            if tag.lower() == "proxy":
                return tag

        for outbound in outbounds:
            tag = str(outbound.get("tag") or "").strip()
            protocol = str(outbound.get("protocol") or "").strip().lower()
            if not tag:
                continue
            if tag.lower() in reserved_tags:
                continue
            if protocol in reserved_protocols:
                continue
            return tag

        first = outbounds[0]
        tag = str(first.get("tag") or "").strip()
        return tag or None

    def _build_xray_rule_from_settings(self, rule, proxy_tag: str | None) -> dict | None:
        """Convert a settings routing rule into an Xray routing rule."""
        action = getattr(rule, "action", None)
        action_value = action.value if hasattr(action, "value") else str(action or "")

        if action_value == "bypass":
            outbound_tag = "bypass"
        elif action_value == "block":
            outbound_tag = "block"
        elif action_value == "proxy":
            if not proxy_tag:
                logger.warning("Skipping proxy routing rule because no proxy outbound was found")
                return None
            outbound_tag = proxy_tag
        else:
            logger.warning(f"Skipping routing rule with unknown action: {action_value}")
            return None

        xray_rule: dict = {
            "type": "field",
            "outboundTag": outbound_tag,
        }

        domains = [item for item in getattr(rule, "domain", []) or [] if item]
        ips = [item for item in getattr(rule, "ip", []) or [] if item]
        protocols = [item for item in getattr(rule, "protocol", []) or [] if item]
        processes = [item for item in getattr(rule, "process", []) or [] if item]
        port = getattr(rule, "port", None)

        if domains:
            xray_rule["domain"] = domains
        if ips:
            xray_rule["ip"] = ips
        if port:
            xray_rule["port"] = port
        if protocols:
            xray_rule["protocol"] = protocols
        if processes:
            xray_rule["process"] = processes

        if not any([domains, ips, port, protocols, processes]):
            return None

        rule_name = getattr(rule, "name", None)
        rule_id = getattr(rule, "id", None)
        if rule_name:
            xray_rule["ruleTag"] = rule_name
        elif rule_id:
            xray_rule["ruleTag"] = f"nabzram-{rule_id}"

        return xray_rule

    def _apply_custom_routing_rules(self, config: dict) -> dict:
        """Prepend user-defined routing rules from settings."""
        try:
            db_settings = db.get_settings()
            rules = getattr(db_settings, "routing_rules", None) or []
        except Exception as e:
            logger.warning(f"Failed to read routing_rules setting: {e}")
            return config

        enabled_rules = [rule for rule in rules if getattr(rule, "enabled", True)]
        if not enabled_rules:
            return config

        modified_config = deepcopy(config)
        if "routing" not in modified_config:
            modified_config["routing"] = {}
        if "rules" not in modified_config["routing"]:
            modified_config["routing"]["rules"] = []

        proxy_tag = self._resolve_proxy_outbound_tag(modified_config)
        custom_rules: list[dict] = []
        for rule in enabled_rules:
            xray_rule = self._build_xray_rule_from_settings(rule, proxy_tag)
            if xray_rule:
                custom_rules.append(xray_rule)

        if not custom_rules:
            return modified_config

        # Custom rules should win over subscription/default rules.
        modified_config["routing"]["rules"] = custom_rules + modified_config["routing"]["rules"]
        logger.info(f"Applied {len(custom_rules)} custom routing rule(s)")
        return modified_config

    def _apply_dns_hijack(self, config: dict) -> dict:
        """Add or remove dns-out outbound and port-53 hijack route based on settings."""
        dns_hijack = True
        try:
            dns_hijack = bool(getattr(db.get_settings(), "dns_hijack", True))
        except Exception as e:
            logger.warning(f"Failed to read dns_hijack setting: {e}")

        modified_config = deepcopy(config)
        if "outbounds" not in modified_config:
            modified_config["outbounds"] = []
        if "routing" not in modified_config:
            modified_config["routing"] = {}
        if "rules" not in modified_config["routing"]:
            modified_config["routing"]["rules"] = []

        # Always strip previous nabzram dns-out pieces so toggling off is clean.
        modified_config["outbounds"] = [
            outbound for outbound in modified_config["outbounds"] if outbound.get("tag", "").lower() != "dns-out"
        ]
        modified_config["routing"]["rules"] = [
            rule
            for rule in modified_config["routing"]["rules"]
            if not (
                str(rule.get("outboundTag", "")).lower() == "dns-out"
                and str(rule.get("port", "")) == "53"
                and not rule.get("domain")
                and not rule.get("ip")
                and not rule.get("protocol")
                and not rule.get("process")
            )
        ]

        if not dns_hijack:
            return modified_config

        proxy_tag = self._resolve_proxy_outbound_tag(modified_config)
        if not proxy_tag:
            logger.warning("DNS hijack enabled but no proxy outbound was found; skipping")
            return modified_config

        dns_outbound = {
            "tag": "dns-out",
            "protocol": "dns",
            "settings": {
                "rewriteAddress": "1.1.1.1",
                "rewriteNetwork": "udp",
                "port": 53,
            },
            "proxySettings": {
                "tag": proxy_tag,
            },
        }
        modified_config["outbounds"].append(dns_outbound)

        dns_rule = {
            "type": "field",
            "port": "53",
            "outboundTag": "dns-out",
            "ruleTag": "nabzram-dns-hijack",
        }
        # Highest priority so DNS is always captured when enabled.
        modified_config["routing"]["rules"] = [dns_rule, *modified_config["routing"]["rules"]]
        logger.info(f"Applied DNS hijack via dns-out -> {proxy_tag}")
        return modified_config

    def _ensure_routing_rules(self, config: dict) -> dict:
        """Ensure that routing rules for private IPs and domains exist."""
        modified_config = deepcopy(config)

        # Ensure routing section exists
        if "routing" not in modified_config:
            modified_config["routing"] = {}
        if "rules" not in modified_config["routing"]:
            modified_config["routing"]["rules"] = []

        # Expected rules for private IPs and domains
        expected_rules = [
            {
                "ip": ["geoip:private"],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": ["geosite:private"],
                "outboundTag": "direct",
                "type": "field",
            },
        ]

        # Track which rules exist
        existing_rules = modified_config["routing"]["rules"]
        added_any = False

        # Check for IP rule (geoip:private)
        has_ip_rule = any(
            rule.get("type") == "field" and rule.get("outboundTag") == "direct" and rule.get("ip") == ["geoip:private"]
            for rule in existing_rules
        )

        if not has_ip_rule:
            existing_rules.append(expected_rules[0])
            added_any = True
            logger.info("Added missing routing rule for geoip:private")

        # Check for domain rule (geosite:private)
        has_domain_rule = any(
            rule.get("type") == "field"
            and rule.get("outboundTag") == "direct"
            and rule.get("domain") == ["geosite:private"]
            for rule in existing_rules
        )

        if not has_domain_rule:
            existing_rules.append(expected_rules[1])
            added_any = True
            logger.info("Added missing routing rule for geosite:private")

        if not added_any and len(existing_rules) == 0:
            logger.debug("Routing rules already exist or were added")

        return modified_config

    def _ensure_sockopt_mark(self, config: dict) -> dict:
        """Ensure all outbounds have streamSettings.sockopt.mark = 438 on Linux."""
        if platform.system() != "Linux":
            return config

        modified_config = deepcopy(config)

        # Ensure outbounds section exists
        if "outbounds" not in modified_config:
            return modified_config

        modified = False
        for outbound in modified_config["outbounds"]:
            # Ensure streamSettings exists
            if "streamSettings" not in outbound:
                outbound["streamSettings"] = {}

            # Ensure sockopt exists
            if "sockopt" not in outbound["streamSettings"]:
                outbound["streamSettings"]["sockopt"] = {}

            # Set mark to 438 if not already set
            current_mark = outbound["streamSettings"]["sockopt"].get("mark")
            if current_mark != 438:
                outbound["streamSettings"]["sockopt"]["mark"] = 438
                modified = True

        if modified:
            logger.info("Applied sockopt.mark = 438 to all outbounds on Linux")

        return modified_config

    def _get_tun_interface_name(self) -> str:
        """Pick a platform-appropriate TUN interface name that is not already in use."""
        system = platform.system()
        if system == "Darwin":
            existing: set[str] = set()
            try:
                output = subprocess.check_output(
                    ["ifconfig", "-l"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                existing = set(output.split())
            except (OSError, subprocess.SubprocessError) as e:
                logger.warning(f"Could not list macOS interfaces for TUN naming: {e}")

            for index in range(256):
                name = f"utun{index}"
                if name not in existing:
                    return name
            return "utun0"

        # Windows (Wintun) and Linux use a dedicated adapter name.
        return "nabzram0"

    def _build_tun_inbound(self) -> dict:
        """Build the TUN inbound configuration for the current platform."""
        return {
            "tag": "tun",
            "protocol": "tun",
            "settings": {
                "name": self._get_tun_interface_name(),
                "desc": "Wintun",
                "mtu": 1500,
                "gateway": [
                    "172.19.0.1/16",
                    "fd00::1/64",
                ],
                "dns": [
                    "1.1.1.1",
                    "8.8.8.8",
                ],
                "autoSystemRoutingTable": [
                    "0.0.0.0/0",
                    "::/0",
                ],
                "autoOutboundsInterface": "auto",
            },
            "sniffing": {
                "destOverride": [
                    "http",
                    "tls",
                    "fakedns",
                ],
                "enabled": True,
                "metadataOnly": False,
                "routeOnly": True,
            },
        }

    def _ensure_tun_inbound(self, config: dict) -> dict:
        """Add or remove the TUN inbound based on the tun_mode setting."""
        tun_mode = False
        try:
            db_settings = db.get_settings()
            tun_mode = bool(getattr(db_settings, "tun_mode", False))
        except Exception as e:
            logger.warning(f"Failed to read tun_mode setting: {e}")

        modified_config = deepcopy(config)
        if "inbounds" not in modified_config:
            modified_config["inbounds"] = []

        # Always strip any existing tun inbound so toggles off cleanly.
        before_count = len(modified_config["inbounds"])
        modified_config["inbounds"] = [
            inbound
            for inbound in modified_config["inbounds"]
            if inbound.get("tag", "").lower() != "tun" and inbound.get("protocol", "").lower() != "tun"
        ]
        removed = before_count - len(modified_config["inbounds"])
        if removed:
            logger.info(f"Removed {removed} existing TUN inbound(s) from configuration")

        if not tun_mode:
            return modified_config

        tun_inbound = self._build_tun_inbound()
        modified_config["inbounds"].append(tun_inbound)
        logger.info(
            f"Added TUN inbound with interface name '{tun_inbound['settings']['name']}'",
        )
        return modified_config

    def start_server(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: dict,
        socks_port: int | None = None,
        http_port: int | None = None,
        is_test: bool = False,
    ) -> tuple[bool, str | None]:
        """Start a server with the given configuration and optional port overrides.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)

        """
        if server_id in self.running_processes:
            logger.warning(f"Server {server_id} is already running")
            return False, None

        try:
            # Apply port overrides at runtime (not stored in database)
            runtime_config = self._apply_port_overrides(config, socks_port, http_port)

            # Apply log level override at runtime (not stored in database)
            runtime_config = self._apply_log_level_override(runtime_config)

            # Ensure direct outbound exists
            runtime_config = self._ensure_direct_outbound(runtime_config)

            # Ensure bypass/block outbounds for custom routing actions
            runtime_config = self._ensure_bypass_outbound(runtime_config)
            runtime_config = self._ensure_block_outbound(runtime_config)

            # Ensure routing rules exist
            runtime_config = self._ensure_routing_rules(runtime_config)

            # Apply user-defined routing rules (prepended for precedence)
            runtime_config = self._apply_custom_routing_rules(runtime_config)

            # Hijack DNS port 53 through dns-out when enabled
            runtime_config = self._apply_dns_hijack(runtime_config)

            # Ensure sockopt.mark = 438 on Linux
            runtime_config = self._ensure_sockopt_mark(runtime_config)

            # Inject TUN inbound when TUN mode is enabled (skip for URL tests)
            tun_mode = False
            if not is_test:
                runtime_config = self._ensure_tun_inbound(runtime_config)
                try:
                    tun_mode = bool(getattr(db.get_settings(), "tun_mode", False))
                except Exception as e:
                    logger.warning(f"Failed to read tun_mode setting: {e}")

            # ENSURE xray has required capabilities on Linux (set them if missing)
            if not is_test and platform.system() == "Linux":
                self.ensure_xray_capabilities()

            # Convert config to JSON string with UUID support
            config_json = json.dumps(runtime_config, indent=2, cls=UUIDEncoder)

            # open(f"config_{server_id}.json", "w").write(config_json)

            logger.debug(
                f"Starting server {server_id} with config size: {len(config_json)} bytes",
            )

            # Get effective xray binary and assets folder
            xray_binary = self.get_effective_xray_binary()
            xray_assets_folder = self.get_xray_assets_folder()

            # Prepare environment variables
            env = None
            if xray_assets_folder:
                env = os.environ.copy()
                env["XRAY_LOCATION_ASSET"] = xray_assets_folder
                logger.info(
                    f"Setting XRAY_LOCATION_ASSET environment variable to: {xray_assets_folder}",
                )

            # Create subprocess. TUN mode needs administrator privileges.
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = subprocess.CREATE_NO_WINDOW

            if tun_mode:
                with NamedTemporaryFile(
                    mode="w",
                    suffix=".json",
                    prefix="nabzram-xray-",
                    delete=False,
                    encoding="utf-8",
                ) as config_file:
                    config_file.write(config_json)
                    config_path = config_file.name
                self._temp_config_paths[server_id] = config_path
                logger.info(
                    f"Starting server {server_id} in TUN mode with elevated privileges",
                )
                process = popen_elevated(
                    [xray_binary, "run", "-config", config_path],
                    env=env,
                )
            else:
                process = subprocess.Popen(
                    [xray_binary, "run", "-config", "stdin:"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=creationflags,
                )

                # Send config via stdin
                process.stdin.write(config_json.encode())
                process.stdin.close()

            # Store process information with runtime config (including port overrides)
            process_info = ProcessInfo(
                server_id=server_id,
                subscription_id=subscription_id,
                process_id=process.pid,
                start_time=datetime.now(),
                config=runtime_config,  # Store the config with applied overrides
            )

            self.running_processes[server_id] = process_info
            self.process_handles[server_id] = process

            # Create log queue for this server with limited size
            self.log_queues[server_id] = Queue(maxsize=200)

            # Start log reading thread
            log_thread = threading.Thread(
                target=self._read_process_logs,
                args=(server_id, process),
                daemon=True,
            )
            log_thread.start()
            self.log_threads[server_id] = log_thread

            # Give the process a moment to start and check if it's still running
            # Elevated starts may wait on a password prompt; allow a bit longer.
            time.sleep(1.0 if tun_mode else 0.1)

            if process.poll() is not None:
                # Process died immediately, clean up and return failure
                logger.error(
                    f"Server {server_id} process died immediately with return code {process.returncode}",
                )

                # Try to read any error output
                error_details = f"Process exited with code {process.returncode}"
                try:
                    remaining_output = process.stdout.read() if process.stdout else b""
                    if remaining_output:
                        error_msg = remaining_output.decode(
                            "utf-8",
                            errors="ignore",
                        ).strip()
                        logger.error(f"Server {server_id} error output: {error_msg}")
                        error_details = f"Process exited with code {process.returncode}. Error: {error_msg}"
                except Exception as ex:
                    logger.debug(f"Failed to read error output: {ex}")

                # Clean up
                self._cleanup_temp_config(server_id)
                if server_id in self.running_processes:
                    del self.running_processes[server_id]
                if server_id in self.process_handles:
                    del self.process_handles[server_id]
                if server_id in self.log_queues:
                    del self.log_queues[server_id]
                if server_id in self.log_threads:
                    del self.log_threads[server_id]
                return False, error_details

            logger.info(f"Started server {server_id} with PID {process.pid}")
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Failed to start server {server_id}: {error_msg}")

            # Clean up on exception
            self._cleanup_temp_config(server_id)
            if server_id in self.running_processes:
                del self.running_processes[server_id]

            if server_id in self.process_handles:
                del self.process_handles[server_id]
            if server_id in self.log_queues:
                del self.log_queues[server_id]
            if server_id in self.log_threads:
                del self.log_threads[server_id]

            return False, f"Failed to start server: {error_msg}"

    def _cleanup_temp_config(self, server_id: UUID) -> None:
        """Remove a temporary config file created for elevated TUN starts."""
        config_path = self._temp_config_paths.pop(server_id, None)
        if not config_path:
            return
        try:
            os.unlink(config_path)
        except OSError as e:
            logger.debug(f"Failed to remove temp config {config_path}: {e}")

    def stop_server(self, server_id: UUID) -> bool:
        """Stop a running server."""
        if server_id not in self.running_processes:
            logger.warning(f"Server {server_id} is not running")
            return False

        try:
            process = self.process_handles[server_id]

            # Try graceful termination first
            process.terminate()

            # Wait for process to terminate
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if doesn't terminate gracefully
                process.kill()
                process.wait()

            # Clean up
            del self.running_processes[server_id]
            del self.process_handles[server_id]
            self._cleanup_temp_config(server_id)

            # Clean up log queue and thread
            if server_id in self.log_queues:
                del self.log_queues[server_id]
            if server_id in self.log_threads:
                del self.log_threads[server_id]

            # Clear current server if this was it
            if self.current_server_id == server_id:
                self.current_server_id = None

            logger.info(f"Stopped server {server_id}")
            return True

        except Exception as e:
            logger.exception(f"Failed to stop server {server_id}: {e}")
            return False

    def restart_server(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: dict,
        socks_port: int | None = None,
        http_port: int | None = None,
    ) -> tuple[bool, str | None]:
        """Restart a server with optional port overrides.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)

        """
        if server_id in self.running_processes:
            self.stop_server(server_id)
            # Small delay to ensure clean shutdown
            time.sleep(1)

        return self.start_server(
            server_id,
            subscription_id,
            config,
            socks_port,
            http_port,
        )

    def is_server_running(self, server_id: UUID) -> bool:
        """Check if a server is currently running."""
        if server_id not in self.running_processes:
            return False

        process = self.process_handles.get(server_id)
        if process is None:
            return False

        # Check if process is still alive
        if process.poll() is not None:
            # Process has terminated, clean up
            if server_id in self.running_processes:
                del self.running_processes[server_id]
            if server_id in self.process_handles:
                del self.process_handles[server_id]
            if server_id in self.log_queues:
                del self.log_queues[server_id]
            if server_id in self.log_threads:
                del self.log_threads[server_id]
            return False

        return True

    def get_process_info(self, server_id: UUID) -> ProcessInfo | None:
        """Get process information for a server."""
        return self.running_processes.get(server_id)

    def get_server_ports(self, server_id: UUID) -> list[int]:
        """Get the allocated ports for a server (legacy method for backward compatibility)."""
        port_info = self.get_server_port_info(server_id)
        return [port["port"] for port in port_info]

    def get_server_port_info(self, server_id: UUID) -> list[dict[str, any]]:
        """Get detailed port information including protocols for a server."""
        if server_id not in self.running_processes:
            return []

        process_info = self.running_processes[server_id]
        config = process_info.config
        port_info = []

        if config and "inbounds" in config:
            for inbound in config["inbounds"]:
                if "port" in inbound:
                    protocol = self._extract_protocol_from_tag(inbound)

                    port_info.append(
                        {
                            "port": inbound["port"],
                            "protocol": protocol,
                            "tag": inbound.get("tag", None),
                        },
                    )

        return port_info

    def _extract_protocol_from_tag(self, inbound: dict) -> str:
        """Extract protocol type from configuration."""
        # Check inbound protocol field if available
        if "protocol" in inbound:
            return inbound["protocol"]

        # Default fallback
        return "unknown"

    # Single server convenience methods
    def get_current_server_id(self) -> UUID | None:
        """Get the currently running server ID."""
        return self.current_server_id

    def is_any_server_running(self) -> bool:
        """Check if any server is currently running."""
        return self.current_server_id is not None and self.is_server_running(
            self.current_server_id,
        )

    def get_current_server_info(self) -> ProcessInfo | None:
        """Get process information for the currently running server."""
        if self.current_server_id:
            return self.get_process_info(self.current_server_id)
        return None

    def get_current_server_ports(self) -> list[int]:
        """Get ports for the currently running server."""
        if self.current_server_id:
            return self.get_server_ports(self.current_server_id)
        return []

    def get_current_server_port_info(self) -> list[dict[str, any]]:
        """Get detailed port information for the currently running server."""
        if self.current_server_id:
            return self.get_server_port_info(self.current_server_id)
        return []

    def stop_current_server(self) -> bool:
        """Stop the currently running server."""
        if self.current_server_id:
            return self.stop_server(self.current_server_id)
        return True  # No server running, consider it success

    def restart_current_server(
        self,
        subscription_id: UUID,
        config: dict,
        socks_port: int | None = None,
        http_port: int | None = None,
    ) -> tuple[bool, str | None]:
        """Restart the currently running server with new config and port overrides.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)

        """
        if self.current_server_id:
            return self.restart_server(
                self.current_server_id,
                subscription_id,
                config,
                socks_port,
                http_port,
            )
        return False, "No server is currently running"

    def _read_process_logs(self, server_id: UUID, process: subprocess.Popen) -> None:
        """Read logs from a process and queue them."""
        try:
            if process.stdout is None:
                logger.debug(f"No stdout pipe for server {server_id}; skipping log reader")
                return

            while True:
                # Use readline to avoid blocking
                line_bytes = process.stdout.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Queue the log line
                if server_id in self.log_queues:
                    try:
                        self.log_queues[server_id].put(
                            {
                                "timestamp": datetime.now(),
                                "server_id": server_id,
                                "message": line,
                            },
                            block=False,
                        )
                    except Exception:
                        # Queue is full or other error, skip this log entry
                        pass

        except Exception as e:
            logger.exception(f"Error reading logs for server {server_id}: {e}")
        finally:
            logger.debug(f"Log reading thread for server {server_id} ended")

    def get_server_logs(self, server_id: UUID) -> Generator[dict]:
        """Get real-time logs for a specific server."""
        if server_id not in self.log_queues:
            return

        queue = self.log_queues[server_id]

        try:
            while True:
                # Wait for log message with timeout
                try:
                    log_entry = queue.get(timeout=1.0)
                    yield log_entry
                except Empty:
                    # Check if server is still running
                    if not self.is_server_running(server_id):
                        break
                    continue
        except Exception as e:
            logger.exception(f"Error streaming logs for server {server_id}: {e}")

    def get_current_server_logs(self) -> Generator[dict]:
        """Get real-time logs from the currently running server."""
        if self.current_server_id:
            for log_entry in self.get_server_logs(self.current_server_id):
                yield log_entry
        else:
            # No server running, just wait and check periodically
            while True:
                time.sleep(1)
                if self.current_server_id:
                    for log_entry in self.get_server_logs(self.current_server_id):
                        yield log_entry
                    break

    def get_log_snapshot(self, server_id: UUID, limit: int = 100) -> list[dict]:
        """Get a snapshot of recent logs from the queue."""
        if server_id not in self.log_queues:
            return []

        logs = []
        queue = self.log_queues[server_id]

        # Get all available logs from queue (non-blocking)
        while len(logs) < limit:
            try:
                log_entry = queue.get_nowait()
                logs.append(
                    {
                        "timestamp": log_entry["timestamp"].isoformat(),
                        "message": log_entry["message"],
                    },
                )
            except Empty:
                break

        return logs

    def get_logs_since(
        self,
        server_id: UUID,
        since_ms: int,
        limit: int = 200,
    ) -> list[dict]:
        """Get logs since a timestamp from the queue."""
        if server_id not in self.log_queues:
            return []

        logs = []
        queue = self.log_queues[server_id]

        # Get all available logs from queue (non-blocking)
        while len(logs) < limit:
            try:
                log_entry = queue.get_nowait()
                log_timestamp_ms = int(log_entry["timestamp"].timestamp() * 1000)

                # Filter by timestamp
                if log_timestamp_ms > since_ms:
                    logs.append(
                        {
                            "timestamp": log_entry["timestamp"].isoformat(),
                            "message": log_entry["message"],
                        },
                    )
            except Empty:
                break

        return logs

    def shutdown_all(self) -> None:
        """Shutdown all running servers."""
        server_ids = list(self.running_processes.keys())
        for server_id in server_ids:
            self.stop_server(server_id)

        logger.info("All servers stopped")

    def _find_available_port(self, start_port: int = 10800) -> int:
        """Find an available port starting from start_port."""
        port = start_port
        while port < 65535:
            if self._is_port_available(port):
                return port
            port += 1
        msg = "No available ports found"
        raise RuntimeError(msg)

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available for binding."""
        try:
            with socket(AF_INET, SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def _wait_for_port(self, port: int, timeout: float = 5.0) -> bool:
        """Wait until the given port is open (listening) on localhost, or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                with socket(AF_INET, SOCK_STREAM) as sock:
                    sock.settimeout(0.2)
                    sock.connect(("127.0.0.1", port))
                    return True
            except Exception:
                time.sleep(0.05)
        return False

    def _allocate_random_ports(self) -> tuple[int, int]:
        """Allocate random available ports for SOCKS and HTTP."""
        # Find random starting points to avoid conflicts
        socks_start = randint(10800, 20000)
        http_start = randint(20001, 30000)

        socks_port = self._find_available_port(socks_start)
        http_port = self._find_available_port(http_start)

        # Ensure ports are different
        while http_port == socks_port:
            http_port = self._find_available_port(http_port + 1)

        return socks_port, http_port

    def test_server_connectivity(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: dict,
        test_timeout: int = 6,
    ) -> tuple[bool, int | None, str | None, int, int]:
        """Test server connectivity by starting it on random ports and making HTTP request
        Returns: (success, ping_ms, error_message, socks_port, http_port).
        """
        socks_port, http_port = self._allocate_random_ports()

        try:
            if server_id == self.current_server_id:
                ports = self.get_current_server_port_info()
                for p in ports:
                    if p["protocol"] == "socks":
                        socks_port = p["port"]
                    if p["protocol"] == "http":
                        http_port = p["port"]

            else:
                # Start server with random ports
                success, error_msg = self.start_server(
                    server_id,
                    subscription_id,
                    config,
                    socks_port,
                    http_port,
                    is_test=True,
                )
                if not success:
                    error_detail = error_msg or "Failed to start server"
                    return False, None, error_detail, socks_port, http_port

                # Wait a moment for server to fully start
                self._wait_for_port(http_port, timeout=2.0)

            # First, make a "warm-up" request to let the proxy initiate its connection
            proxies = {
                "http": f"http://127.0.0.1:{http_port}",
                "https": f"http://127.0.0.1:{http_port}",
            }
            try:
                # Warm-up request (ignore result, just to trigger connection)
                http_get(
                    "http://gstatic.com/generate_204",
                    proxies=proxies,
                    timeout=1,
                )
            except Exception:
                # Ignore any errors in warm-up
                pass

            # Now measure the ping with the real test request
            start_time = time.time()
            try:
                response = http_get(
                    "http://gstatic.com/generate_204",
                    proxies=proxies,
                    timeout=test_timeout,
                )

                if response.status_code == 204:
                    ping_ms = int((time.time() - start_time) * 1000)
                    return True, ping_ms, None, socks_port, http_port
                return (
                    False,
                    None,
                    f"HTTP {response.status_code}",
                    socks_port,
                    http_port,
                )

            except Timeout:
                return False, None, "Connection timeout", socks_port, http_port
            except RequestException as e:
                return False, None, f"Connection error: {e!s}", socks_port, http_port

        except Exception as e:
            return False, None, f"Test error: {e!s}", socks_port, http_port
        finally:
            # Always stop the test server
            try:
                if server_id != self.current_server_id and server_id in self.running_processes:
                    self.stop_server(server_id)
            except Exception:
                pass

    def test_subscription_servers(
        self,
        subscription_servers: list,
        subscription_id: UUID,
        test_timeout: int = 6,
    ) -> list[dict]:
        """Test all servers in a subscription in parallel.
        Returns list of test results.
        """

        def test_one(server):
            try:
                success, ping_ms, error, socks_port, http_port = self.test_server_connectivity(
                    server.id,
                    subscription_id,
                    server.raw,
                    test_timeout,
                )
                return {
                    "server_id": server.id,
                    "remarks": server.remarks,
                    "success": success,
                    "ping_ms": ping_ms,
                    "error": error,
                    "socks_port": socks_port,
                    "http_port": http_port,
                }
            except Exception as e:
                return {
                    "server_id": server.id,
                    "remarks": server.remarks,
                    "success": False,
                    "ping_ms": None,
                    "error": f"Test failed: {e!s}",
                    "socks_port": 0,
                    "http_port": 0,
                }

        results = []
        # Use ThreadPoolExecutor for parallel testing
        with ThreadPoolExecutor(max_workers=min(8, len(subscription_servers) or 1)) as executor:
            future_to_server = {executor.submit(test_one, server): server for server in subscription_servers}
            for future in as_completed(future_to_server):
                result = future.result()
                results.append(result)

        # Optionally, sort results to match input order
        server_id_to_result = {r["server_id"]: r for r in results}
        ordered_results = [
            server_id_to_result.get(server.id) for server in subscription_servers if server_id_to_result.get(server.id)
        ]
        return ordered_results


# Global process manager instance
process_manager = ProcessManager()
