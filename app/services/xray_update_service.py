"""
Xray binary update service
"""

import logging
import os
import platform
from hashlib import sha256
from pathlib import Path
from shutil import move
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Dict, List
from zipfile import ZipFile

from httpx import AsyncClient

logger = logging.getLogger(__name__)


class XrayUpdateService:
    """Service for updating Xray binary"""

    def __init__(self):
        self.github_api_base = "https://api.github.com/repos/XTLS/Xray-core"
        self.github_releases_base = (
            "https://github.com/XTLS/Xray-core/releases/download"
        )
        self.timeout = 30.0

    def _get_system_architecture(self) -> str:
        """Map platform.machine to Xray release arch suffix."""
        machine = platform.machine().lower()

        # Normalize common variants
        if machine in {"x86_64", "amd64"}:
            return "64"
        if machine in {"i386", "i686"}:
            return "32"
        if machine in {"armv5", "armv5tel"}:
            return "arm32-v5"
        if machine in {"armv6", "armv6l"}:
            return "arm32-v6"
        if machine in {"armv7", "armv7l"}:
            return "arm32-v7a"
        if machine in {"armv8", "aarch64", "arm64"}:
            return "arm64-v8a"
        if machine in {"mips"}:
            return "mips32"
        if machine in {"mipsle"}:
            return "mips32le"
        if machine in {"mips64"}:
            return "mips64"
        if machine in {"mips64le"}:
            return "mips64le"
        if machine in {"ppc64"}:
            return "ppc64"
        if machine in {"ppc64le"}:
            return "ppc64le"
        if machine in {"riscv64"}:
            return "riscv64"
        if machine in {"s390x"}:
            return "s390x"
        # Default to 64-bit
        return "64"

    def _get_os_suffix(self) -> str:
        """Map platform.system to Xray release OS suffix."""
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        if system == "windows":
            return "windows"
        if system == "linux":
            return "linux"
        if system == "freebsd":
            return "freebsd"
        if system == "openbsd":
            return "openbsd"
        # Fallback to linux naming
        return "linux"

    def _build_asset_filename(self) -> str:
        """Build the exact asset filename for current OS/arch."""
        os_suffix = self._get_os_suffix()
        arch_suffix = self._get_system_architecture()

        # Special cases for macOS Intel vs Apple Silicon are covered by arch mapping
        # Result examples:
        # - Xray-linux-64.zip
        # - Xray-windows-64.zip
        # - Xray-macos-arm64-v8a.zip
        return f"Xray-{os_suffix}-{arch_suffix}.zip"

    def _get_http_client(self) -> AsyncClient:
        """Create an AsyncClient with default timeout."""
        return AsyncClient(timeout=self.timeout)

    async def get_latest_version(self) -> str:
        """Get the latest Xray release version"""
        try:
            async with self._get_http_client() as client:
                response = await client.get(
                    f"{self.github_api_base}/releases/latest",
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                response.raise_for_status()

                data = response.json()
                version = data.get("tag_name", "")

                # Normalize version (ensure it starts with 'v')
                if version and not version.startswith("v"):
                    version = f"v{version}"

                return version

        except Exception as e:
            logger.error(f"Failed to get latest Xray version: {e}")
            raise RuntimeError(f"Failed to fetch latest version: {str(e)}")

    async def get_available_versions(self, limit: int = 10) -> List[str]:
        """Get list of available Xray versions"""
        try:
            async with self._get_http_client() as client:
                response = await client.get(
                    f"{self.github_api_base}/releases",
                    headers={"Accept": "application/vnd.github.v3+json"},
                    params={"per_page": limit},
                )
                response.raise_for_status()

                data = response.json()
                versions = []

                for release in data:
                    version = release.get("tag_name", "")
                    if version:
                        # Normalize version
                        if not version.startswith("v"):
                            version = f"v{version}"
                        versions.append(version)

                return versions

        except Exception as e:
            logger.error(f"Failed to get Xray versions: {e}")
            raise RuntimeError(f"Failed to fetch versions: {str(e)}")

    async def get_available_versions_with_sizes(
        self, limit: int = 10
    ) -> Dict[str, int]:
        """Get available Xray versions with their download sizes"""
        try:
            async with self._get_http_client() as client:
                response = await client.get(
                    f"{self.github_api_base}/releases",
                    headers={"Accept": "application/vnd.github.v3+json"},
                    params={"per_page": limit},
                )
                response.raise_for_status()

                data = response.json()
                filename = self._build_asset_filename()
                version_sizes = {}

                for release in data:
                    version = release.get("tag_name", "")
                    if version:
                        # Normalize version
                        if not version.startswith("v"):
                            version = f"v{version}"

                        # Look for the matching asset in this release
                        assets = release.get("assets", [])
                        for asset in assets:
                            if asset.get("name") == filename:
                                size = asset.get("size")
                                if isinstance(size, int):
                                    version_sizes[version] = size
                                break

                return version_sizes

        except Exception as e:
            logger.error(f"Failed to get Xray versions with sizes: {e}")
            raise RuntimeError(f"Failed to fetch versions with sizes: {str(e)}")

    async def download_xray(self, version: str, target_path: str) -> bool:
        """Download and install Xray binary"""
        try:
            # Normalize version
            if not version.startswith("v"):
                version = f"v{version}"

            filename = self._build_asset_filename()
            download_url = f"{self.github_releases_base}/{version}/{filename}"
            checksum_url = f"{download_url}.dgst"

            logger.info(f"Downloading Xray {version} asset {filename}")

            # Create temporary directory
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_file = temp_path / filename
                checksum_file = temp_path / f"{filename}.dgst"

                # Download files
                async with self._get_http_client() as client:
                    # Download zip file
                    logger.info(f"Downloading from: {download_url}")
                    response = await client.get(download_url, follow_redirects=True)
                    response.raise_for_status()

                    with open(zip_file, "wb") as f:
                        f.write(response.content)

                    # Download checksum file
                    logger.info(f"Downloading checksum from: {checksum_url}")
                    response = await client.get(checksum_url, follow_redirects=True)
                    response.raise_for_status()

                    checksum_content = response.text
                    if "Not Found" in checksum_content:
                        logger.warning(
                            "Checksum verification not available for this version"
                        )
                    else:
                        with open(checksum_file, "w") as f:
                            f.write(checksum_content)

                        # Verify checksum
                        await self._verify_checksum(zip_file, checksum_file)

                # Extract and install
                await self._extract_and_install(zip_file, target_path)

            logger.info(f"Successfully updated Xray to version {version}")
            return True

        except Exception as e:
            logger.error(f"Failed to download Xray {version}: {e}")
            raise RuntimeError(f"Download failed: {str(e)}")

    async def _verify_checksum(self, zip_file: Path, checksum_file: Path) -> None:
        """Verify the downloaded file checksum"""
        try:
            # Read expected checksum
            checksum_content = checksum_file.read_text()

            # Extract SHA256 checksum (format: "SHA256= <hash>")
            import re

            match = re.search(r"256=\s*([a-fA-F0-9]+)", checksum_content)
            if not match:
                logger.warning("Could not parse checksum file")
                return

            expected_checksum = match.group(1).lower()

            # Calculate actual checksum
            sha256_hash = sha256()
            with open(zip_file, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)

            actual_checksum = sha256_hash.hexdigest()

            if expected_checksum != actual_checksum:
                raise RuntimeError("SHA256 checksum verification failed")

            logger.info("Checksum verification passed")

        except Exception as e:
            logger.error(f"Checksum verification failed: {e}")
            raise

    async def _extract_and_install(self, zip_file: Path, target_path: str) -> None:
        """Extract zip file and install xray binary"""
        try:
            # Create target directory if it doesn't exist
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)

            # Extract zip file
            with ZipFile(zip_file, "r") as zip_ref:
                # Look for xray binary in the zip
                xray_found = False
                # Find binary inside the archive (Windows uses xray.exe)
                binary_candidates = {"xray", "xray.exe"}
                for file_info in zip_ref.filelist:
                    basename = os.path.basename(file_info.filename)
                    if basename in binary_candidates:
                        # Extract xray binary to temporary location
                        with NamedTemporaryFile(delete=False) as temp_binary:
                            temp_binary.write(zip_ref.read(file_info.filename))
                            temp_binary_path = temp_binary.name
                        # Make it executable and move to target location
                        os.chmod(temp_binary_path, 0o755)
                        move(temp_binary_path, target_path)
                        xray_found = True
                        break

                if not xray_found:
                    raise RuntimeError("xray binary not found in downloaded archive")
            logger.info(f"Xray binary installed to: {target_path}")

        except Exception as e:
            logger.error(f"Failed to extract and install: {e}")
            raise


