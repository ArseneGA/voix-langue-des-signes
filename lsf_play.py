# lsf_play.py
# Helpers pour convertir une liste de Step (SIGN/SPELL/SKIP) en SigML jouable
# et l'envoyer au SiGML-Player via TCP.
#
# Dépend de:
#   - phrase_to_sigml_sequence.py (structures Step + resolve_local_sigml)
#   - sigml_player.py (send)

from __future__ import annotations

import time
from pathlib import Path
from typing import List

import phrase_to_sigml_sequence as seq
from sigml_player import send


# ----------------------------
# Helpers internes
# ----------------------------

def _iter_spell_files(sigml_dir: Path, text: str) -> List[Path]:
    """
    Convertit une chaîne à épeler en liste de Paths de .sigml (lettres / chiffres).
    - lettres: a.sigml ... z.sigml
    - chiffres: 0.sigml ... 9.sigml (si présents)
    Ignore tout le reste.
    """
    sigml_dir = Path(sigml_dir)
    files: List[Path] = []

    for ch in (text or "").lower():
        if "a" <= ch <= "z":
            files.append(seq.resolve_local_sigml(sigml_dir, f"{ch}.sigml"))
        elif ch.isdigit():
            files.append(seq.resolve_local_sigml(sigml_dir, f"{ch}.sigml"))
        else:
            # ignore espaces, tirets, etc.
            continue

    return files


# ----------------------------
# API
# ----------------------------

def steps_to_blobs(sigml_dir: Path, steps: List[seq.Step]) -> List[bytes]:
    """
    Convertit une liste de Step en une liste de blobs SigML (bytes).
    - SIGN: charge <value> (fichier .sigml)
    - SPELL: charge lettre par lettre (a.sigml..z.sigml, et chiffres si présents)
    - SKIP: ignoré
    """
    sigml_dir = Path(sigml_dir)
    blobs: List[bytes] = []

    for st in steps:
        if st.kind == "SKIP":
            continue

        if st.kind == "SIGN":
            p = seq.resolve_local_sigml(sigml_dir, st.value)
            blobs.append(p.read_bytes())
            continue

        if st.kind == "SPELL":
            for p in _iter_spell_files(sigml_dir, st.value):
                blobs.append(p.read_bytes())
            continue

        # Si un kind inconnu arrive, on ignore (ou tu peux raise)
        continue

    return blobs


def play_steps(
    sigml_dir: Path,
    steps: List[seq.Step],
    host: str = "127.0.0.1",
    port: int = 8052,
    delay_sign: float = 1.15,
    delay_letter: float = 0.35,
) -> None:
    """
    Joue une liste de Step en envoyant chaque SigML au player.
    - délai différent pour SIGN vs lettres d'épellation.
    """
    sigml_dir = Path(sigml_dir)

    for st in steps:
        if st.kind == "SKIP":
            continue

        if st.kind == "SIGN":
            p = seq.resolve_local_sigml(sigml_dir, st.value)
            send(p.read_bytes(), host=host, port=port)
            time.sleep(delay_sign)
            continue

        if st.kind == "SPELL":
            for p in _iter_spell_files(sigml_dir, st.value):
                send(p.read_bytes(), host=host, port=port)
                time.sleep(delay_letter)
            continue

        # kind inconnu: ignore
        continue
