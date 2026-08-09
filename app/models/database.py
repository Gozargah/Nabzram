"""Database models for TinyDB storage."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer


class XrayLogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    NONE = "none"


class RoutingAction(str, Enum):
    BYPASS = "bypass"
    PROXY = "proxy"
    BLOCK = "block"


class RoutingRuleModel(BaseModel):
    """Custom routing rule applied at runtime."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Stable rule id")
    name: str | None = Field(None, description="Optional display name for the rule")
    action: RoutingAction = Field(..., description="bypass, proxy, or block")
    domain: list[str] = Field(default_factory=list, description="Domain matchers (e.g. geosite:cn)")
    ip: list[str] = Field(default_factory=list, description="IP matchers (e.g. geoip:cn, CIDR, IP)")
    port: str | None = Field(None, description="Port matcher (e.g. 53,443,1000-2000)")
    protocol: list[str] = Field(default_factory=list, description="Protocol matchers (http, tls, quic, bittorrent)")
    process: list[str] = Field(default_factory=list, description="Process name matchers")
    enabled: bool = Field(True, description="Whether this rule is active")


class ServerModel(BaseModel):
    """Server model for database storage."""

    id: UUID = Field(default_factory=uuid4)
    remarks: str = Field(..., description="Server remarks from subscription")
    raw: dict[str, Any] = Field(..., description="Full JSON config")

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @property
    def json_config(self) -> str:
        """Get the server configuration as formatted JSON string."""

        def serialize_uuids(obj):
            if isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: serialize_uuids(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_uuids(item) for item in obj]
            return obj

        return json.dumps(serialize_uuids(self.raw), indent=2)


class SubscriptionModel(BaseModel):
    """Subscription model for database storage."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Subscription name")
    url: str = Field(..., description="Subscription URL (normalized)")
    servers: list[ServerModel] = Field(
        default_factory=list,
        description="List of servers",
    )
    last_updated: datetime | None = Field(None, description="Last update timestamp")
    user_info: Optional["SubscriptionUserInfo"] = Field(
        None,
        description="User traffic and expiry info",
    )

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer("last_updated")
    def serialize_last_updated(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None


class SubscriptionUserInfo(BaseModel):
    """Subscription user info model for traffic and expiry data."""

    used_traffic: int = Field(..., description="Total used traffic in bytes")
    total: int | None = Field(
        None,
        description="Total data limit in bytes (None if unlimited)",
    )
    expire: datetime | None = Field(
        None,
        description="Expiry date (None if no expiry)",
    )

    @field_serializer("expire")
    def serialize_expire(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None


class SettingsModel(BaseModel):
    """Settings model for database storage."""

    socks_port: int | None = Field(None, description="Global SOCKS port override")
    http_port: int | None = Field(None, description="Global HTTP port override")
    xray_binary: str | None = Field(None, description="Path to xray binary")
    xray_assets_folder: str | None = Field(
        None,
        description="Path to xray assets folder",
    )

    xray_log_level: Optional[XrayLogLevel] = Field(
        XrayLogLevel.WARNING,
        description="Xray log level override (debug, info, warning, error, none)",
    )

    system_proxy: Optional[bool] = Field(True, description="Enable OS-level system proxy management")
    tun_mode: Optional[bool] = Field(
        False,
        description="Enable TUN mode to route all traffic through a TUN interface",
    )
    routing_rules: list[RoutingRuleModel] = Field(
        default_factory=list,
        description="Custom routing rules for bypass, proxy, or block",
    )


class ProcessInfo(BaseModel):
    """Process information for running servers (not stored in database)."""

    server_id: UUID
    subscription_id: UUID
    process_id: int
    start_time: datetime
    config: dict[str, Any]

    @field_serializer("server_id", "subscription_id")
    def serialize_uuids(self, value: UUID) -> str:
        return str(value)

    @field_serializer("start_time")
    def serialize_start_time(self, value: datetime) -> str:
        return value.isoformat()


class AppearanceModel(BaseModel):
    """Settings model for database storage."""

    theme: str | None = Field(None, description="Theme")
    font: str | None = Field(None, description="Font")
