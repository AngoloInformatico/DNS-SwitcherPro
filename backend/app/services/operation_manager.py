from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

import httpx

from backend.app.config.settings_manager import SettingsManager
from backend.app.database.repositories import HistoryRepository
from backend.app.security.credential_store import CredentialStore
from backend.app.services.dns_verifier import DnsVerifier
from backend.app.services.events import EventBroker
from backend.app.services.router_client import RouterClient
from backend.app.services.windows_network import CommandCancelled, WindowsNetwork

Mode = Literal["pihole", "standard"]


@dataclass
class OperationStatus:
    active_mode: str = "unknown"
    dns_ip: str | None = None
    router_ip: str = ""
    last_change: str | None = None
    last_verification: str = "Non ancora eseguita"
    last_operation_at: str | None = None
    busy: bool = False
    checking_router: bool = False
    requested_mode: str | None = None
    error: str | None = None
    warning: str | None = None


class OperationManager:
    def __init__(self, settings: SettingsManager, credentials: CredentialStore,
                 history: HistoryRepository, broker: EventBroker):
        self.settings_manager = settings
        self.credentials = credentials
        self.history = history
        self.broker = broker
        current = settings.get()
        self.status = OperationStatus(
            # Mostra immediatamente l'ultimo valore confermato, poi il frontend
            # lo confronta in background con il dato effettivo del router.
            active_mode=current.last_mode,
            dns_ip=(current.pihole_ip if current.last_mode == "pihole" else current.standard_dns_ip)
            if current.last_mode in {"pihole", "standard"} else None,
            router_ip=current.router_ip,
        )
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._cancel_event = asyncio.Event()
        self.network = WindowsNetwork(self._emit)
        self.verifier = DnsVerifier(self.network)

    async def _emit(self, level: str, message: str) -> None:
        await self.broker.publish(level, message)

    def public_status(self) -> dict[str, object]:
        return asdict(self.status)

    def start(self, mode: Mode) -> None:
        if self.status.checking_router:
            raise RuntimeError("Attendere il rilevamento del DNS configurato sul router")
        if self.status.busy or (self._task and not self._task.done()):
            raise RuntimeError("È già in corso un'operazione")
        self._cancel_event = asyncio.Event()
        # Blocca subito ulteriori clic, prima ancora che il task asincrono inizi.
        self.status.busy = True
        self.status.requested_mode = mode
        self.status.error = None
        self.status.warning = None
        self._task = asyncio.create_task(self._switch(mode), name=f"dns-switch-{mode}")

    async def wait(self) -> None:
        if self._task:
            await self._task

    async def cancel(self) -> None:
        if not self._task or self._task.done():
            return
        self._cancel_event.set()
        await self.network.cancel()

    async def _switch(self, mode: Mode) -> None:
        async with self._lock:
            settings = self.settings_manager.get()
            target = settings.pihole_ip if mode == "pihole" else settings.standard_dns_ip
            label = "DNS Pi-hole" if mode == "pihole" else "DNS Standard"
            operation_id = self.history.start(mode, target)
            self.status.router_ip = settings.router_ip
            await self._emit("info", f"Modalità richiesta: {label}")
            router: RouterClient | None = None
            try:
                if mode == "pihole":
                    await self._emit("info", f"Verifica server Pi-hole: {target}")
                    if not await self.verifier.port_reachable(target):
                        raise RuntimeError("Pi-hole non raggiungibile sulla porta DNS 53. Controllare server e firewall.")
                    await self._emit("success", "Server Pi-hole raggiungibile sulla porta DNS 53")

                username, password = self.credentials.get()
                await self._emit("info", f"Connessione al router {settings.router_ip}")
                router = RouterClient(settings, username, password)
                await router.login()
                await self._emit("success", "Login router completato")
                previous = await router.get_current_dns()
                await self._emit("info", f"DNS precedente: {previous or 'non rilevato'}")
                if previous == target:
                    await self._emit("success", f"DNS {target} già configurato sul router")
                else:
                    await self._emit("info", f"Impostazione nuovo DNS: {target}")
                    if not await router.set_dns(target) or not await router.apply_configuration():
                        raise RuntimeError("Il router non ha confermato il salvataggio")
                    await self._emit("info", "Conferma del DNS salvato nel pannello router")
                    if not await router.confirm_dns(target):
                        raise RuntimeError(
                            f"Il router non mostra il DNS {target} dopo il salvataggio. "
                            "La configurazione non è stata considerata completata."
                        )
                await self._emit("success", f"Configurazione router confermata: DNS {target}")

                # Da questo momento il cambio è riuscito: il pannello del router è
                # la fonte autorevole. I controlli locali successivi non devono
                # trasformare un salvataggio confermato in un falso errore.
                now = datetime.now().astimezone().isoformat()
                self.settings_manager.update({"last_mode": mode})
                self.status.active_mode = mode
                self.status.dns_ip = target
                self.status.last_change = f"{previous or 'sconosciuto'} → {target}"
                self.status.last_operation_at = now
                self.status.last_verification = f"DNS {target} confermato sul router"

                warnings: list[str] = []
                try:
                    await self.network.refresh(settings.refresh_mode, self._cancel_event)
                    if settings.refresh_mode == "full":
                        warnings.append("La connettività può impiegare alcuni secondi a tornare disponibile.")
                except CommandCancelled:
                    warnings.append("Aggiornamento della rete Windows annullato; il DNS sul router è già stato applicato.")
                except Exception as exc:
                    warnings.append(f"DNS applicato, ma aggiornamento rete Windows non completato: {exc}")

                verification_message = self.status.last_verification
                if not self._cancel_event.is_set():
                    try:
                        valid, resolver_message = await self.verifier.verify(target, self._cancel_event)
                        if valid:
                            verification_message = resolver_message
                        else:
                            verification_message = (
                                f"DNS {target} confermato sul router; il test del resolver non ha risposto"
                            )
                            warnings.append(
                                f"DNS {target} applicato al router. Il test del resolver non ha risposto; "
                                "il lease DHCP locale potrebbe non essere ancora aggiornato."
                            )
                    except CommandCancelled:
                        verification_message = f"DNS {target} confermato sul router"
                    except Exception as exc:
                        verification_message = f"DNS {target} confermato sul router"
                        warnings.append(f"DNS applicato; test del resolver non disponibile: {exc}")

                self.status.last_verification = verification_message
                self.status.warning = " ".join(warnings) or None
                result_message = self.status.warning or verification_message
                self.history.finish(operation_id, "success", result_message)
                if self.status.warning:
                    await self._emit("warning", self.status.warning)
                await self._emit("success", f"Operazione completata: {label} attivo sul router")
            except CommandCancelled:
                self.status.error = "Operazione annullata"
                self.history.finish(operation_id, "cancelled", self.status.error)
                await self._emit("warning", self.status.error)
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                self.status.error = message
                self.status.last_operation_at = datetime.now().astimezone().isoformat()
                self.history.finish(operation_id, "error", message)
                await self._emit("error", message)
                await self._emit("warning", "Verificare le impostazioni e riprovare.")
            finally:
                if router:
                    await router.logout()
                self.status.busy = False
                self.status.requested_mode = None

    async def refresh_router_status(self) -> dict[str, object]:
        """Legge il DNS effettivo dal router senza modificarne la configurazione."""
        if self.status.busy:
            return self.public_status()
        self.status.checking_router = True
        router: RouterClient | None = None
        try:
            async with self._lock:
                settings = self.settings_manager.get()
                username, password = self.credentials.get()
                router = RouterClient(settings, username, password)
                await self._emit("info", f"Lettura DNS configurato sul router {settings.router_ip}")
                await router.login()
                current_dns = await router.get_current_dns()
                if not current_dns:
                    raise RuntimeError("Il router non ha restituito un indirizzo DNS")

                if current_dns == settings.pihole_ip:
                    active_mode = "pihole"
                elif current_dns == settings.standard_dns_ip:
                    active_mode = "standard"
                else:
                    active_mode = "unknown"

                now = datetime.now().astimezone().isoformat()
                self.status.active_mode = active_mode
                self.status.dns_ip = current_dns
                self.status.router_ip = settings.router_ip
                self.status.last_operation_at = now
                self.status.last_verification = f"DNS {current_dns} letto direttamente dal router"
                self.status.error = None
                self.status.warning = (
                    f"Il router usa il DNS {current_dns}, che non corrisponde alle due modalità configurate."
                    if active_mode == "unknown" else None
                )
                if active_mode != "unknown":
                    self.settings_manager.update({"last_mode": active_mode})
                await self._emit("success", f"DNS attivo rilevato sul router: {current_dns}")
        except Exception as exc:
            self.status.warning = f"Impossibile leggere automaticamente il DNS dal router: {exc}"
            await self._emit("warning", self.status.warning)
        finally:
            if router:
                await router.logout()
            self.status.checking_router = False
        return self.public_status()

    async def test_connection(
        self,
        target: str,
        *,
        address: str | None = None,
        router_protocol: str | None = None,
        router_port: int | None = None,
        router_timeout: float | None = None,
    ) -> tuple[bool, str]:
        settings = self.settings_manager.get()
        if target == "pihole":
            tested_address = address or settings.pihole_ip
            ok = await self.verifier.port_reachable(tested_address)
            return ok, f"Pi-hole {tested_address} risponde sulla porta DNS 53" if ok else f"Pi-hole {tested_address} non risponde sulla porta DNS 53"
        if target == "standard":
            tested_address = address or settings.standard_dns_ip
            ok = await self.verifier.port_reachable(tested_address)
            return ok, f"DNS standard {tested_address} raggiungibile" if ok else f"DNS standard {tested_address} non raggiungibile sulla porta 53"
        tested_address = address or settings.router_ip
        protocol = router_protocol or settings.router_protocol
        port = router_port or settings.router_port
        timeout = router_timeout or settings.router_timeout
        default_port = 443 if protocol == "https" else 80
        suffix = "" if port == default_port else f":{port}"
        router_url = f"{protocol}://{tested_address}{suffix}"
        try:
            async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True) as client:
                response = await client.get(router_url)
            ok = response.status_code < 500
            return ok, f"Router {tested_address} raggiungibile (HTTP {response.status_code})"
        except (httpx.HTTPError, OSError):
            return False, f"Router {tested_address} non raggiungibile"
