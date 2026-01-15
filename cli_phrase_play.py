# cli_phrase_play.py
# Texte FR -> Steps (LSF) -> envoi au SiGML-Player via TCP.
#
# Dépend:
#   - lsf_context.py (make_context, build_steps_basic)
#   - lsf_play.py (play_steps)
#   - sigml_player.py (start_player)
#
# Exemple:
#   python cli_phrase_play.py --text "je ne vais pas à Paris demain" --show_plan --start_player --player_exe "SiGML-Player.exe"

from __future__ import annotations

import argparse
from pathlib import Path

from lsf_context import build_steps_basic, make_context
from lsf_play import play_steps
from sigml_player import start_player


def main() -> None:
    ap = argparse.ArgumentParser()

    ap.add_argument("--lex", default="LexData.xls", help="LexData.xls (TSV UTF-16)")
    ap.add_argument("--sigml_dir", default="sigml_fr", help="Dossier .sigml")
    ap.add_argument("--text", required=True, help="Phrase FR")

    ap.add_argument("--max_expr_len", type=int, default=6, help="Longueur max expression (tokens)")

    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8052)

    ap.add_argument("--delay_sign", type=float, default=1.15)
    ap.add_argument("--delay_letter", type=float, default=0.35)

    ap.add_argument("--start_player", action="store_true")
    ap.add_argument("--player_exe", default="SiGML-Player.exe")

    ap.add_argument("--show_plan", action="store_true")
    args = ap.parse_args()

    ctx = make_context(Path(args.lex), Path(args.sigml_dir))

    if args.start_player:
        start_player(Path(args.player_exe), host=args.host, port=args.port)

    steps, meta, ordered_tokens = build_steps_basic(ctx, args.text, max_expr_len=args.max_expr_len)

    if args.show_plan:
        print("TEXT:", args.text)
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


if __name__ == "__main__":
    main()
