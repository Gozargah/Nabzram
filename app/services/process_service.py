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
from uuid import UUID

import netifaces
from requests import get as http_get
from requests.exceptions import RequestException, Timeout

from app.database import db
from app.models.database import ProcessInfo

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

    def get_default_network_interface(self) -> str | None:
        """Get the default network interface for the current system."""
        try:
            # Get the interface associated with the default gateway
            default_gateway = netifaces.gateways().get("default", {})
            if default_gateway:
                for family in default_gateway.keys():
                    gateway_info = default_gateway[family]
                    if isinstance(gateway_info, tuple) and len(gateway_info) >= 2:
                        interface = gateway_info[1]
                        logger.info(f"Detected default network interface: {interface}")
                        return interface

            # Fallback: find the first non-loopback interface with an IP
            interfaces = netifaces.interfaces()
            for interface in interfaces:
                if interface.startswith("lo"):
                    continue  # Skip loopback interfaces

                addr_info = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addr_info:
                    addrs = addr_info[netifaces.AF_INET]
                    for addr in addrs:
                        ip = addr.get("addr", "")
                        if ip and not ip.startswith("127."):  # Not loopback
                            logger.info(f"Fallback: Using network interface: {interface}")
                            return interface

        except Exception as e:
            logger.warning(f"Failed to detect default network interface: {e}")
            return None

        logger.warning("No suitable network interface found")
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

    def _apply_default_network_interface(self, config: dict) -> dict:
        """Apply default network interface to outbound configurations that don't have streamSettings.sockopt.interface defined."""
        try:
            default_interface = self.get_default_network_interface()
            if not default_interface:
                logger.debug("No default network interface available, skipping interface injection")
                return config

            modified_config = deepcopy(config)
            outbounds = modified_config.get("outbounds", [])

            if not outbounds:
                return modified_config

            interface_added_count = 0

            for outbound in outbounds:
                # Skip if outbound already has sockopt.interface defined
                stream_settings = outbound.get("streamSettings", {})
                sockopt = stream_settings.get("sockopt", {})

                if "interface" in sockopt:
                    logger.debug(
                        f"Outbound {outbound.get('tag', '-')} already has interface defined: {sockopt.get('interface')}"
                    )
                    continue

                # Add default interface to this outbound
                if "streamSettings" not in outbound:
                    outbound["streamSettings"] = {}
                if "sockopt" not in outbound["streamSettings"]:
                    outbound["streamSettings"]["sockopt"] = {}

                outbound["streamSettings"]["sockopt"]["interface"] = default_interface

                download_settings = (
                    stream_settings.get("xhttpSettings", {}).get("extra", {}).get("downloadSettings", {})
                )

                if download_settings:
                    if "sockopt" not in download_settings:
                        download_settings["sockopt"] = {}
                    if "interface" not in download_settings["sockopt"]:
                        download_settings["sockopt"]["interface"] = default_interface

                interface_added_count += 1

                logger.debug(f"Added default interface '{default_interface}' to outbound {outbound.get('tag', '-')}")

            if interface_added_count > 0:
                logger.info(
                    f"Applied default network interface '{default_interface}' to {interface_added_count} outbound(s)"
                )

            return modified_config

        except Exception as e:
            logger.warning(f"Failed to apply default network interface: {e}")
            return config

    def start_server(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: dict,
        socks_port: int | None = None,
        http_port: int | None = None,
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

            # Apply default network interface to outbounds at runtime (not stored in database)
            runtime_config = self._apply_default_network_interface(runtime_config)

            # Convert config to JSON string with UUID support
            config_json = json.dumps(runtime_config, indent=2, cls=UUIDEncoder)
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

            # Create subprocess
            # On Windows, hide the console window
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = subprocess.CREATE_NO_WINDOW

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
            time.sleep(0.1)

            if process.poll() is not None:
                # Process died immediately, clean up and return failure
                logger.error(
                    f"Server {server_id} process died immediately with return code {process.returncode}",
                )

                # Try to read any error output
                error_details = f"Process exited with code {process.returncode}"
                try:
                    remaining_output = process.stdout.read()
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
            if server_id in self.running_processes:
                del self.running_processes[server_id]

            if server_id in self.process_handles:
                del self.process_handles[server_id]
            if server_id in self.log_queues:
                del self.log_queues[server_id]
            if server_id in self.log_threads:
                del self.log_threads[server_id]

            return False, f"Failed to start server: {error_msg}"

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