class GeodataUpdateService:
    """Service for updating Xray geodata files (geoip.dat, geosite.dat)"""

    def __init__(self):
        self.geodata_base_url = (
            "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download"
        )
        self.timeout = 30.0

    async def update_geodata(self, assets_folder: str) -> Dict[str, bool]:
        """Download and update geoip.dat and geosite.dat files"""
        try:
            if not assets_folder:
                raise RuntimeError("Assets folder path is required")

            # Create assets directory if it doesn't exist
            os.makedirs(assets_folder, exist_ok=True)

            results = {}
            files_to_download = [
                ("geoip.dat", f"{self.geodata_base_url}/geoip.dat"),
                ("geosite.dat", f"{self.geodata_base_url}/geosite.dat"),
            ]

            logger.info(f"Updating geodata in: {assets_folder}")

            # Create temporary directory
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                async with AsyncClient(timeout=60.0) as client:
                    for filename, url in files_to_download:
                        try:
                            logger.info(f"Downloading {filename}")

                            # Download file
                            response = await client.get(url, follow_redirects=True)
                            response.raise_for_status()

                            temp_file = temp_path / filename
                            with open(temp_file, "wb") as f:
                                f.write(response.content)

                            # Download checksum if available
                            checksum_url = f"{url}.sha256sum"
                            try:
                                checksum_response = await client.get(
                                    checksum_url, follow_redirects=True
                                )
                                checksum_response.raise_for_status()

                                checksum_file = temp_path / f"{filename}.sha256sum"
                                with open(checksum_file, "w") as f:
                                    f.write(checksum_response.text)

                                # Verify checksum
                                await self._verify_geodata_checksum(
                                    temp_file, checksum_file
                                )

                            except Exception as e:
                                logger.warning(
                                    f"Checksum verification not available for {filename}: {e}"
                                )

                            # Move to target location
                            target_file = os.join(assets_folder, filename)
                            move(str(temp_file), target_file)
                            os.chmod(target_file, 0o644)

                            results[filename] = True
                            logger.info(f"Successfully updated {filename}")

                        except Exception as e:
                            logger.error(f"Failed to update {filename}: {e}")
                            results[filename] = False

            return results

        except Exception as e:
            logger.error(f"Failed to update geodata: {e}")
            raise RuntimeError(f"Geodata update failed: {str(e)}")

    async def _verify_geodata_checksum(
        self, file_path: Path, checksum_file: Path
    ) -> None:
        """Verify geodata file checksum"""
        try:
            checksum_content = checksum_file.read_text().strip()

            # Parse checksum (format: "<hash>  <filename>")
            expected_checksum = checksum_content.split()[0].lower()

            # Calculate actual checksum
            sha256_hash = sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)

            actual_checksum = sha256_hash.hexdigest()

            if expected_checksum != actual_checksum:
                raise RuntimeError(
                    f"SHA256 checksum verification failed for {file_path.name}"
                )

            logger.info(f"Checksum verification passed for {file_path.name}")

        except Exception as e:
            logger.error(f"Checksum verification failed for {file_path.name}: {e}")
            raise
