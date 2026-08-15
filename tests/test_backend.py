from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from backend.app.api.schemas import ConnectionTestPayload
from backend.app.config.settings_manager import AppSettings
from backend.app.config.settings_manager import SettingsManager
from backend.app.database.connection import Database
from backend.app.database.repositories import SettingsRepository
from backend.app.services.router_client import (
    BrowserRouterAdapter,
    HttpRouterAdapter,
    RouterCompatibilityError,
)
from backend.app.services.operation_manager import OperationManager
from backend.app.security.credential_store import EncryptedFileBackend
from backend.app.services.windows_network import WindowsNetwork
from backend.app.utils.validators import validate_ipv4


@pytest.mark.parametrize("value, expected", [("192.168.1.1", "192.168.1.1"), (" 10.0.0.2 ", "10.0.0.2")])
def test_validate_ipv4(value: str, expected: str) -> None:
    assert validate_ipv4(value) == expected


@pytest.mark.parametrize("value", ["192.168.1.1/24", "192.168.1.1,192.168.1.2", "fe80::1", "not-an-ip"])
def test_validate_ipv4_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_ipv4(value)


def test_settings_are_persisted(tmp_path: Path) -> None:
    database = Database(tmp_path / "dns.db")
    database.initialize()
    manager = SettingsManager(SettingsRepository(database))
    manager.update({"pihole_ip": "10.0.0.2", "last_mode": "pihole"})
    reloaded = SettingsManager(SettingsRepository(database)).get()
    assert reloaded.pihole_ip == "10.0.0.2"
    assert reloaded.last_mode == "pihole"


def test_database_schema_is_local(tmp_path: Path) -> None:
    database = Database(tmp_path / "dns.db")
    database.initialize()
    with database.connect() as connection:
        names = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"settings", "router_credentials", "operation_history"} <= names


def app_settings(**overrides: object) -> AppSettings:
    values: dict[str, object] = {
        "router_ip": "192.168.1.1",
        "router_port": 80,
        "router_protocol": "http",
        "router_timeout": 2.0,
        "apply_timeout": 5.0,
        "pihole_ip": "192.168.1.2",
        "standard_dns_ip": "192.168.1.1",
        "refresh_mode": "quick",
        "theme": "system",
        "last_mode": "unknown",
        "compatibility_mode": "auto",
        "ipv6_test_enabled": False,
    }
    values.update(overrides)
    return AppSettings(**values)  # type: ignore[arg-type]


def test_javascript_login_falls_back_to_browser() -> None:
    html = """
    <html><title>Login</title><form>
      <input id="srp_username" type="text">
      <input id="srp_password" type="password">
      <div id="sign-me-in" class="btn">Sign in</div>
    </form></html>
    """
    adapter = HttpRouterAdapter(app_settings(), "admin", "secret")
    asyncio.run(adapter.client.aclose())
    adapter.client = httpx.AsyncClient(
        base_url="http://192.168.1.1",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request)),
    )
    try:
        with pytest.raises(RouterCompatibilityError, match="JavaScript/SRP"):
            asyncio.run(adapter.login())
    finally:
        asyncio.run(adapter.client.aclose())


def test_http_adapter_recognizes_technicolor_dns_select() -> None:
    html = """
    <form action="/modals/ethernet-modal.lp" method="post">
      <select name="dns_v4_pri">
        <option value="">Router</option>
        <option value="192.168.1.2" selected>Custom (192.168.1.2)</option>
      </select>
    </form>
    """
    adapter = HttpRouterAdapter(app_settings(), "admin", "secret")
    try:
        form = adapter._extract_dns_form("http://192.168.1.1/modals/ethernet-modal.lp", html)
        assert form is not None
        assert form.field_name == "dns_v4_pri"
        assert form.current_value == "192.168.1.2"
    finally:
        asyncio.run(adapter.client.aclose())


class FakeLocator:
    def __init__(self, visible: bool = False):
        self.visible = visible
        self.clicked = False

    @property
    def first(self) -> "FakeLocator":
        return self

    async def count(self) -> int:
        return int(self.visible)

    async def is_visible(self) -> bool:
        return self.visible

    async def click(self, **_: object) -> None:
        self.clicked = True


class FakeLoginPage:
    def __init__(self) -> None:
        self.sign_in = FakeLocator(visible=True)
        self.hidden = FakeLocator()

    def locator(self, selector: str) -> FakeLocator:
        return self.sign_in if selector == "#sign-me-in" else self.hidden

    def get_by_text(self, *_: object, **__: object) -> FakeLocator:
        return self.hidden


def test_browser_login_clicks_technicolor_sign_in_control() -> None:
    adapter = BrowserRouterAdapter(app_settings(), "admin", "secret")
    page = FakeLoginPage()
    adapter._page = page
    asyncio.run(adapter._click_login())
    assert page.sign_in.clicked


