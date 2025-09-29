"""
Pydantic models for API request/response schemas
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class ServerStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


class SubscriptionCreate(BaseModel):
    name: str = Field(..., description="Name for the subscription")
    url: HttpUrl = Field(..., description="Subscription URL")


class SubscriptionUpdate(BaseModel):
    name: Optional[str] = Field(None, description="New name for the subscription")
    url: Optional[HttpUrl] = Field(None, description="Subscription URL")


class SubscriptionUserInfoResponse(BaseModel):
    """Response model for subscription user info (traffic and expiry data)"""

    used_traffic: int = Field(
        ..., description="Total used traffic (upload + download) in bytes"
    )
    total: Optional[int] = Field(
        None, description="Total data limit in bytes (None if unlimited)"
    )
    expire: Optional[datetime] = Field(
        None, description="Expiry date (None if no expiry)"
    )


class ServerResponse(BaseModel):
    id: UUID = Field(..., description="Server ID")
    remarks: str = Field(..., description="Server remarks/name")
    status: ServerStatus = Field(..., description="Server status")


class ServerDetailResponse(ServerResponse):
    raw: Dict[str, Any] = Field(..., description="Full server configuration")


class SubscriptionResponse(BaseModel):
    id: UUID = Field(..., description="Subscription ID")
    name: str = Field(..., description="Subscription name")
    url: str = Field(..., description="Subscription URL")
    last_updated: Optional[datetime] = Field(None, description="Last update time")
    server_count: int = Field(..., description="Number of servers in subscription")
    user_info: Optional[SubscriptionUserInfoResponse] = Field(
        None, description="User traffic and expiry info"
    )


class SubscriptionDetailResponse(SubscriptionResponse):
    servers: List[ServerResponse] = Field(
        default_factory=list, description="List of servers"
    )


class SettingsResponse(BaseModel):
    socks_port: Optional[int] = Field(None, description="Global SOCKS port override")
    http_port: Optional[int] = Field(None, description="Global HTTP port override")
    xray_binary: Optional[str] = Field(None, description="Path to xray binary")
    xray_assets_folder: Optional[str] = Field(
        None, description="Path to xray assets folder"
    )

    class XrayLogLevel(str, Enum):
        DEBUG = "debug"
        INFO = "info"
        WARNING = "warning"
        ERROR = "error"
        NONE = "none"

    xray_log_level: Optional[XrayLogLevel] = Field(
        XrayLogLevel.WARNING,
        description="Xray log level override (debug, info, warning, error, none)",
    )


class SettingsUpdate(BaseModel):
    socks_port: Optional[int] = Field(None, description="Global SOCKS port override")
    http_port: Optional[int] = Field(None, description="Global HTTP port override")
    xray_binary: Optional[str] = Field(None, description="Path to xray binary")
    xray_assets_folder: Optional[str] = Field(
        None, description="Path to xray assets folder"
    )
    xray_log_level: Optional[SettingsResponse.XrayLogLevel] = Field(
        None, description="Xray log level override (debug, info, warning, error, none)"
    )

    @field_validator("socks_port")
    @classmethod
    def validate_socks_port(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if not (1 <= v <= 65535):
            raise ValueError("SOCKS port must be between 1 and 65535")
        return v

    @field_validator("http_port")
    @classmethod
    def validate_http_port(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if not (1 <= v <= 65535):
            raise ValueError("HTTP port must be between 1 and 65535")
        return v

    @model_validator(mode="after")
    def validate_port_conflict(self):
        if (
            self.socks_port is not None
            and self.http_port is not None
            and self.socks_port == self.http_port
        ):
            raise ValueError("SOCKS and HTTP ports cannot be the same")
        return self


class SystemInfo(BaseModel):
    available: bool = Field(..., description="Whether xray-core is available")
    version: Optional[str] = Field(None, description="Xray-core version")
    commit: Optional[str] = Field(None, description="Git commit hash")
    go_version: Optional[str] = Field(None, description="Go version used to build")
    arch: Optional[str] = Field(None, description="Architecture")


class AllocatedPort(BaseModel):
    port: int = Field(..., description="Port number")
    protocol: str = Field(..., description="Protocol type (e.g., socks, http, etc.)")
    tag: Optional[str] = Field(None, description="Inbound tag from configuration")


class LogMessage(BaseModel):
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    server_id: Optional[UUID] = Field(
        None, description="Server ID that generated the log"
    )


class APIResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Any] = Field(None, description="Response data")


class ErrorResponse(BaseModel):
    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


# Server-specific response models
class ServerStartResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    server_id: UUID = Field(..., description="Server ID that was started")
    status: ServerStatus = Field(..., description="Current server status")
    remarks: str = Field(..., description="Server remarks/name")


class ServerStopResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    server_id: Optional[UUID] = Field(None, description="Server ID that was stopped")
    status: ServerStatus = Field(..., description="Current server status")


class ServerStatusResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    server_id: Optional[UUID] = Field(None, description="Server ID")
    status: ServerStatus = Field(..., description="Current server status")
    remarks: Optional[str] = Field(None, description="Server remarks/name")
    process_id: Optional[int] = Field(None, description="Process ID if running")
    start_time: Optional[str] = Field(None, description="Start time if running")
    allocated_ports: Optional[List[AllocatedPort]] = Field(
        None, description="Allocated ports with protocol information if running"
    )


# Subscription-specific response models
class SubscriptionCreateResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    id: UUID = Field(..., description="Created subscription ID")
    name: str = Field(..., description="Subscription name")
    server_count: int = Field(..., description="Number of servers fetched")


class SubscriptionUpdateResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    id: UUID = Field(..., description="Updated subscription ID")
    name: str = Field(..., description="Updated subscription name")


class SubscriptionDeleteResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    id: UUID = Field(..., description="Deleted subscription ID")
    name: str = Field(..., description="Deleted subscription name")


class SubscriptionServersUpdateResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    id: UUID = Field(..., description="Updated subscription ID")
    server_count: int = Field(..., description="Number of servers after update")
    last_updated: str = Field(..., description="Last update timestamp")


# Settings-specific response models
class SettingsUpdateResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    socks_port: Optional[int] = Field(None, description="Updated SOCKS port")
    http_port: Optional[int] = Field(None, description="Updated HTTP port")
    xray_binary: Optional[str] = Field(None, description="Updated xray binary path")
    xray_assets_folder: Optional[str] = Field(
        None, description="Updated xray assets folder path"
    )
    xray_log_level: Optional[SettingsResponse.XrayLogLevel] = Field(
        None, description="Updated xray log level"
    )


# URL Test response models
class ServerTestResult(BaseModel):
    server_id: UUID = Field(..., description="Server ID")
    remarks: str = Field(..., description="Server remarks/name")
    success: bool = Field(..., description="Whether the test was successful")
    ping_ms: Optional[int] = Field(None, description="Ping time in milliseconds")
    error: Optional[str] = Field(None, description="Error message if test failed")
    socks_port: int = Field(..., description="Allocated SOCKS port")
    http_port: int = Field(..., description="Allocated HTTP port")


class SubscriptionUrlTestResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    subscription_id: UUID = Field(..., description="Subscription ID")
    subscription_name: str = Field(..., description="Subscription name")
    total_servers: int = Field(..., description="Total number of servers tested")
    successful_tests: int = Field(..., description="Number of successful tests")
    failed_tests: int = Field(..., description="Number of failed tests")
    results: List[ServerTestResult] = Field(
        ..., description="Individual server test results"
    )


# Xray update schemas
class XrayAssetInfo(BaseModel):
    version: str = Field(..., description="Version tag (e.g., v1.8.10)")
    size_bytes: Optional[int] = Field(
        None, description="Asset size in bytes for current OS/arch"
    )


class XrayVersionInfo(BaseModel):
    current_version: Optional[str] = Field(
        None, description="Currently installed Xray version"
    )
    latest_version: str = Field(..., description="Latest available Xray version")
    available_versions: List[XrayAssetInfo] = Field(
        ..., description="List of available versions with asset sizes"
    )


class XrayUpdateRequest(BaseModel):
    version: Optional[str] = Field(
        None, description="Specific version to install (latest if not provided)"
    )


class XrayUpdateResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    version: str = Field(..., description="Version that was installed")
    current_version: Optional[str] = Field(
        None, description="Previously installed version"
    )


class GeodataUpdateResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    updated_files: Dict[str, bool] = Field(
        ..., description="Status of each updated file"
    )
    assets_folder: str = Field(..., description="Assets folder path used")
