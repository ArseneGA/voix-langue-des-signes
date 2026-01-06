# voice_to_phrase.py
# Micro -> Vosk -> texte (phrase), sans mots-clés, sans SigML.
#
# Installation (Windows):
#   pip install vosk sounddevice
#
# Lancement depuis:
#   C:\Users\arsen\Desktop\10_Projets\Au513\video
#   python voice_to_phrase.py
#
# Optionnel:
#   python voice_to_phrase.py --show_partial
#   python voice_to_phrase.py --model "voix-langue-des-signes-feature-stt-yohann/stt/model/vosk-model-small-fr-0.22"

import argparse
import json
import queue
import sys
from pathlib import Path

from vosk import Model, KaldiRecognizer

try:
    import sounddevice as sd
except ImportError:
    sd = None


DEFAULT_MODEL = "voix-langue-des-signes-feature-stt-yohann/stt/model/vosk-model-small-fr-0.22"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Dossier du modèle Vosk")
    ap.add_argument("--samplerate", type=int, default=16000, help="Hz (reco: 16000)")
    ap.add_argument("--device", type=int, default=None, help="Index device micro (optionnel)")
    ap.add_argument("--show_partial", action="store_true", help="Affiche les résultats partiels")
    args = ap.parse_args()

    if sd is None:
        print("Erreur: sounddevice non installé.\n  pip install sounddevice", file=sys.stderr)
        sys.exit(1)

    model_path = Path(args.model)
    if not model_path.exists():
        raise FileNotFoundError(f"Modèle introuvable: {model_path.resolve()}")

    model = Model(str(model_path))
    rec = KaldiRecognizer(model, args.samplerate)
    rec.SetWords(False)

    q: "queue.Queue[bytes]" = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            # warnings audio (over/underflow)
            pass
        q.put(bytes(indata))

    print("Listening... (Ctrl+C pour arrêter)")
    print(f"Model: {model_path.resolve()}")
    print(f"Sample rate: {args.samplerate} Hz\n")

    try:
        with sd.RawInputStream(
            samplerate=args.samplerate,
            blocksize=8000,
            dtype="int16",
            channels=1,
            device=args.device,
            callback=callback,
        ):
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = (res.get("text") or "").strip()
                    if text:
                        print(f"FINAL: {text}")
                else:
                    if args.show_partial:
                        res = json.loads(rec.PartialResult())
                        partial = (res.get("partial") or "").strip()
                        if partial:
                            print(f"PARTIAL: {partial}")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        # libère proprement
        try:
            rec.FinalResult()
        except Exception:
            pass


if __name__ == "__main__":
    main()
