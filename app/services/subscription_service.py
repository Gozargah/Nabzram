"""Subscription management service."""

import logging
from copy import deepcopy
from datetime import UTC, datetime
from json import JSONDecodeError
from typing import Any
from urllib.parse import urljoin
from uuid import uuid4

from requests import Session
from requests.exceptions import HTTPError, RequestException

from app.models.database import ServerModel, SubscriptionModel, SubscriptionUserInfo
from app.models.schemas import SubscriptionCreate

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing proxy subscriptions."""

    def __init__(self) -> None:
        self.session = Session()
        self.session.timeout = 30.0

    def close(self) -> None:
        """Close HTTP session."""
        self.session.close()

    def _normalize_url(self, url: str) -> str:
        """Normalize subscription URL by appending /v2ray-json if missing."""
        url = str(url).rstrip("/")

        # Check if URL already ends with v2ray-json or similar
        if not any(endpoint in url.lower() for endpoint in ["/v2ray-json", "/v2ray", "/json"]):
            url = urljoin(url + "/", "v2ray-json")

        return url

    def _parse_subscription_userinfo(
        self,
        userinfo_header: str,
    ) -> SubscriptionUserInfo | None:
        """Parse subscription-userinfo header.

        Format: upload=0; download=862108477783; total=0; expire=0
        - upload + download = used traffic in bytes
        - total = data limit (0 means unlimited, should be None)
        - expire = UTC timestamp (0 means no expiry, should be None)
        """
        try:
            # Parse key-value pairs separated by semicolons
            pairs = {}
            for part in userinfo_header.split(";"):
                part = part.strip()
                if "=" in part:
                    key, value = part.split("=", 1)
                    pairs[key.strip()] = value.strip()

            # Extract values
            upload = int(pairs.get("upload", 0))
            download = int(pairs.get("download", 0))
            total_raw = int(pairs.get("total", 0))
            expire_raw = int(pairs.get("expire", 0))

            # Calculate used traffic (upload + download)
            used_traffic = upload + download

            # Convert total: 0 means unlimited (None)
            total = total_raw if total_raw > 0 else None

            # Convert expire: 0 means no expiry (None)
            expire = None
            if expire_raw > 0:
                expire = datetime.fromtimestamp(expire_raw, tz=UTC)

            return SubscriptionUserInfo(
                used_traffic=used_traffic,
                total=total,
                expire=expire,
            )

        except (ValueError, KeyError) as e:
            # Log the error but don't fail the entire subscription fetch
            logger.warning(f"Failed to parse subscription-userinfo header '{userinfo_header}': {e}")
            return None

    def fetch_subscription_config(
        self,
        url: str,
    ) -> tuple[list[dict[str, Any]], SubscriptionUserInfo | None]:
        """Fetch and parse subscription configuration and user info."""
        try:
            response = self.session.get(url)
            response.raise_for_status()

            # Parse subscription-userinfo header if present
            user_info = None
            userinfo_header = response.headers.get("subscription-userinfo")
            if userinfo_header:
                user_info = self._parse_subscription_userinfo(userinfo_header)

            # Try to parse as JSON
            try:
                config_data = response.json()
            except JSONDecodeError:
                # If not JSON, might be base64 encoded or other format
                msg = "Invalid subscription format: not valid JSON"
                raise ValueError(msg)

            # Handle different response formats
            configs = None
            if isinstance(config_data, list):
                configs = config_data
            elif isinstance(config_data, dict):
                # Some subscriptions wrap configs in an object
                if "configs" in config_data:
                    configs = config_data["configs"]
                elif "servers" in config_data:
                    configs = config_data["servers"]
                else:
                    configs = [config_data]
            else:
                msg = "Invalid subscription format: unexpected data structure"
                raise ValueError(msg)

            return configs, user_info

        except HTTPError:
            msg = f"HTTP error {response.status_code}: {response.text}"
            raise ValueError(msg)
        except RequestException as e:
            msg = f"Failed to fetch subscription: {e!s}"
            raise ValueError(msg)

    def _extract_server_info(
        self,
        config: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """Extract server remarks and clean config."""
        # Try to find remarks in various possible locations
        remarks = "Unknown Server"

        # Common locations for server names/remarks
        if "remarks" in config:
            remarks = config["remarks"]
        elif "ps" in config:  # V2Ray format
            remarks = config["ps"]
        elif "name" in config:
            remarks = config["name"]
        elif "tag" in config:
            remarks = config["tag"]
        elif isinstance(config.get("outbounds"), list) and len(config["outbounds"]) > 0:
            outbound = config["outbounds"][0]
            if "tag" in outbound:
                remarks = outbound["tag"]

        return remarks, config

    def _apply_port_overrides(
        self,
        config: dict[str, Any],
        socks_port: int | None,
        http_port: int | None,
    ) -> dict[str, Any]:
        """Apply global port overrides to inbound configurations."""
        if not config.get("inbounds"):
            return config

        modified_config = deepcopy(config)

        for inbound in modified_config.get("inbounds", []):
            tag = inbound.get("tag", "").lower()

            if socks_port and "socks" in tag:
                inbound["port"] = socks_port
            elif http_port and "http" in tag:
                inbound["port"] = http_port

        return modified_config

    def create_subscription(
        self,
        subscription_data: SubscriptionCreate,
        socks_port: int | None = None,
        http_port: int | None = None,
    ) -> SubscriptionModel:
        """Create a new subscription and fetch its servers."""
        # Normalize URL
        normalized_url = self._normalize_url(str(subscription_data.url))

        # Fetch subscription configuration and user info
        configs, user_info = self.fetch_subscription_config(normalized_url)

        # Create server models from configs
        servers = []
        for config in configs:
            remarks, clean_config = self._extract_server_info(config)

            # Apply port overrides if specified
            if socks_port or http_port:
                clean_config = self._apply_port_overrides(
                    clean_config,
                    socks_port,
                    http_port,
                )

            server = ServerModel(
                id=uuid4(),
                remarks=remarks,
                raw=clean_config,
                status="stopped",
            )
            servers.append(server)

        # Create subscription model
        return SubscriptionModel(
            id=uuid4(),
            name=subscription_data.name,
            url=normalized_url,
            servers=servers,
            last_updated=datetime.now(),
            user_info=user_info,
        )

    def update_subscription_servers(
        self,
        subscription: SubscriptionModel,
        socks_port: int | None = None,
        http_port: int | None = None,
    ) -> SubscriptionModel:
        """Update servers for an existing subscription."""
        # Fetch fresh configuration and user info
        configs, user_info = self.fetch_subscription_config(subscription.url)

        # Create new server models
        new_servers = []
        existing_servers_by_remarks = {server.remarks: server for server in subscription.servers}

        for config in configs:
            remarks, clean_config = self._extract_server_info(config)

            # Apply port overrides if specified
            if socks_port or http_port:
                clean_config = self._apply_port_overrides(
                    clean_config,
                    socks_port,
                    http_port,
                )

            # Try to preserve existing server ID and status if server exists
            existing_server = existing_servers_by_remarks.get(remarks)
            if existing_server:
                server = ServerModel(
                    id=existing_server.id,
                    remarks=remarks,
                    raw=clean_config,
                    status=existing_server.status,  # Preserve status
                )
            else:
                server = ServerModel(
                    id=uuid4(),
                    remarks=remarks,
                    raw=clean_config,
                    status="stopped",
                )

            new_servers.append(server)

        # Update subscription
        subscription.servers = new_servers
        subscription.last_updated = datetime.now()
        subscription.user_info = user_info

        return subscription
