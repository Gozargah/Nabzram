"""Pydantic models for API request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.models.database import XrayLogLevel


class SubscriptionCreate(BaseModel):
    name: str = Field(..., description="Name for the subscription")
    url: HttpUrl = Field(..., description="Subscription URL")


class SubscriptionUpdate(BaseModel):
    name: str | None = Field(None, description="New name for the subscription")
    url: HttpUrl | None = Field(None, description="Subscription URL")


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
    system_proxy: Optional[bool] = Field(
        None, description="Enable OS-level system proxy management"
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
