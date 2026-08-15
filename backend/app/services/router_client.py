from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from backend.app.config.settings_manager import AppSettings
from backend.app.paths import ensure_work_dirs
from backend.app.security.secret_masking import mask_secrets
from backend.app.utils.validators import validate_ipv4


class RouterError(RuntimeError):
    pass


class RouterAuthenticationError(RouterError):
    pass


class RouterCompatibilityError(RouterError):
    pass


@dataclass
class DnsForm:
    url: str
    action: str
    method: str
    field_name: str
    current_value: str | None
    values: dict[str, str]


class HttpRouterAdapter:
    """DOM-driven adapter: no private firmware endpoint is assumed."""

    LINK_HINTS = ("lan", "dhcp", "local", "network", "rete")
    DNS_HINT = re.compile(r"(?i)(server[_-]?)?dns(?!.*(ipv6|dynamic|ddns))")

    def __init__(self, settings: AppSettings, username: str, password: str):
        self.settings = settings
        self.username = username
        self.password = password
        self.client = httpx.AsyncClient(
            base_url=settings.router_url,
            timeout=httpx.Timeout(settings.router_timeout),
            verify=False,
            follow_redirects=True,
            headers={"User-Agent": "DNS-Switcher-Pro/1.1"},
        )
        self._last_form: DnsForm | None = None
        self._last_submit_ok = False

    async def login(self) -> bool:
        try:
            response = await self.client.get("/")
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RouterError("Timeout durante la connessione al router") from exc
        except httpx.HTTPError as exc:
            raise RouterError("Router non raggiungibile") from exc

        form = self._find_login_form(response.text)
        if form is None:
            if BeautifulSoup(response.text, "html.parser").find("input", {"type": re.compile("password", re.I)}):
                raise RouterCompatibilityError(
                    "La pagina di accesso usa JavaScript/SRP e richiede la modalità browser Edge"
                )
            return True
        action, values, username_field, password_field = form
        values[username_field] = self.username
        values[password_field] = self.password
        try:
            result = await self.client.post(urljoin(str(response.url), action), data=values)
            result.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RouterError("Timeout durante il login al router") from exc
        except httpx.HTTPError as exc:
            raise RouterError("Errore HTTP durante il login al router") from exc
        if self._find_login_form(result.text) is not None or re.search(
            r"(?i)(credenziali|password).{0,30}(errat|invalid|wrong)", result.text
        ):
            raise RouterAuthenticationError("Credenziali router non valide")
        return True

    def _find_login_form(self, html: str) -> tuple[str, dict[str, str], str, str] | None:
        soup = BeautifulSoup(html, "html.parser")
        for form in soup.find_all("form"):
            password_input = form.find("input", {"type": re.compile("password", re.I)})
            if not isinstance(password_input, Tag) or not password_input.get("name"):
                continue
            user_input = form.find("input", {"name": re.compile(r"user|login", re.I)})
            if not isinstance(user_input, Tag) or not user_input.get("name"):
                text_inputs = form.find_all("input", {"type": re.compile(r"text|email", re.I)})
                user_input = text_inputs[0] if text_inputs else None
            if not isinstance(user_input, Tag) or not user_input.get("name"):
                continue
            return (
                str(form.get("action") or "/"),
                self._form_values(form),
                str(user_input["name"]),
                str(password_input["name"]),
            )
        return None

    @staticmethod
    def _form_values(form: Tag) -> dict[str, str]:
        values: dict[str, str] = {}
        for field in form.find_all(["input", "select", "textarea"]):
            name = field.get("name")
            if not name or field.has_attr("disabled"):
                continue
            if field.name == "select":
                selected = field.find("option", selected=True) or field.find("option")
                values[str(name)] = str(selected.get("value", "")) if selected else ""
            elif field.get("type") in {"checkbox", "radio"} and not field.has_attr("checked"):
                continue
            else:
                values[str(name)] = str(field.get("value", ""))
        return values

    async def _discover_dns_form(self) -> DnsForm:
        home = await self.client.get("/")
        home.raise_for_status()
        candidates = [str(home.url)]
        soup = BeautifulSoup(home.text, "html.parser")
        base_host = urlparse(str(home.url)).netloc
        for link in soup.find_all("a", href=True):
            href = urljoin(str(home.url), str(link["href"]))
            lowered = f"{href} {link.get_text(' ', strip=True)}".lower()
            if urlparse(href).netloc == base_host and any(hint in lowered for hint in self.LINK_HINTS):
                if href not in candidates:
                    candidates.append(href)
            if len(candidates) >= 12:
                break

        for url in candidates:
            response = home if url == str(home.url) else await self.client.get(url)
            if response.status_code >= 400:
                continue
            found = self._extract_dns_form(str(response.url), response.text)
            if found:
                self._last_form = found
                return found
        raise RouterCompatibilityError(
            "Campo Server DNS non individuato nella WebUI. Attivare la modalità compatibilità browser."
        )

    def _extract_dns_form(self, page_url: str, html: str) -> DnsForm | None:
        soup = BeautifulSoup(html, "html.parser")
        for form in soup.find_all("form"):
            values = self._form_values(form)
            for field in form.find_all(["input", "select"]):
                identity = " ".join(
                    str(field.get(key, "")) for key in ("name", "id", "aria-label", "placeholder")
                )
                if not self.DNS_HINT.search(identity):
                    continue
                name = field.get("name")
                if not name:
                    continue
                if field.name == "select":
                    selected = field.find("option", selected=True) or field.find("option")
                    raw_value = str(selected.get("value", "") if selected else "").strip()
                else:
                    raw_value = str(field.get("value", "")).strip()
                current = None
                if raw_value:
                    try:
                        current = validate_ipv4(raw_value)
                    except ValueError:
                        continue
                return DnsForm(
                    url=page_url,
                    action=urljoin(page_url, str(form.get("action") or page_url)),
                    method=str(form.get("method") or "post").lower(),
                    field_name=str(name),
                    current_value=current,
                    values=values,
                )
        return None

    async def get_current_dns(self) -> str | None:
        form = await self._discover_dns_form()
        return form.current_value

    async def set_dns(self, dns_ip: str) -> bool:
        address = validate_ipv4(dns_ip)
        form = self._last_form or await self._discover_dns_form()
        values = dict(form.values)
        values[form.field_name] = address
        try:
            if form.method == "get":
                response = await self.client.get(form.action, params=values)
            else:
                response = await self.client.post(form.action, data=values)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RouterError("Timeout durante il salvataggio del DNS") from exc
        except httpx.HTTPError as exc:
            raise RouterError("Il router ha rifiutato il salvataggio del DNS") from exc
        self._last_submit_ok = True
        self._last_form = None
        return True

    async def apply_configuration(self) -> bool:
        return self._last_submit_ok

    async def confirm_dns(self, expected: str) -> bool:
        address = validate_ipv4(expected)
        deadline = asyncio.get_running_loop().time() + self.settings.apply_timeout
        while asyncio.get_running_loop().time() < deadline:
            self._last_form = None
            try:
                if await self.get_current_dns() == address:
                    return True
            except (httpx.HTTPError, RouterCompatibilityError):
                pass
            await asyncio.sleep(0.5)
        return False

    async def logout(self) -> None:
        try:
            for path in ("/logout", "/auth/logout"):
                response = await self.client.get(path)
                if response.status_code < 400:
                    break
        finally:
            await self.client.aclose()


