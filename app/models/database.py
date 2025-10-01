"""Database models for TinyDB storage."""

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


class ServerModel(BaseModel):
    """Server model for database storage."""

    id: UUID = Field(default_factory=uuid4)
    remarks: str = Field(..., description="Server remarks from subscription")
    raw: dict[str, Any] = Field(..., description="Full JSON config")
    status: str = Field(default="stopped", description="Server status")

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)


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
