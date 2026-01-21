# cli_voice_play.py
# Micro -> Vosk -> (FINAL) -> Steps LSF -> envoi au SiGML-Player
#
# Dépend:
#   - speech_vosk.py (iter_vosk_results)
#   - lsf_context.py (make_context, build_steps_voice)
#   - lsf_play.py (play_steps)
#   - sigml_player.py (start_player)
#
# Exemple:
#   python .\cli_voice_play.py --start_player --player_exe ".\SiGML-Player.exe" --show_partial --show_plan

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from lsf_context import make_context, build_steps_voice
from lsf_play import play_steps
from sigml_player import start_player
from speech_vosk import iter_vosk_results


DEFAULT_MODEL = "voix-langue-des-signes-feature-stt-yohann/stt/model/vosk-model-small-fr-0.22"


def main() -> None:
    ap = argparse.ArgumentParser()

    # Contexte LSF / SigML
    ap.add_argument("--lex", default="LexData.xls", help="LexData.xls (TSV UTF-16)")
    ap.add_argument("--sigml_dir", default="sigml_fr", help="Dossier .sigml (renommés FR + alphabet)")
    ap.add_argument("--max_expr_len", type=int, default=6, help="Longueur max expression (tokens)")

    # Réseau / player
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8052)
    ap.add_argument("--delay_sign", type=float, default=1.15)
    ap.add_argument("--delay_letter", type=float, default=0.35)
    ap.add_argument("--start_player", action="store_true")
    ap.add_argument("--player_exe", default="SiGML-Player.exe")

    # Vosk
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Dossier du modèle Vosk")
    ap.add_argument("--samplerate", type=int, default=16000, help="Hz (recommandé: 16000)")
    ap.add_argument("--device", type=int, default=None, help="Index du micro (optionnel)")

    # Logs
    ap.add_argument("--show_partial", action="store_true")
    ap.add_argument("--show_plan", action="store_true")

    # Dédup
    ap.add_argument("--min_final_interval", type=float, default=0.35, help="Anti-spam (s) entre deux finals identiques")

    args = ap.parse_args()

    ctx = make_context(Path(args.lex), Path(args.sigml_dir))

    if args.start_player:
        start_player(Path(args.player_exe), host=args.host, port=args.port)

    model_path = Path(args.model)
    print("Listening... (Ctrl+C pour arrêter)")
    print(f"Model: {model_path.resolve()}")
    print(f"Player: {args.host}:{args.port}\n")

    last_partial = ""
    last_final = ""
    last_final_time = 0.0

    try:
        for res in iter_vosk_results(model_path, samplerate=args.samplerate, device=args.device):
            if res.kind == "partial" and args.show_partial:
                if res.text != last_partial:
                    last_partial = res.text
                    print("\rPARTIAL:", res.text[:110].ljust(110), end="")

            if res.kind != "final":
                continue

            text = (res.text or "").strip()
            if not text:
                continue

            # Nettoie la ligne PARTIAL avant d'imprimer un FINAL
            if args.show_partial:
                print("\r" + (" " * 140), end="\r")

            now = time.time()
            if text == last_final and (now - last_final_time) < args.min_final_interval:
                continue

            last_final = text
            last_final_time = now

            print("FINAL:", text)

            steps, meta, ordered_tokens = build_steps_voice(ctx, text, max_expr_len=args.max_expr_len)

            if args.show_plan:
                print("TOKENS:", ordered_tokens)
                if meta:
                    print("META:", meta)
                print("STEPS:", steps)

            play_steps(
                ctx.sigml_dir,
                steps,
                host=args.host,
                port=args.port,
                delay_sign=args.delay_sign,
                delay_letter=args.delay_letter,
            )
            print()

    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