class BrowserRouterAdapter:
    """Fallback for JavaScript-only firmware pages, using Edge or bundled Chromium."""

    def __init__(self, settings: AppSettings, username: str, password: str):
        self.settings = settings
        self.username = username
        self.password = password
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._applied = False

    async def _visible(self, selector: str) -> Any | None:
        locator = self._page.locator(selector).first
        return locator if await locator.count() and await locator.is_visible() else None

    async def _click_login(self) -> None:
        selectors = (
            "#sign-me-in",  # TIM HUB / Technicolor SRP login
            'button[type="submit"]',
            'input[type="submit"]',
            '[role="button"][id*="login" i]',
            '[role="button"][id*="sign" i]',
            '[onclick*="login" i]',
        )
        for selector in selectors:
            candidate = await self._visible(selector)
            if candidate is not None:
                await candidate.click(timeout=3000)
                return
        for name in (r"sign in", r"log in", r"login", r"accedi", r"entra"):
            candidate = self._page.get_by_text(re.compile(rf"^{name}$", re.I)).first
            if await candidate.count() and await candidate.is_visible():
                await candidate.click(timeout=3000)
                return
        raise RouterCompatibilityError(
            "Comando di accesso non individuato nella pagina del router"
        )

    async def _wait_for_login_result(self) -> None:
        dashboard_timeout = max(self.settings.router_timeout, 20.0)
        deadline = asyncio.get_running_loop().time() + dashboard_timeout
        error_pattern = re.compile(
            r"invalid username|invalid password|wrong password|credenziali.*errat|password.*errat|accesso.*fallit",
            re.I,
        )
        while asyncio.get_running_loop().time() < deadline:
            error = self._page.get_by_text(error_pattern).first
            if await error.count() and await error.is_visible():
                raise RouterAuthenticationError("Credenziali router non valide")
            password = self._page.locator('input[type="password"]').first
            if not await password.count() or not await password.is_visible():
                try:
                    await self._page.wait_for_function(
                        """() => {
                            if (!document.body) return false;
                            const text = document.body.innerText.trim().toLowerCase();
                            const password = document.querySelector('input[type="password"]');
                            const passwordVisible = password && password.getClientRects().length > 0;
                            return !passwordVisible && text.length > 80 &&
                                   !text.includes('sign in') && !text.includes('your password');
                        }""",
                        timeout=int(dashboard_timeout * 1000),
                    )
                    await self._page.wait_for_timeout(250)
                    return
                except Exception as exc:
                    raise RouterError("Il pannello del router non si è caricato dopo l'accesso") from exc
            await self._page.wait_for_timeout(200)
        raise RouterAuthenticationError(
            "Il router non ha completato l'accesso. Verificare le credenziali o eventuali blocchi temporanei."
        )

    async def login(self) -> bool:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RouterCompatibilityError("Fallback browser non installato") from exc
        self._playwright = await async_playwright().start()
        try:
            channel = os.getenv("DNS_SWITCHER_BROWSER_CHANNEL")
            if channel is None and sys.platform == "win32":
                channel = "msedge"
            launch_options: dict[str, Any] = {"headless": True}
            if channel:
                launch_options["channel"] = channel
            self._browser = await self._playwright.chromium.launch(**launch_options)
            context = await self._browser.new_context(ignore_https_errors=True)
            self._page = await context.new_page()
            navigation_timeout = max(self.settings.router_timeout, 30.0)
            try:
                # The Technicolor UI sometimes never fires DOMContentLoaded even
                # though the login page is already usable. Waiting for the first
                # response commit avoids a false timeout before authentication.
                await self._page.goto(
                    self.settings.router_url,
                    wait_until="commit",
                    timeout=int(navigation_timeout * 1000),
                )
                await self._page.locator("body").wait_for(
                    state="attached", timeout=int(navigation_timeout * 1000)
                )
            except Exception as exc:
                raise RouterError(
                    f"Il router {self.settings.router_ip} non ha risposto entro {navigation_timeout:.0f} secondi"
                ) from exc
            password = self._page.locator('input[type="password"]').first
            if await password.count() and await password.is_visible():
                username = self._page.locator(
                    'input[name*="user" i], input[id*="user" i], input[autocomplete="username"], input[type="text"]'
                ).first
                if not await username.count():
                    raise RouterCompatibilityError("Campo nome utente non individuato")
                await username.fill(self.username)
                await password.fill(self.password)
                await self._click_login()
                await self._wait_for_login_result()
            return True
        except RouterError:
            raise
        except Exception as exc:
            raise RouterError(mask_secrets(f"Automazione browser non riuscita: {exc}", (self.password,))) from exc

    async def _find_dns_input(self) -> Any | None:
        # TIM HUB / Technicolor usa a seconda del firmware un input testuale o
        # un menu che diventa un input dopo aver scelto l'opzione "custom".
        known = self._page.locator(
            'input[name="dns_v4_pri"], select[name="dns_v4_pri"], '
            'input[name="ipv4_dns_pri"], select[name="ipv4_dns_pri"], '
            'input[name="primary_dns"], select[name="primary_dns"]'
        ).first
        if await known.count() and await known.is_visible():
            return known

        label_pattern = re.compile(
            r"(?:server\s+dns|dns\s+server|primary\s+dns|dns\s+primar|dns\s+preferenz|local\s+dns)",
            re.I,
        )
        locator = self._page.get_by_label(label_pattern).first
        if await locator.count() and await locator.is_visible():
            return locator

        controls = self._page.locator(
            'input:not([type="hidden"]):not([type="password"]), select'
        )
        for index in range(min(await controls.count(), 160)):
            field = controls.nth(index)
            if not await field.is_visible():
                continue
            identity = await field.evaluate(
                """element => {
                    const label = element.id ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`) : null;
                    return [element.name, element.id, element.getAttribute('aria-label'), element.placeholder,
                            label?.textContent, element.parentElement?.textContent].filter(Boolean).join(' ');
                }"""
            )
            lowered = str(identity).lower()
            if "dns" in lowered and not any(word in lowered for word in ("ipv6", "ddns", "dynamic")):
                return field
        return None

    async def _open_technicolor_lan_modal(self) -> bool:
        """Open the known Technicolor LAN modal without depending on its translation."""
        launchers = self._page.locator(
            '[data-remote*="ethernet-modal.lp"], '
            '[data-id*="ethernet-modal"], '
            'a[href*="ethernet-modal.lp"]'
        )
        for index in range(min(await launchers.count(), 8)):
            launcher = launchers.nth(index)
            if not await launcher.is_visible():
                continue
            try:
                await launcher.click(timeout=3000)
                await self._page.wait_for_timeout(500)
                return True
            except Exception:
                continue

        # Nelle dashboard Technicolor la funzione globale tch.loadModal carica
        # lo stesso pannello anche quando il collegamento della card è nascosto.
        try:
            opened = await self._page.evaluate(
                """() => {
                    if (!window.tch || typeof window.tch.loadModal !== 'function') return false;
                    window.tch.loadModal('modals/ethernet-modal.lp');
                    return true;
                }"""
            )
            if opened:
                await self._page.wait_for_timeout(500)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    async def _reveal_element(locator: Any) -> None:
        await locator.evaluate(
            """element => {
                let current = element;
                while (current && current !== document.documentElement) {
                    current.style.setProperty('display', 'block', 'important');
                    current.style.setProperty('visibility', 'visible', 'important');
                    current.style.setProperty('opacity', '1', 'important');
                    current.removeAttribute('hidden');
                    current = current.parentElement;
                }
            }"""
        )

    async def _open_direct_dns_page(self) -> bool:
        """Navigate to known authenticated LAN pages when the dashboard modal stalls."""
        paths = (
            "/modals/ethernet-modal.lp",
            "/modals/local-network-modal.lp",
            "/modals/lan-modal.lp",
        )
        timeout = int(max(self.settings.router_timeout, 15.0) * 1000)
        for path in paths:
            try:
                response = await self._page.goto(
                    urljoin(self.settings.router_url + "/", path.lstrip("/")),
                    wait_until="commit",
                    timeout=timeout,
                )
                if response is not None and response.status >= 400:
                    continue
                await self._page.locator("body").wait_for(state="attached", timeout=timeout)
                await self._page.wait_for_timeout(500)

                known = self._page.locator(
                    'input[name="dns_v4_pri"], select[name="dns_v4_pri"], '
                    'input[name="ipv4_dns_pri"], select[name="ipv4_dns_pri"], '
                    'input[name="primary_dns"], select[name="primary_dns"]'
                ).first
                if not await known.count():
                    continue

                # A modal fragment opened as a full page can retain Bootstrap's
                # display:none. Reveal only the DNS control and its ancestors.
                await self._reveal_element(known)
                if await known.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def _write_compatibility_diagnostic(self) -> str | None:
        """Persist structural DOM metadata without field values or page text."""
        try:
            document = await self._page.evaluate(
                """() => {
                    const visible = element => !!(element.offsetWidth || element.offsetHeight ||
                                                   element.getClientRects().length);
                    const controls = [...document.querySelectorAll('input, select, textarea, button')]
                        .slice(0, 250)
                        .map(element => {
                            const label = element.id
                                ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`)
                                : element.closest('.control-group, .form-group')?.querySelector('label');
                            return {
                                tag: element.tagName.toLowerCase(),
                                type: element.getAttribute('type'),
                                name: element.getAttribute('name'),
                                id: element.id || null,
                                aria_label: element.getAttribute('aria-label'),
                                placeholder: element.getAttribute('placeholder'),
                                label: label?.textContent?.trim().slice(0, 120) || null,
                                visible: visible(element),
                                disabled: element.disabled === true
                            };
                        });
                    const launchers = [...document.querySelectorAll('[data-remote], [data-id], a[href]')]
                        .slice(0, 250)
                        .map(element => ({
                            tag: element.tagName.toLowerCase(),
                            id: element.id || null,
                            data_remote: element.getAttribute('data-remote'),
                            data_id: element.getAttribute('data-id'),
                            href: element.getAttribute('href'),
                            title: element.getAttribute('title'),
                            aria_label: element.getAttribute('aria-label')
                        }));
                    return {
                        url: `${location.origin}${location.pathname}`,
                        title: document.title,
                        controls,
                        launchers
                    };
                }"""
            )
            document["frames"] = [
                str(frame.url).split("?", 1)[0] for frame in self._page.frames
            ]
            path = ensure_work_dirs()["logs"] / "router-diagnostic.json"
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(path)
        except Exception:
            return None

    async def _wait_for_dns_input(self, timeout: float) -> Any | None:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            found = await self._find_dns_input()
            if found is not None:
                return found
            await self._page.wait_for_timeout(250)
        return None

    async def _dns_input(self) -> Any:
        found = await self._find_dns_input()
        if found is not None:
            return found

        # TIM HUB / Technicolor AGTHP: the DNS field lives in the asynchronous
        # "Rete Locale" modal and only appears after expanding advanced options.
        if await self._open_technicolor_lan_modal():
            found = await self._wait_for_dns_input(min(self.settings.router_timeout, 5.0))
            if found is not None:
                return found
            advanced = self._page.get_by_text(
                re.compile(r"(mostra opzioni avanzate|show advanced options)", re.I)
            ).first
            if await advanced.count() and await advanced.is_visible():
                try:
                    await advanced.click(timeout=3000)
                    found = await self._wait_for_dns_input(self.settings.router_timeout)
                    if found is not None:
                        return found
                except Exception:
                    pass

        # Some TIM firmware dashboards acknowledge the click but never finish
        # injecting the modal in headless Chromium. The authenticated modal URL
        # is more reliable and keeps the same browser session/cookies.
        if await self._open_direct_dns_page():
            found = await self._find_dns_input()
            if found is not None:
                return found

        for lan_title in (r"rete locale", r"local network"):
            lan = self._page.get_by_text(re.compile(rf"^\s*{lan_title}\s*$", re.I)).first
            if not await lan.count() or not await lan.is_visible():
                continue
            try:
                await lan.click(timeout=3000)
                close_button = self._page.get_by_text(
                    re.compile(r"^\s*(chiudi|close)\s*$", re.I)
                ).first
                await close_button.wait_for(
                    state="visible", timeout=int(max(self.settings.router_timeout, 20.0) * 1000)
                )
                found = await self._find_dns_input()
                if found is not None:
                    return found
                advanced = self._page.get_by_text(
                    re.compile(r"(mostra opzioni avanzate|show advanced options)", re.I)
                ).first
                if await advanced.count() and await advanced.is_visible():
                    await advanced.click(timeout=3000)
                    found = await self._wait_for_dns_input(self.settings.router_timeout)
                    if found is not None:
                        return found
            except Exception:
                # Continue with the generic firmware navigation below.
                pass

        navigation = (
            r"home network", r"lan",
            r"show advanced options", r"mostra opzioni avanzate",
            r"dhcp server settings", r"impostazioni dhcp server", r"dhcp",
            r"network", r"rete",
        )
        for nav_text in navigation:
            candidates = self._page.get_by_text(re.compile(rf"^\s*{nav_text}\s*$", re.I))
            for index in range(min(await candidates.count(), 5)):
                candidate = candidates.nth(index)
                if not await candidate.is_visible():
                    continue
                try:
                    await candidate.click(timeout=2500)
                    # Technicolor loads modal content asynchronously and can take
                    # several seconds even on the local network.
                    found = await self._wait_for_dns_input(min(self.settings.router_timeout, 8.0))
                except Exception:
                    continue
                if found is not None:
                    return found
        diagnostic = await self._write_compatibility_diagnostic()
        detail = " Diagnostico salvato in logs/router-diagnostic.json." if diagnostic else ""
        raise RouterCompatibilityError(
            "Campo DNS IPv4 non individuato nel pannello router. Aprire Local Network/DHCP e riprovare, "
            f"oppure usare la modalità HTTP se il firmware la supporta.{detail}"
        )

    async def get_current_dns(self) -> str | None:
        value = await (await self._dns_input()).input_value()
        try:
            return validate_ipv4(value)
        except ValueError:
            return None

    async def _set_dns_control_value(self, field: Any, address: str) -> Any:
        """Set an IPv4 value on either a text input or Technicolor's DNS select."""
        tag_name = str(await field.evaluate("element => element.tagName.toLowerCase()"))
        if tag_name == "select":
            field_name = str(await field.get_attribute("name") or "dns_v4_pri")
            matching_option = field.locator(f'option[value="{address}"]')
            if await matching_option.count():
                await field.select_option(value=address)
            else:
                custom_option = field.locator(
                    'option[value="custom"], option[value="manual"], option[value="static"]'
                ).first
                if not await custom_option.count():
                    raise RouterCompatibilityError(
                        "Il menu DNS del router non permette un indirizzo personalizzato"
                    )
                custom_value = await custom_option.get_attribute("value")
                await field.select_option(value=str(custom_value))
                replacement = self._page.locator(
                    f'input[name="{field_name}"]:not([type="hidden"])'
                ).first
                await replacement.wait_for(
                    state="visible", timeout=int(max(self.settings.router_timeout, 5.0) * 1000)
                )
                field = replacement
                await field.fill(address)
        else:
            await field.fill(address)
        return field

    async def set_dns(self, dns_ip: str) -> bool:
        address = validate_ipv4(dns_ip)
        field = await self._set_dns_control_value(await self._dns_input(), address)
        await field.press("Tab")
        apply_button = self._page.locator("#save-config").first
        if await apply_button.count():
            try:
                await apply_button.wait_for(state="visible", timeout=3000)
            except Exception:
                try:
                    await self._reveal_element(apply_button)
                except Exception:
                    pass
        if not await apply_button.count() or not await apply_button.is_visible():
            apply_button = self._page.get_by_text(
                re.compile(r"^\s*(applica|salva|conferma|apply|save|confirm)\s*$", re.I)
            ).first
        if not await apply_button.count() or not await apply_button.is_visible():
            raise RouterCompatibilityError("Pulsante Applica non individuato dall'automazione browser")
        try:
            await apply_button.click(timeout=3000)
        except Exception:
            await apply_button.evaluate("element => element.click()")
        await self._page.wait_for_timeout(900)
        self._applied = True
        return True

    async def apply_configuration(self) -> bool:
        return self._applied

    async def confirm_dns(self, expected: str) -> bool:
        address = validate_ipv4(expected)
        deadline = asyncio.get_running_loop().time() + self.settings.apply_timeout
        while asyncio.get_running_loop().time() < deadline:
            try:
                field = await self._dns_input()
                if validate_ipv4(await field.input_value()) == address:
                    return True
            except (ValueError, RouterCompatibilityError):
                pass
            await self._page.wait_for_timeout(500)
        return False

    async def logout(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


class RouterClient:
    def __init__(self, settings: AppSettings, username: str, password: str):
        self.settings = settings
        self.username = username
        self.password = password
        self.adapter: HttpRouterAdapter | BrowserRouterAdapter | None = None

    async def login(self) -> bool:
        mode = self.settings.compatibility_mode
        if mode == "browser":
            self.adapter = BrowserRouterAdapter(self.settings, self.username, self.password)
            return await self.adapter.login()
        http_adapter = HttpRouterAdapter(self.settings, self.username, self.password)
        self.adapter = http_adapter
        try:
            return await http_adapter.login()
        except RouterCompatibilityError as exc:
            await http_adapter.logout()
            requires_javascript_login = "JavaScript/SRP" in str(exc)
            if mode != "auto" and not (mode == "http" and requires_javascript_login):
                raise
            self.adapter = BrowserRouterAdapter(self.settings, self.username, self.password)
            return await self.adapter.login()

    async def get_current_dns(self) -> str | None:
        if not self.adapter:
            raise RouterError("Sessione router non inizializzata")
        try:
            return await self.adapter.get_current_dns()
        except RouterCompatibilityError:
            if self.settings.compatibility_mode != "auto" or isinstance(self.adapter, BrowserRouterAdapter):
                raise
            await self.adapter.logout()
            self.adapter = BrowserRouterAdapter(self.settings, self.username, self.password)
            await self.adapter.login()
            return await self.adapter.get_current_dns()

    async def set_dns(self, dns_ip: str) -> bool:
        validate_ipv4(dns_ip)
        if not self.adapter:
            raise RouterError("Sessione router non inizializzata")
        return await self.adapter.set_dns(dns_ip)

    async def apply_configuration(self) -> bool:
        if not self.adapter:
            raise RouterError("Sessione router non inizializzata")
        return await self.adapter.apply_configuration()

    async def confirm_dns(self, expected: str) -> bool:
        validate_ipv4(expected)
        if not self.adapter:
            raise RouterError("Sessione router non inizializzata")
        return await self.adapter.confirm_dns(expected)

    async def logout(self) -> None:
        if self.adapter:
            await self.adapter.logout()
