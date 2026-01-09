# sigml_player.py
# Client TCP minimal pour envoyer du SigML au SiGML-Player + helper pour lancer l'exe.
#
# Hypothèse: le SiGML-Player écoute sur 127.0.0.1:8052 (paramétrable).
#
# API:
#   - send(sigml_xml: bytes, host, port, timeout) -> None
#   - can_connect(host, port, timeout) -> bool
#   - start_player(player_exe: Path, host, port, wait_ready, max_wait_s) -> Popen|None

from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from typing import Optional


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8052


def send(sigml_xml: bytes, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 5.0) -> None:
    """
    Envoie un blob SigML (XML en bytes) au SiGML-Player via TCP.
    """
    if not isinstance(sigml_xml, (bytes, bytearray)):
        raise TypeError("sigml_xml doit être de type bytes/bytearray")

    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(sigml_xml)


def can_connect(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 0.5) -> bool:
    """
    Retourne True si un serveur écoute déjà sur host:port.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_player(
    player_exe: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    wait_ready: bool = True,
    max_wait_s: float = 8.0,
) -> Optional[subprocess.Popen]:
    """
    Lance SiGML-Player.exe si aucune connexion n'est possible sur host:port.

    Sorties:
      - None si le player est déjà lancé (port joignable)
      - subprocess.Popen si on a lancé un nouveau process (même si non prêt)

    Notes:
      - Certains executables fonctionnent mieux si on fixe cwd au dossier de l'exe.
      - wait_ready: si True, on attend (au plus max_wait_s) que le port réponde.
    """
    if can_connect(host, port):
        return None

    player_exe = Path(player_exe)
    if not player_exe.exists():
        raise FileNotFoundError(f"SiGML-Player introuvable: {player_exe.resolve()}")

    proc = subprocess.Popen([str(player_exe)], cwd=str(player_exe.parent))

    if not wait_ready:
        return proc

    t0 = time.time()
    while time.time() - t0 < max_wait_s:
        if can_connect(host, port):
            return proc
        time.sleep(0.25)

    return proc
