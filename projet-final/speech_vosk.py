# speech_vosk.py
# Micro -> Vosk : générateur d'événements (partial/final) réutilisable.
#
# Dépendances:
#   pip install vosk sounddevice
#
# API:
#   - SpeechResult(kind, text)
#   - iter_vosk_results(model_path, samplerate, device, blocksize, accept_empty_final)
#       -> generator[SpeechResult]

from __future__ import annotations

import json
import queue
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

try:
    from vosk import Model, KaldiRecognizer  # type: ignore
except Exception:  # pragma: no cover
    Model = None
    KaldiRecognizer = None

try:
    import sounddevice as sd  # type: ignore
except Exception:  # pragma: no cover
    sd = None


@dataclass(frozen=True)
class SpeechResult:
    kind: str  # "partial" | "final"
    text: str


def iter_vosk_results(
    model_path: Path,
    samplerate: int = 16000,
    device: Optional[int] = None,
    blocksize: int = 8000,
    accept_empty_final: bool = False,
) -> Generator[SpeechResult, None, None]:
    """
    Ouvre le micro et yield en continu des résultats Vosk.

    Entrées:
      - model_path: dossier du modèle Vosk (ex: vosk-model-small-fr-0.22)
      - samplerate: 16000 recommandé
      - device: index du micro (optionnel)
      - blocksize: taille des chunks audio (impact latence)
      - accept_empty_final: si True, yield aussi les finals vides

    Sortie:
      - generator de SpeechResult(kind="partial"/"final", text="...")

    Erreurs:
      - si vosk ou sounddevice non installés
      - si modèle introuvable
      - si device audio indisponible
    """
    if sd is None:
        raise RuntimeError("sounddevice non installé. Installe: pip install sounddevice")
    if Model is None or KaldiRecognizer is None:
        raise RuntimeError("vosk non installé. Installe: pip install vosk")

    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Modèle Vosk introuvable: {model_path.resolve()}")

    model = Model(str(model_path))
    rec = KaldiRecognizer(model, samplerate)

    q: "queue.Queue[bytes]" = queue.Queue()

    def callback(indata, frames, time_info, status):  # noqa: ARG001
        # indata est un buffer brut (dtype int16)
        q.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=samplerate,
        blocksize=blocksize,
        dtype="int16",
        channels=1,
        device=device,
        callback=callback,
    ):
        while True:
            data = q.get()

            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result() or "{}")
                txt = (res.get("text") or "").strip()
                if txt or accept_empty_final:
                    yield SpeechResult(kind="final", text=txt)
            else:
                res = json.loads(rec.PartialResult() or "{}")
                txt = (res.get("partial") or "").strip()
                if txt:
                    yield SpeechResult(kind="partial", text=txt)
