"""
Xray-core process management service
"""

import asyncio
import json
import logging
import os
import platform
from copy import deepcopy
from datetime import datetime
from random import randint
from shutil import which
from socket import AF_INET, SOCK_STREAM, socket
from time import time
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from uuid import UUID

from httpx import AsyncClient, TimeoutException

from app.core.config import get_settings
from app.dependencies import get_global_database
from app.models.database import ProcessInfo

logger = logging.getLogger(__name__)


class UUIDEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles UUID objects"""

    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ProcessManager:
    """Manages xray-core processes"""

    def __init__(self):
        self.settings = get_settings()
        self.running_processes: Dict[UUID, ProcessInfo] = {}
        self.process_handles: Dict[UUID, asyncio.subprocess.Process] = {}
        self.log_queues: Dict[UUID, asyncio.Queue] = {}
        self.current_server_id: Optional[UUID] = (
            None  # Track the currently running server
        )

    @property
    def db(self):
        """Get the global database instance"""
        return get_global_database()

    def get_effective_xray_binary(self) -> str:
        """Get the effective xray binary path from database settings or system PATH"""
        try:
            db_settings = self.db.get_settings()
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
        elif platform.system() == "Windows":
            return "C:\\Program Files\\Xray\\xray.exe"
        else:
            return "/usr/bin/xray"

    def get_xray_assets_folder(self) -> Optional[str]:
        """Get the xray assets folder from database settings"""
        try:
            db_settings = self.db.get_settings()
            if db_settings.xray_assets_folder:
                return db_settings.xray_assets_folder
        except Exception as e:
            logger.warning(
                f"Failed to get xray_assets_folder from database settings: {e}"
            )

        # No fallback - return None if not set in database
        return None

    async def check_xray_availability(self) -> Dict[str, any]:
        """Check if xray-core is available and get version info"""
        try:
            # Try to run xray version command
            xray_binary = self.get_effective_xray_binary()

            # On Windows, hide the console window
            creationflags = 0
            if platform.system() == "Windows":
                import subprocess

                creationflags = subprocess.CREATE_NO_WINDOW

            process = await asyncio.create_subprocess_exec(
                xray_binary,
                "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creationflags,
            )

            stdout, stderr = await process.communicate()

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
                            r"go version ([^\s]+)", line, re.IGNORECASE
                        )
                        if go_version_match:
                            version_info["go_version"] = go_version_match.group(1)
                        arch_match = re.search(r"(amd64|arm64|386|arm)", line)
                        if arch_match:
                            version_info["arch"] = arch_match.group(1)
                    elif "/" in line and any(
                        arch in line for arch in ["amd64", "arm64", "386", "arm"]
                    ):
                        # Try to extract arch from e.g. linux/amd64
                        arch_match = re.search(r"(amd64|arm64|386|arm)", line)
                        if arch_match:
                            version_info["arch"] = arch_match.group(1)

                return version_info
            else:
                return {"available": False, "error": stderr.decode().strip()}

        except FileNotFoundError:
            xray_binary = self.get_effective_xray_binary()
            return {
                "available": False,
                "error": f"xray binary not found: {xray_binary}",
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    async def start_single_server(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: Dict,
        socks_port: Optional[int] = None,
        http_port: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Start a single server (stops any currently running server first)

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        # Stop any currently running server first
        if self.current_server_id and self.is_server_running(self.current_server_id):
            logger.info(
                f"Stopping current server {self.current_server_id} before starting new one"
            )
            await self.stop_server(self.current_server_id)

        # Start the new server with port overrides
        success, error_msg = await self.start_server(
            server_id, subscription_id, config, socks_port, http_port
        )
        if success:
            self.current_server_id = server_id

        return success, error_msg

    def _apply_port_overrides(
        self, config: Dict, socks_port: Optional[int], http_port: Optional[int]
    ) -> Dict:
        """Apply global port overrides to inbound configurations at runtime"""
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

    def _apply_log_level_override(self, config: Dict) -> Dict:
        """Apply global log level override to xray configuration"""
        try:
            db_settings = self.db.get_settings()
            if db_settings.xray_log_level:
                modified_config = deepcopy(config)

                # Ensure log section exists
                if "log" not in modified_config:
                    modified_config["log"] = {}

                # Override the log level
                original_level = modified_config["log"].get("loglevel", "warning")
                modified_config["log"]["loglevel"] = db_settings.xray_log_level

                logger.info(
                    f"Overriding xray log level: {original_level} -> {db_settings.xray_log_level}"
                )
                return modified_config
        except Exception as e:
            logger.warning(f"Failed to apply log level override: {e}")

        return config

    async def start_server(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: Dict,
        socks_port: Optional[int] = None,
        http_port: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Start a server with the given configuration and optional port overrides

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

            # Convert config to JSON string with UUID support
            config_json = json.dumps(runtime_config, indent=2, cls=UUIDEncoder)
            logger.debug(
                f"Starting server {server_id} with config size: {len(config_json)} bytes"
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
                    f"Setting XRAY_LOCATION_ASSET environment variable to: {xray_assets_folder}"
                )

            # Create async subprocess
            # On Windows, hide the console window
            creationflags = 0
            if platform.system() == "Windows":
                import subprocess

                creationflags = subprocess.CREATE_NO_WINDOW

            process = await asyncio.create_subprocess_exec(
                xray_binary,
                "run",
                "-config",
                "stdin:",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024 * 1024,  # 1MB buffer limit
                env=env,
                creationflags=creationflags,
            )

            # Send config via stdin
            process.stdin.write(config_json.encode())
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()

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
            self.log_queues[server_id] = asyncio.Queue(maxsize=1000)

            # Start log reading task
            asyncio.create_task(self._read_process_logs(server_id, process))

            # Give the process a moment to start and check if it's still running
            await asyncio.sleep(0.1)

            if process.returncode is not None:
                # Process died immediately, clean up and return failure
                logger.error(
                    f"Server {server_id} process died immediately with return code {process.returncode}"
                )

                # Try to read any error output
                error_details = f"Process exited with code {process.returncode}"
                try:
                    remaining_output = await asyncio.wait_for(
                        process.stdout.read(), timeout=1.0
                    )
                    if remaining_output:
                        error_msg = remaining_output.decode(
                            "utf-8", errors="ignore"
                        ).strip()
                        logger.error(f"Server {server_id} error output: {error_msg}")
                        error_details = f"Process exited with code {process.returncode}. Error: {error_msg}"
                except asyncio.TimeoutError:
                    pass
                except Exception as ex:
                    logger.debug(f"Failed to read error output: {ex}")

                # Clean up
                if server_id in self.running_processes:
                    del self.running_processes[server_id]
                if server_id in self.process_handles:
                    del self.process_handles[server_id]
                if server_id in self.log_queues:
                    del self.log_queues[server_id]
                return False, error_details

            logger.info(f"Started server {server_id} with PID {process.pid}")
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to start server {server_id}: {error_msg}")

            # Clean up on exception
            if server_id in self.running_processes:
                del self.running_processes[server_id]

            if server_id in self.process_handles:
                del self.process_handles[server_id]
            if server_id in self.log_queues:
                del self.log_queues[server_id]

            return False, f"Failed to start server: {error_msg}"

    async def stop_server(self, server_id: UUID) -> bool:
        """Stop a running server"""
        if server_id not in self.running_processes:
            logger.warning(f"Server {server_id} is not running")
            return False

        try:
            process = self.process_handles[server_id]

            # Try graceful termination first
            process.terminate()

            # Wait for process to terminate
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                # Force kill if doesn't terminate gracefully
                process.kill()
                await process.wait()

            # Clean up
            del self.running_processes[server_id]
            del self.process_handles[server_id]

            # Clean up log queue
            if server_id in self.log_queues:
                del self.log_queues[server_id]

            # Clear current server if this was it
            if self.current_server_id == server_id:
                self.current_server_id = None

            logger.info(f"Stopped server {server_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop server {server_id}: {e}")
            return False

    async def restart_server(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: Dict,
        socks_port: Optional[int] = None,
        http_port: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Restart a server with optional port overrides

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        if server_id in self.running_processes:
            await self.stop_server(server_id)
            # Small delay to ensure clean shutdown
            await asyncio.sleep(1)

        return await self.start_server(
            server_id, subscription_id, config, socks_port, http_port
        )

    def is_server_running(self, server_id: UUID) -> bool:
        """Check if a server is currently running"""
        if server_id not in self.running_processes:
            return False

        process = self.process_handles.get(server_id)
        if process is None:
            return False

        # Check if process is still alive
        if process.returncode is not None:
            # Process has terminated, clean up
            if server_id in self.running_processes:
                del self.running_processes[server_id]
            if server_id in self.process_handles:
                del self.process_handles[server_id]
            if server_id in self.log_queues:
                del self.log_queues[server_id]
            return False

        return True

    def get_process_info(self, server_id: UUID) -> Optional[ProcessInfo]:
        """Get process information for a server"""
        return self.running_processes.get(server_id)

    def get_server_ports(self, server_id: UUID) -> List[int]:
        """Get the allocated ports for a server (legacy method for backward compatibility)"""
        port_info = self.get_server_port_info(server_id)
        return [port["port"] for port in port_info]

    def get_server_port_info(self, server_id: UUID) -> List[Dict[str, any]]:
        """Get detailed port information including protocols for a server"""
        if server_id not in self.running_processes:
            return []

        process_info = self.running_processes[server_id]
        config = process_info.config
        port_info = []

        if config and "inbounds" in config:
            for inbound in config["inbounds"]:
                if "port" in inbound:
                    tag = inbound.get("tag", "")
                    protocol = self._extract_protocol_from_tag(tag, inbound)

                    port_info.append(
                        {
                            "port": inbound["port"],
                            "protocol": protocol,
                            "tag": tag if tag else None,
                        }
                    )

        return port_info

    def _extract_protocol_from_tag(self, tag: str, inbound: Dict) -> str:
        """Extract protocol type from inbound tag or configuration"""
        tag_lower = tag.lower() if tag else ""

        # Check tag for common protocol indicators
        if "socks" in tag_lower:
            return "socks"
        elif "http" in tag_lower:
            return "http"
        elif "trojan" in tag_lower:
            return "trojan"
        elif "vless" in tag_lower:
            return "vless"
        elif "vmess" in tag_lower:
            return "vmess"
        elif "shadowsocks" in tag_lower or "ss" in tag_lower:
            return "shadowsocks"

        # Check inbound protocol field if available
        if "protocol" in inbound:
            return inbound["protocol"]

        # Default fallback
        return "unknown"

    # Single server convenience methods
    def get_current_server_id(self) -> Optional[UUID]:
        """Get the currently running server ID"""
        return self.current_server_id

    def is_any_server_running(self) -> bool:
        """Check if any server is currently running"""
        return self.current_server_id is not None and self.is_server_running(
            self.current_server_id
        )

    def get_current_server_info(self) -> Optional[ProcessInfo]:
        """Get process information for the currently running server"""
        if self.current_server_id:
            return self.get_process_info(self.current_server_id)
        return None

    def get_current_server_ports(self) -> List[int]:
        """Get ports for the currently running server"""
        if self.current_server_id:
            return self.get_server_ports(self.current_server_id)
        return []

    def get_current_server_port_info(self) -> List[Dict[str, any]]:
        """Get detailed port information for the currently running server"""
        if self.current_server_id:
            return self.get_server_port_info(self.current_server_id)
        return []

    async def stop_current_server(self) -> bool:
        """Stop the currently running server"""
        if self.current_server_id:
            return await self.stop_server(self.current_server_id)
        return True  # No server running, consider it success

    async def restart_current_server(
        self,
        subscription_id: UUID,
        config: Dict,
        socks_port: Optional[int] = None,
        http_port: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Restart the currently running server with new config and port overrides

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        if self.current_server_id:
            return await self.restart_server(
                self.current_server_id, subscription_id, config, socks_port, http_port
            )
        return False, "No server is currently running"

    async def _read_process_logs(
        self, server_id: UUID, process: asyncio.subprocess.Process
    ):
        """Read logs from a process and queue them"""
        try:
            while True:
                # Use async readline to avoid blocking
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Queue the log line
                if server_id in self.log_queues:
                    try:
                        await self.log_queues[server_id].put(
                            {
                                "timestamp": datetime.now(),
                                "server_id": server_id,
                                "message": line,
                            }
                        )
                    except asyncio.QueueFull:
                        # Queue is full, skip this log entry
                        pass
                    except Exception:
                        # Queue might be closed or other error
                        break

        except Exception as e:
            logger.error(f"Error reading logs for server {server_id}: {e}")
        finally:
            logger.debug(f"Log reading task for server {server_id} ended")

    async def get_server_logs(self, server_id: UUID) -> AsyncGenerator[Dict, None]:
        """Get real-time logs for a specific server"""
        if server_id not in self.log_queues:
            return

        queue = self.log_queues[server_id]

        try:
            while True:
                # Wait for log message with timeout
                try:
                    log_entry = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield log_entry
                except asyncio.TimeoutError:
                    # Check if server is still running
                    if not self.is_server_running(server_id):
                        break
                    continue
        except Exception as e:
            logger.error(f"Error streaming logs for server {server_id}: {e}")

    async def get_current_server_logs(self) -> AsyncGenerator[Dict, None]:
        """Get real-time logs from the currently running server"""
        if self.current_server_id:
            async for log_entry in self.get_server_logs(self.current_server_id):
                yield log_entry
        else:
            # No server running, just wait and check periodically
            while True:
                await asyncio.sleep(1)
                if self.current_server_id:
                    async for log_entry in self.get_server_logs(self.current_server_id):
                        yield log_entry
                    break

    async def shutdown_all(self):
        """Shutdown all running servers"""
        server_ids = list(self.running_processes.keys())
        for server_id in server_ids:
            await self.stop_server(server_id)

        logger.info("All servers stopped")

    def _find_available_port(self, start_port: int = 10800) -> int:
        """Find an available port starting from start_port"""
        port = start_port
        while port < 65535:
            if self._is_port_available(port):
                return port
            port += 1
        raise RuntimeError("No available ports found")

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available for binding"""
        try:
            with socket(AF_INET, SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def _allocate_random_ports(self) -> Tuple[int, int]:
        """Allocate random available ports for SOCKS and HTTP"""
        # Find random starting points to avoid conflicts
        socks_start = randint(10800, 20000)
        http_start = randint(20001, 30000)

        socks_port = self._find_available_port(socks_start)
        http_port = self._find_available_port(http_start)

        # Ensure ports are different
        while http_port == socks_port:
            http_port = self._find_available_port(http_port + 1)

        return socks_port, http_port

    async def test_server_connectivity(
        self,
        server_id: UUID,
        subscription_id: UUID,
        config: Dict,
        test_timeout: int = 6,
    ) -> Tuple[bool, Optional[int], Optional[str], int, int]:
        """
        Test server connectivity by starting it on random ports and making HTTP request
        Returns: (success, ping_ms, error_message, socks_port, http_port)
        """
        socks_port, http_port = self._allocate_random_ports()

        try:
            # Apply random port overrides to config
            runtime_config = self._apply_port_overrides(config, socks_port, http_port)

            # Apply log level override to config
            runtime_config = self._apply_log_level_override(runtime_config)

            # Start server with random ports
            success, error_msg = await self.start_server(
                server_id, subscription_id, runtime_config
            )
            if not success:
                error_detail = error_msg or "Failed to start server"
                return False, None, error_detail, socks_port, http_port

            # Wait a moment for server to fully start
            await asyncio.sleep(2)

            # Test HTTP connectivity through the proxy
            start_time = time()
            try:
                # Use the HTTP proxy for testing
                proxy_url = f"http://127.0.0.1:{http_port}"

                async with AsyncClient(
                    proxy=proxy_url,
                    timeout=test_timeout,
                ) as client:
                    response = await client.get("http://gstatic.com/generate_204")

                    if response.status_code == 204:
                        ping_ms = int((time() - start_time) * 1000)
                        return True, ping_ms, None, socks_port, http_port
                    else:
                        return (
                            False,
                            None,
                            f"HTTP {response.status_code}",
                            socks_port,
                            http_port,
                        )

            except TimeoutException:
                return False, None, "Connection timeout", socks_port, http_port
            except Exception as e:
                return False, None, f"Connection error: {str(e)}", socks_port, http_port

        except Exception as e:
            return False, None, f"Test error: {str(e)}", socks_port, http_port
        finally:
            # Always stop the test server
            try:
                if server_id in self.running_processes:
                    await self.stop_server(server_id)
            except Exception:
                pass

    async def test_subscription_servers(
        self, subscription_servers: List, subscription_id: UUID, test_timeout: int = 6
    ) -> List[Dict]:
        """
        Test all servers in a subscription concurrently
        Returns list of test results
        """
        results = []

        # Create tasks for concurrent testing
        tasks = []
        for server in subscription_servers:
            task = asyncio.create_task(
                self.test_server_connectivity(
                    server.id, subscription_id, server.raw, test_timeout
                )
            )
            tasks.append((server, task))

        # Wait for all tests to complete
        for server, task in tasks:
            try:
                success, ping_ms, error, socks_port, http_port = await task

                results.append(
                    {
                        "server_id": server.id,
                        "remarks": server.remarks,
                        "success": success,
                        "ping_ms": ping_ms,
                        "error": error,
                        "socks_port": socks_port,
                        "http_port": http_port,
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "server_id": server.id,
                        "remarks": server.remarks,
                        "success": False,
                        "ping_ms": None,
                        "error": f"Test failed: {str(e)}",
                        "socks_port": 0,
                        "http_port": 0,
                    }
                )

        return results


# Global process manager instance
process_manager = ProcessManager()
