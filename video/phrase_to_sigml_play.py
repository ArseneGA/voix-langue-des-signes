# phrase_to_sigml_play.py
# Utilise phrase_to_sigml_sequence.py pour construire la séquence de signes,
# puis envoie chaque SigML au SIGML-Player via TCP (par défaut 127.0.0.1:8052).
#
# Prérequis:
# - phrase_to_sigml_sequence.py dans le même dossier
# - LexData.xls
# - sigml_fr/ (mots + lettres) avec tes .sigml locaux
# - SIGML-Player.exe lancé (optionnellement auto-start via --start_player)
#
# Exemples:
#   python phrase_to_sigml_play.py --lex LexData.xls --sigml_dir sigml_fr --text "je ne vais pas à Paris demain" --show_plan
#   python phrase_to_sigml_play.py --lex LexData.xls --sigml_dir sigml_fr --text "bonjour" --start_player --player_exe "C:\...\SIGML-Player.exe"

import argparse
import socket
import subprocess
import time
from pathlib import Path
from typing import List, Optional

import phrase_to_sigml_sequence as seq  # <-- réutilise TON code


def send_to_sigml_player(sigml_xml: bytes, host: str = "127.0.0.1", port: int = 8052, timeout: float = 5.0):
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(sigml_xml)


def can_connect(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def maybe_start_player(player_exe: Optional[str], host: str, port: int, wait_s: float = 8.0) -> None:
    if not player_exe:
        raise RuntimeError(
            "Impossible de se connecter au SIGML-Player. "
            "Lance SIGML-Player.exe, ou utilise --start_player --player_exe <chemin>."
        )

    exe_path = Path(player_exe)
    if not exe_path.exists():
        raise FileNotFoundError(f"SIGML-Player.exe introuvable: {exe_path.resolve()}")

    subprocess.Popen([str(exe_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # attendre que le port écoute
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if can_connect(host, port, timeout=0.5):
            return
        time.sleep(0.25)

    raise RuntimeError(
        f"SIGML-Player lancé mais port {host}:{port} injoignable après {wait_s:.1f}s. "
        "Vérifie la config du player (port) et le pare-feu."
    )


def build_steps(
    lex_path: Path,
    sigml_dir: Path,
    text: str,
    max_expr_len: int,
):
    entries = seq.read_lexdata_utf16_tsv(lex_path)
    root = seq.build_trie(entries)
    lex_vocab = set(tok for e in entries for tok in e.tokens)

    raw_tokens = seq.tokenize_fr(text)
    tokens = [seq.canonical_token(t) for t in raw_tokens]

    ordered_tokens, meta = seq.transform_for_lsf(tokens, lex_vocab)
    steps = seq.segment_tokens(root, ordered_tokens, max_expr_len=max_expr_len)

    return steps, meta, ordered_tokens


def step_to_sigml_blobs(sigml_dir: Path, steps: List[seq.Step]) -> List[bytes]:
    blobs: List[bytes] = []
    for st in steps:
        if st.kind == "SKIP":
            continue

        if st.kind == "SIGN":
            p = seq.resolve_local_sigml(sigml_dir, st.value)  # ex: "un_peu.sigml"
            blobs.append(p.read_bytes())
            continue

        if st.kind == "SPELL":
            for ch in st.value:
                if "a" <= ch <= "z":
                    p = seq.resolve_local_sigml(sigml_dir, f"{ch}.sigml")
                    blobs.append(p.read_bytes())
                elif ch.isdigit():
                    p = seq.resolve_local_sigml(sigml_dir, f"{ch}.sigml")
                    blobs.append(p.read_bytes())
                else:
                    pass
    return blobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lex", default="LexData.xls", help="LexData.xls (TSV UTF-16)")
    ap.add_argument("--sigml_dir", default="sigml_fr", help="Dossier contenant tous les .sigml FR")
    ap.add_argument("--text", required=True, help="Phrase en français")
    ap.add_argument("--host", default="127.0.0.1", help="Host SIGML-Player")
    ap.add_argument("--port", type=int, default=8052, help="Port SIGML-Player")
    ap.add_argument("--delay_sign", type=float, default=1.15, help="Pause entre signes")
    ap.add_argument("--delay_letter", type=float, default=0.35, help="Pause entre lettres")
    ap.add_argument("--max_expr_len", type=int, default=6, help="Longueur max des expressions")
    ap.add_argument("--show_plan", action="store_true", help="Affiche tokens et plan")
    ap.add_argument("--start_player", action="store_true", help="Tente de lancer SIGML-Player.exe si pas connecté")
    ap.add_argument("--player_exe", default="", help="Chemin vers SIGML-Player.exe (si --start_player)")
    args = ap.parse_args()

    lex_path = Path(args.lex)
    sigml_dir = Path(args.sigml_dir)

    if not lex_path.exists():
        raise FileNotFoundError(f"Introuvable: {lex_path.resolve()}")
    if not sigml_dir.exists():
        raise FileNotFoundError(f"Dossier introuvable: {sigml_dir.resolve()}")

    steps, meta, ordered_tokens = build_steps(
        lex_path=lex_path,
        sigml_dir=sigml_dir,
        text=args.text,
        max_expr_len=args.max_expr_len,
    )

    if args.show_plan:
        print("META:", meta)
        print("TOKENS:", ordered_tokens)
        print("PLAN:")
        for st in steps:
            if st.kind == "SIGN":
                print(f" - SIGN  {st.value}   ({st.raw})")
            else:
                print(f" - {st.kind:5s} {st.value}   ({st.raw})")

    # connexion SIGML-Player (auto-start optionnel)
    if not can_connect(args.host, args.port, timeout=0.5):
        if args.start_player:
            maybe_start_player(args.player_exe or None, args.host, args.port)
        else:
            raise RuntimeError(
                f"SIGML-Player injoignable sur {args.host}:{args.port}. "
                "Lance SIGML-Player.exe, ou ajoute --start_player --player_exe <chemin>."
            )

    # construire blobs SigML puis envoyer un par un
    blobs = step_to_sigml_blobs(sigml_dir, steps)

    for st in steps:
        if st.kind == "SKIP":
            continue

        if st.kind == "SIGN":
            p = seq.resolve_local_sigml(sigml_dir, st.value)
            send_to_sigml_player(p.read_bytes(), host=args.host, port=args.port)
            time.sleep(args.delay_sign)
            continue

        if st.kind == "SPELL":
            for ch in st.value:
                if "a" <= ch <= "z":
                    p = seq.resolve_local_sigml(sigml_dir, f"{ch}.sigml")
                    send_to_sigml_player(p.read_bytes(), host=args.host, port=args.port)
                    time.sleep(args.delay_letter)
                elif ch.isdigit():
                    p = seq.resolve_local_sigml(sigml_dir, f"{ch}.sigml")
                    send_to_sigml_player(p.read_bytes(), host=args.host, port=args.port)
                    time.sleep(args.delay_letter)

    print(f"[OK] {len(blobs)} envois SigML effectués.")


if __name__ == "__main__":
    main()

#python phrase_to_sigml_play.py --lex LexData.xls --sigml_dir sigml_fr --text "bonjour" --start_player --player_exe "C:\Users\arsen\Desktop\10_Projets\Au513\video\SiGML-Player.exe"

