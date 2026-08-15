from __future__ import annotations

from ipaddress import IPv4Address, ip_address


def validate_ipv4(value: str) -> str:
    candidate = value.strip()
    if any(character in candidate for character in ("/", ",", ";", " ")):
        raise ValueError("Inserire un solo indirizzo IPv4, senza slash o testo aggiuntivo")
    try:
        parsed = ip_address(candidate)
    except ValueError as exc:
        raise ValueError("Indirizzo IPv4 non valido") from exc
    if not isinstance(parsed, IPv4Address):
        raise ValueError("È richiesto un indirizzo IPv4")
    return str(parsed)

