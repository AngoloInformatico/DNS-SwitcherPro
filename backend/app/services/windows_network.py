from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

EventCallback = Callable[[str, str], Awaitable[None]]


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str


class CommandCancelled(RuntimeError):
    pass


class WindowsNetwork:
    def __init__(self, emit: EventCallback):
        self.emit = emit
        self._process: asyncio.subprocess.Process | None = None

    async def run_command(
        self, command: Sequence[str], cancel_event: asyncio.Event | None = None
    ) -> CommandResult:
        printable = " ".join(command)
        await self.emit("command", f"Esecuzione: {printable}")
        process_options: dict[str, object] = {}
        if sys.platform == "win32":
            process_options["creationflags"] = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
        try:
            self._process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
                **process_options,
            )
        except FileNotFoundError as exc:
            await self.emit("error", f"Comando non disponibile: {command[0]}")
            raise RuntimeError(f"Comando non disponibile: {command[0]}") from exc

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        async def consume(stream: asyncio.StreamReader | None, level: str, target: list[str]) -> None:
            if stream is None:
                return
            while line := await stream.readline():
                decoded = line.decode(errors="replace").rstrip()
                target.append(decoded)
                if decoded:
                    await self.emit(level, decoded)

        stdout_task = asyncio.create_task(consume(self._process.stdout, "output", stdout_lines))
        stderr_task = asyncio.create_task(consume(self._process.stderr, "error", stderr_lines))
        wait_task = asyncio.create_task(self._process.wait())
        cancel_task = asyncio.create_task(cancel_event.wait()) if cancel_event else None

        try:
            tasks = {wait_task}
            if cancel_task:
                tasks.add(cancel_task)
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if cancel_task and cancel_task in done and cancel_event and cancel_event.is_set():
                self._process.terminate()
                await self._process.wait()
                await self.emit("warning", "Comando annullato dall'utente")
                raise CommandCancelled("Operazione annullata")
            return_code = await wait_task
            await asyncio.gather(stdout_task, stderr_task)
        finally:
            if cancel_task:
                cancel_task.cancel()
            self._process = None

        await self.emit("success" if return_code == 0 else "error", f"Codice di uscita: {return_code}")
        return CommandResult(tuple(command), return_code, "\n".join(stdout_lines), "\n".join(stderr_lines))

    async def refresh(self, mode: str, cancel_event: asyncio.Event) -> list[CommandResult]:
        if sys.platform != "win32":
            await self.emit(
                "info",
                "Esecuzione in container: il DNS è stato aggiornato sul router; "
                "il rinnovo DHCP avverrà sui singoli dispositivi.",
            )
            return []
        commands = (
            [("ipconfig", "/release"), ("ipconfig", "/renew"), ("ipconfig", "/flushdns")]
            if mode == "full"
            else [("ipconfig", "/flushdns"), ("ipconfig", "/renew"), ("ipconfig", "/flushdns")]
        )
        results: list[CommandResult] = []
        for command in commands:
            result = await self.run_command(command, cancel_event)
            results.append(result)
            if result.return_code != 0:
                detail = result.stderr or result.stdout or "errore sconosciuto"
                if "elevation" in detail.lower() or "privileg" in detail.lower():
                    raise PermissionError("Permessi insufficienti per aggiornare la rete Windows")
                raise RuntimeError(f"Il comando {' '.join(command)} è terminato con errore")
        return results

    async def inspect(self, cancel_event: asyncio.Event | None = None) -> CommandResult:
        return await self.run_command(("ipconfig", "/all"), cancel_event)

    async def cancel(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
