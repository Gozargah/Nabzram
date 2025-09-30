"""
Pydantic models for API request/response schemas
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class XrayLogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    NONE = "none"


class SubscriptionCreate(BaseModel):
    name: str = Field(..., description="Name for the subscription")
    url: HttpUrl = Field(..., description="Subscription URL")


class SubscriptionUpdate(BaseModel):
    name: Optional[str] = Field(None, description="New name for the subscription")
    url: Optional[HttpUrl] = Field(None, description="Subscription URL")


class SettingsUpdate(BaseModel):
    socks_port: Optional[int] = Field(None, description="Global SOCKS port override")
    http_port: Optional[int] = Field(None, description="Global HTTP port override")
    xray_binary: Optional[str] = Field(None, description="Path to xray binary")
    xray_assets_folder: Optional[str] = Field(
        None, description="Path to xray assets folder"
    )
    xray_log_level: Optional[XrayLogLevel] = Field(
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


class AppearanceUpdate(BaseModel):
    theme: Optional[str] = Field(None, description="Theme")
    font: Optional[str] = Field(None, description="Font")
