"""Pydantic models for API request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.models.database import RoutingAction, RoutingRuleModel, XrayLogLevel


class SubscriptionCreate(BaseModel):
    name: str = Field(..., description="Name for the subscription")
    url: HttpUrl = Field(..., description="Subscription URL")


class SubscriptionUpdate(BaseModel):
    name: str | None = Field(None, description="New name for the subscription")
    url: HttpUrl | None = Field(None, description="Subscription URL")


class RoutingRuleUpdate(BaseModel):
    """Routing rule payload for settings updates."""

    id: str | None = Field(None, description="Stable rule id")
    name: str | None = Field(None, description="Optional display name")
    action: RoutingAction = Field(..., description="bypass, proxy, or block")
    domain: list[str] = Field(default_factory=list)
    ip: list[str] = Field(default_factory=list)
    port: str | None = Field(None)
    protocol: list[str] = Field(default_factory=list)
    process: list[str] = Field(default_factory=list)
    enabled: bool = Field(True)

    @field_validator("domain", "ip", "protocol", "process", mode="before")
    @classmethod
    def normalize_string_lists(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [part.strip() for part in v.split(",") if part.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @field_validator("port", mode="before")
    @classmethod
    def normalize_port(cls, v):
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    def to_model(self) -> RoutingRuleModel:
        data = self.model_dump(exclude_none=False)
        if not data.get("id"):
            data.pop("id", None)
        return RoutingRuleModel.model_validate(data)


class SettingsUpdate(BaseModel):
    socks_port: int | None = Field(None, description="Global SOCKS port override")
    http_port: int | None = Field(None, description="Global HTTP port override")
    xray_binary: str | None = Field(None, description="Path to xray binary")
    xray_assets_folder: str | None = Field(
        None,
        description="Path to xray assets folder",
    )
    xray_log_level: XrayLogLevel | None = Field(
        None,
        description="Xray log level override (debug, info, warning, error, none)",
    )
    system_proxy: Optional[bool] = Field(None, description="Enable OS-level system proxy management")
    tun_mode: Optional[bool] = Field(
        None,
        description="Enable TUN mode to route all traffic through a TUN interface",
    )
    dns_hijack: Optional[bool] = Field(
        None,
        description="Hijack DNS (port 53) via dns-out outbound through the proxy",
    )
    routing_rules: list[RoutingRuleUpdate] | None = Field(
        None,
        description="Custom routing rules for bypass, proxy, or block",
    )

    @field_validator("socks_port")
    @classmethod
    def validate_socks_port(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if not (1 <= v <= 65535):
            msg = "SOCKS port must be between 1 and 65535"
            raise ValueError(msg)
        return v

    @field_validator("http_port")
    @classmethod
    def validate_http_port(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if not (1 <= v <= 65535):
            msg = "HTTP port must be between 1 and 65535"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_port_conflict(self):
        if self.socks_port is not None and self.http_port is not None and self.socks_port == self.http_port:
            msg = "SOCKS and HTTP ports cannot be the same"
            raise ValueError(msg)
        return self


class AppearanceUpdate(BaseModel):
    theme: str | None = Field(None, description="Theme")
    font: str | None = Field(None, description="Font")
