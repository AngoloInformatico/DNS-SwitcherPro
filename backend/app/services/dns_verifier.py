from __future__ import annotations

import asyncio

from backend.app.services.windows_network import WindowsNetwork
from backend.app.utils.validators import validate_ipv4


class DnsVerifier:
    def __init__(self, network: WindowsNetwork):
        self.network = network

    async def port_reachable(self, dns_ip: str, timeout: float = 2.0) -> bool:
        address = validate_ipv4(dns_ip)
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(address, 53), timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            return False

    async def verify(self, dns_ip: str, cancel_event: asyncio.Event) -> tuple[bool, str]:
        address = validate_ipv4(dns_ip)
        result = await self.network.run_command(("nslookup", "google.com.", address), cancel_event)
        combined = f"{result.stdout}\n{result.stderr}".lower()
        failed_markers = ("timed out", "server failed", "non-existent domain", "impossibile", "timeout")
        valid = result.return_code == 0 and not any(marker in combined for marker in failed_markers)
        message = (
            f"Query DNS completata tramite {address}"
            if valid
            else f"Il resolver {address} non ha risposto correttamente"
        )
        return valid, message