class FakeNavigationResponse:
    def __init__(self, status: int):
        self.status = status


class FakeBodyLocator:
    async def wait_for(self, **_: object) -> None:
        return None


class FakeDirectNavigationPage:
    def __init__(self, dashboard_url: str):
        self.url = dashboard_url
        self.dashboard_url = dashboard_url
        self.visited: list[str] = []

    async def goto(self, url: str, **_: object) -> FakeNavigationResponse:
        self.url = url
        self.visited.append(url)
        return FakeNavigationResponse(200 if url == self.dashboard_url else 404)

    def locator(self, _selector: str) -> FakeBodyLocator:
        return FakeBodyLocator()

    async def wait_for_timeout(self, _timeout: int) -> None:
        return None


def test_browser_restores_dashboard_after_direct_pages_are_not_found() -> None:
    adapter = BrowserRouterAdapter(app_settings(), "admin", "secret")
    dashboard_url = "http://192.168.1.1/"
    page = FakeDirectNavigationPage(dashboard_url)
    adapter._page = page
    adapter._dashboard_url = dashboard_url

    found = asyncio.run(adapter._open_direct_dns_page())

    assert found is False
    assert page.url == dashboard_url
    assert page.visited[0] == "http://192.168.1.1/modals/ethernet-modal.lp?intf=lan"
    assert page.visited[-1] == dashboard_url
    assert [attempt["status"] for attempt in adapter._compatibility_attempts] == [404, 404, 404, 404]


class FakeDnsOption:
    def __init__(self, value: str | None = None):
        self.value = value

    @property
    def first(self) -> "FakeDnsOption":
        return self

    async def count(self) -> int:
        return int(self.value is not None)

    async def get_attribute(self, name: str) -> str | None:
        return self.value if name == "value" else None


class FakeDnsInput:
    def __init__(self) -> None:
        self.value = ""
        self.tab_pressed = False

    @property
    def first(self) -> "FakeDnsInput":
        return self

    async def wait_for(self, **_: object) -> None:
        return None

    async def fill(self, value: str) -> None:
        self.value = value

    async def press(self, key: str) -> None:
        self.tab_pressed = key == "Tab"


class FakeDnsSelect:
    def __init__(self) -> None:
        self.selected = ""

    async def evaluate(self, _script: str) -> str:
        return "select"

    async def get_attribute(self, name: str) -> str | None:
        return "dns_v4_pri" if name == "name" else None

    def locator(self, selector: str) -> FakeDnsOption:
        if 'value="custom"' in selector:
            return FakeDnsOption("custom")
        return FakeDnsOption()

    async def select_option(self, *, value: str) -> None:
        self.selected = value


class FakeDnsPage:
    def __init__(self, replacement: FakeDnsInput):
        self.replacement = replacement

    def locator(self, _selector: str) -> FakeDnsInput:
        return self.replacement


def test_browser_dns_select_switches_to_custom_input() -> None:
    adapter = BrowserRouterAdapter(app_settings(), "admin", "secret")
    replacement = FakeDnsInput()
    adapter._page = FakeDnsPage(replacement)
    select = FakeDnsSelect()

    resulting_field = asyncio.run(adapter._set_dns_control_value(select, "192.168.1.2"))

    assert select.selected == "custom"
    assert resulting_field is replacement
    assert replacement.value == "192.168.1.2"


class InjectedSubmitAdapter(BrowserRouterAdapter):
    def __init__(self, field: FakeDnsInput):
        super().__init__(app_settings(), "admin", "secret")
        self.field = field
        self._injected_dns_fragment = True
        self.submitted = False

    async def _dns_input(self) -> FakeDnsInput:
        return self.field

    async def _set_dns_control_value(self, field: FakeDnsInput, address: str) -> FakeDnsInput:
        await field.fill(address)
        return field

    async def _submit_injected_dns_form(self) -> None:
        self.submitted = True


def test_injected_dns_fragment_uses_authenticated_form_submission() -> None:
    field = FakeDnsInput()
    adapter = InjectedSubmitAdapter(field)

    assert asyncio.run(adapter.set_dns("192.168.1.2")) is True
    assert adapter.submitted is True
    assert adapter._applied is True
    assert field.tab_pressed is True
    assert field.value == "192.168.1.2"


def test_connection_payload_validates_draft_address() -> None:
    payload = ConnectionTestPayload(target="pihole", address=" 10.0.0.2 ")
    assert payload.address == "10.0.0.2"
    with pytest.raises(ValueError):
        ConnectionTestPayload(target="pihole", address="not-an-ip")


