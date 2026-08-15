from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.utils.validators import validate_ipv4


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    router_ip: str
    router_port: int = Field(ge=1, le=65535)
    router_protocol: Literal["http", "https"]
    router_timeout: float = Field(ge=1, le=120)
    apply_timeout: float = Field(ge=5, le=300)
    pihole_ip: str
    standard_dns_ip: str
    refresh_mode: Literal["quick", "full"]
    theme: Literal["light", "dark", "system"]
    compatibility_mode: Literal["auto", "http", "browser"]
    ipv6_test_enabled: bool = False

    @field_validator("router_ip", "pihole_ip", "standard_dns_ip")
    @classmethod
    def ipv4_only(cls, value: str) -> str:
        return validate_ipv4(value)


class CredentialsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=128)
    password: str | None = Field(default=None, max_length=512)


class SwitchPayload(BaseModel):
    mode: Literal["pihole", "standard"]


class ConnectionTestPayload(BaseModel):
    target: Literal["router", "pihole", "standard"]
    address: str | None = None
    router_protocol: Literal["http", "https"] | None = None
    router_port: int | None = Field(default=None, ge=1, le=65535)
    router_timeout: float | None = Field(default=None, ge=1, le=120)

    @field_validator("address")
    @classmethod
    def address_is_ipv4(cls, value: str | None) -> str | None:
        return validate_ipv4(value) if value is not None else None
