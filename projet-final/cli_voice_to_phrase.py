# cli_voice_to_phrase.py
# Micro -> Vosk -> affiche les résultats (partial et/ou final).
#
# Dépend:
#   - speech_vosk.py
#
# Installation:
#   pip install vosk sounddevice
#
# Exemples:
#   python cli_voice_to_phrase.py
#   python cli_voice_to_phrase.py --show_partial
#   python cli_voice_to_phrase.py --model "voix-langue-des-signes-feature-stt-yohann/stt/model/vosk-model-small-fr-0.22" --device 1

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from speech_vosk import iter_vosk_results


DEFAULT_MODEL = "voix-langue-des-signes-feature-stt-yohann/stt/model/vosk-model-small-fr-0.22"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Dossier du modèle Vosk")
    ap.add_argument("--samplerate", type=int, default=16000, help="Hz (recommandé: 16000)")
    ap.add_argument("--device", type=int, default=None, help="Index du micro (optionnel)")
    ap.add_argument("--show_partial", action="store_true", help="Affiche les résultats partiels")
    args = ap.parse_args()

    model_path = Path(args.model)

    print("Listening... (Ctrl+C pour arrêter)")
    print(f"Model: {model_path.resolve()}\n")

    last_partial = ""

    try:
        for res in iter_vosk_results(model_path, samplerate=args.samplerate, device=args.device):
            if res.kind == "partial" and args.show_partial:
                # évite de spam si identique
                if res.text != last_partial:
                    last_partial = res.text
                    print("\rPARTIAL:", res.text[:100].ljust(100), end="")

            elif res.kind == "final":
                if args.show_partial:
                    # nettoie la ligne PARTIAL avant d'imprimer un FINAL
                    print("\r" + (" " * 140), end="\r")
                print("FINAL:", res.text)

    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
