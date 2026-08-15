from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.app.config.defaults import DEFAULT_SETTINGS
from backend.app.database.repositories import SettingsRepository
from backend.app.utils.validators import validate_ipv4


@dataclass(frozen=True)
class AppSettings:
    router_ip: str
    router_port: int
    router_protocol: str
    router_timeout: float
    apply_timeout: float
    pihole_ip: str
    standard_dns_ip: str
    refresh_mode: str
    theme: str
    last_mode: str
    compatibility_mode: str
    ipv6_test_enabled: bool

    @property
    def router_url(self) -> str:
        default_port = 443 if self.router_protocol == "https" else 80
        suffix = "" if self.router_port == default_port else f":{self.router_port}"
        return f"{self.router_protocol}://{self.router_ip}{suffix}"

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


class SettingsManager:
    ALLOWED = set(DEFAULT_SETTINGS)

    def __init__(self, repository: SettingsRepository):
        self.repository = repository
        existing = repository.all()
        missing = {key: value for key, value in DEFAULT_SETTINGS.items() if key not in existing}
        if missing:
            repository.set_many(missing)

    def get(self) -> AppSettings:
        values = DEFAULT_SETTINGS | self.repository.all()
        return AppSettings(
            router_ip=validate_ipv4(values["router_ip"]),
            router_port=int(values["router_port"]),
            router_protocol=values["router_protocol"],
            router_timeout=float(values["router_timeout"]),
            apply_timeout=float(values["apply_timeout"]),
            pihole_ip=validate_ipv4(values["pihole_ip"]),
            standard_dns_ip=validate_ipv4(values["standard_dns_ip"]),
            refresh_mode=values["refresh_mode"],
            theme=values["theme"],
            last_mode=values["last_mode"],
            compatibility_mode=values["compatibility_mode"],
            ipv6_test_enabled=values["ipv6_test_enabled"].lower() == "true",
        )

    def update(self, values: dict[str, object]) -> AppSettings:
        unknown = set(values) - self.ALLOWED
        if unknown:
            raise ValueError(f"Impostazioni non supportate: {', '.join(sorted(unknown))}")
        serialized = {key: str(value).lower() if isinstance(value, bool) else str(value) for key, value in values.items()}
        self.repository.set_many(serialized)
        return self.get()

    def reset(self) -> AppSettings:
        self.repository.set_many(DEFAULT_SETTINGS)
        return self.get()