class FakeSettingsManager:
    def __init__(self, current: AppSettings):
        self.current = current
        self.updates: list[dict[str, object]] = []

    def get(self) -> AppSettings:
        return self.current

    def update(self, values: dict[str, object]) -> AppSettings:
        self.updates.append(values)
        return self.current


class FakeCredentials:
    def get(self) -> tuple[str, str]:
        return "admin", "secret"


class FakeHistory:
    def __init__(self) -> None:
        self.finished: tuple[int, str, str] | None = None

    def start(self, _mode: str, _target: str) -> int:
        return 7

    def finish(self, operation_id: int, status: str, message: str) -> None:
        self.finished = operation_id, status, message


class FakeBroker:
    async def publish(self, _level: str, _message: str) -> None:
        return None


class FakeNetwork:
    async def refresh(self, _mode: str, _cancel_event: asyncio.Event) -> list[object]:
        return []

    async def cancel(self) -> None:
        return None


class FakeVerifier:
    async def port_reachable(self, _target: str) -> bool:
        return True

    async def verify(self, target: str, _cancel_event: asyncio.Event) -> tuple[bool, str]:
        return False, f"Il resolver {target} non ha risposto correttamente"


class FakeRouter:
    current_dns = "192.168.1.1"
    set_calls = 0

    def __init__(self, *_args: object):
        pass

    async def login(self) -> None:
        return None

    async def logout(self) -> None:
        return None

    async def get_current_dns(self) -> str:
        return self.current_dns

    async def set_dns(self, _target: str) -> bool:
        type(self).set_calls += 1
        return True

    async def apply_configuration(self) -> bool:
        return True

    async def confirm_dns(self, _target: str) -> bool:
        return True


def make_operation_manager() -> tuple[OperationManager, FakeSettingsManager, FakeHistory]:
    settings = FakeSettingsManager(app_settings())
    history = FakeHistory()
    manager = OperationManager(settings, FakeCredentials(), history, FakeBroker())  # type: ignore[arg-type]
    manager.network = FakeNetwork()  # type: ignore[assignment]
    manager.verifier = FakeVerifier()  # type: ignore[assignment]
    return manager, settings, history


def test_router_confirmation_is_success_even_when_resolver_test_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.app.services.operation_manager.RouterClient", FakeRouter)
    FakeRouter.current_dns = "192.168.1.1"
    FakeRouter.set_calls = 0
    manager, settings, history = make_operation_manager()

    asyncio.run(manager._switch("pihole"))

    assert manager.status.active_mode == "pihole"
    assert manager.status.dns_ip == "192.168.1.2"
    assert manager.status.error is None
    assert manager.status.warning and "applicato al router" in manager.status.warning
    assert history.finished and history.finished[1] == "success"
    assert settings.updates == [{"last_mode": "pihole"}]
    assert FakeRouter.set_calls == 1


def test_switch_is_idempotent_when_dns_is_already_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.app.services.operation_manager.RouterClient", FakeRouter)
    FakeRouter.current_dns = "192.168.1.2"
    FakeRouter.set_calls = 0
    manager, _, history = make_operation_manager()

    asyncio.run(manager._switch("pihole"))

    assert manager.status.active_mode == "pihole"
    assert history.finished and history.finished[1] == "success"
    assert FakeRouter.set_calls == 0


def test_container_credential_backend_encrypts_password(tmp_path: Path) -> None:
    path = tmp_path / "router_credentials.enc"
    backend = EncryptedFileBackend(path, "a-secure-container-token-with-32-characters")

    backend.set_password("DNS-Switcher-Pro", "router-admin", "very-secret-password")

    assert backend.get_password("DNS-Switcher-Pro", "router-admin") == "very-secret-password"
    assert b"very-secret-password" not in path.read_bytes()


def test_linux_container_skips_windows_dhcp_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[tuple[str, str]] = []

    async def emit(level: str, message: str) -> None:
        messages.append((level, message))

    monkeypatch.setattr("backend.app.services.windows_network.sys.platform", "linux")
    network = WindowsNetwork(emit)

    result = asyncio.run(network.refresh("quick", asyncio.Event()))

    assert result == []
    assert any("container" in message for _, message in messages)


def test_container_accepts_lan_host_with_valid_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = "container-session-token-with-more-than-32-characters"
    monkeypatch.setenv("DNS_SWITCHER_CONTAINER", "1")
    monkeypatch.setenv("DNS_SWITCHER_WORK_DIR", str(tmp_path / "container-data"))
    monkeypatch.setenv("DNS_SWITCHER_SESSION_TOKEN", token)
    monkeypatch.setenv("DNS_SWITCHER_ALLOWED_HOSTS", "*")
    from backend.app.main import create_app

    app = create_app(session_token=token)

    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://zimaos.local") as client:
            return await client.get("/api/health", headers={"X-Session-Token": token})

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
