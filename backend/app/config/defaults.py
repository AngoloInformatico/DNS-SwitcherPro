"""Application defaults. Operational services always read these via SettingsManager."""

DEFAULT_SETTINGS: dict[str, str] = {
    "router_ip": "192.168.1.1",
    "router_port": "80",
    "router_protocol": "http",
    "router_timeout": "10",
    "apply_timeout": "30",
    "pihole_ip": "192.168.1.2",
    "standard_dns_ip": "192.168.1.1",
    "refresh_mode": "quick",
    "theme": "system",
    "last_mode": "unknown",
    "compatibility_mode": "auto",
    "ipv6_test_enabled": "false",
}

APP_NAME = "DNS Switcher Pro"
APP_VERSION = "1.1.3"
CREDENTIAL_SERVICE = "DNS-Switcher-Pro"
CREDENTIAL_KEY = "router-admin"
