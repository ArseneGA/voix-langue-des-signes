# voice_to_sigml_player.py
# Pipeline complet:
# Micro -> Vosk (FR) -> phrase -> phrase_to_sigml_sequence.py (LSF ordering + segmentation)
# -> lemmatisation verbes (spaCy) + mapping pronoms -> validation vocab (LexData + sigml_fr)
# -> envoi au SiGML-Player.exe via TCP (127.0.0.1:8052)
#
# Prérequis:
#   pip install vosk sounddevice spacy
#   python -m spacy download fr_core_news_sm
#
# Dossier (dans ton dossier "video"):
#   - LexData.xls
#   - sigml_fr/
#   - phrase_to_sigml_sequence.py
#   - SiGML-Player.exe (à lancer manuellement, ou --start_player)
#
# Usage:
#   python voice_to_sigml_player.py --start_player --show_plan
#   python voice_to_sigml_player.py --min_words 2

import argparse
import json
import queue
import socket
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Set

from vosk import Model, KaldiRecognizer
import sounddevice as sd

import spacy
import phrase_to_sigml_sequence as seq  # réutilise ton fichier

# ---- spaCy ----
# NOTE: nécessite "python -m spacy download fr_core_news_sm"
NLP = spacy.load("fr_core_news_sm")

# --- chemins par défaut (ton arborescence) ---
DEFAULT_MODEL = "voix-langue-des-signes-feature-stt-yohann/stt/model/vosk-model-small-fr-0.22"
DEFAULT_LEX = "LexData.xls"
DEFAULT_SIGML_DIR = "sigml_fr"
DEFAULT_PLAYER_EXE = "SiGML-Player.exe"


# ----------------------------
# SiGML Player (TCP)
# ----------------------------

def send_to_sigml_player(sigml_xml: bytes, host: str, port: int, timeout: float = 5.0) -> None:
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(sigml_xml)

def can_connect(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def maybe_start_player(player_exe: Path, host: str, port: int, wait_s: float = 8.0) -> None:
    if not player_exe.exists():
        raise FileNotFoundError(f"SiGML-Player.exe introuvable: {player_exe.resolve()}")

    subprocess.Popen([str(player_exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    t0 = time.time()
    while time.time() - t0 < wait_s:
        if can_connect(host, port, timeout=0.5):
            return
        time.sleep(0.25)

    raise RuntimeError(
        f"SiGML-Player lancé mais {host}:{port} injoignable après {wait_s:.1f}s. "
        "Vérifie le port du player et le pare-feu."
    )


# ----------------------------
# Vocab local (sigml_fr)
# ----------------------------

def build_sigml_vocab(sigml_dir: Path) -> Set[str]:
    # ex: "paris.sigml" -> "paris"
    return {p.stem.lower() for p in sigml_dir.glob("*.sigml")}


# ----------------------------
# Normalisation tokens post-LSF
# ----------------------------

def lemmatize_verbs_with_spacy(tokens: List[str], known: Set[str]) -> List[str]:
    """
    - Analyse la séquence tokenisée (déjà ordonnée façon LSF)
    - Remplace VERB/AUX par lemma SI lemma est connu (LexData ou sigml_fr)
    """
    if not tokens:
        return tokens

    doc = NLP(" ".join(tokens))
    out: List[str] = []
    for t in doc:
        tok = (t.text or "").lower()
        if t.pos_ in ("VERB", "AUX"):
            lemma = (t.lemma_ or tok).lower()
            out.append(lemma if lemma in known else tok)
        else:
            out.append(tok)
    return out

def apply_small_synonyms(tokens: List[str], known: Set[str]) -> List[str]:
    """
    Mini mapping utile (facultatif).
    Ne remplace que si la cible existe.
    """
    mapping = {
        "salut": ["bonjour"],
    }
    out: List[str] = []
    for t in tokens:
        if t in mapping:
            replaced = False
            for cand in mapping[t]:
                if cand in known:
                    out.append(cand)
                    replaced = True
                    break
            if not replaced:
                out.append(t)
        else:
            out.append(t)
    return out

def normalize_pronouns(tokens: List[str], known: Set[str]) -> List[str]:
    """
    Fix: si 'moi' est absent mais 'je' existe, utilise 'je' (et idem toi/tu).
    (Ton lexique/tes sigml peuvent avoir un seul des deux.)
    """
    out: List[str] = []
    for t in tokens:
        if t == "moi" and ("moi" not in known) and ("je" in known):
            out.append("je")
        elif t == "toi" and ("toi" not in known) and ("tu" in known):
            out.append("tu")
        else:
            out.append(t)
    return out


# ----------------------------
# Build plan (phrase -> steps)
# ----------------------------

def build_steps(lex_path: Path, sigml_dir: Path, text: str, max_expr_len: int):
    # LexData
    entries = seq.read_lexdata_utf16_tsv(lex_path)
    root = seq.build_trie(entries)
    lex_vocab = {tok for e in entries for tok in e.tokens}

    # Vocab fichiers locaux
    sigml_vocab = build_sigml_vocab(sigml_dir)
    known = lex_vocab | sigml_vocab

    # Tokenisation phrase brute
    raw_tokens = seq.tokenize_fr(text)
    tokens = [seq.canonical_token(t) for t in raw_tokens]

    # Ordonnancement LSF + heuristiques (temps/lieu/sujet/neg/question, etc.)
    ordered_tokens, meta = seq.transform_for_lsf(tokens, lex_vocab)

    # Normalisation: synonymes (salut->bonjour), pronoms (moi->je), verbes -> infinitif (spaCy)
    ordered_tokens = apply_small_synonyms([t.lower() for t in ordered_tokens], known)
    ordered_tokens = normalize_pronouns(ordered_tokens, known)
    ordered_tokens = lemmatize_verbs_with_spacy(ordered_tokens, known)

    # Segmentation en signes / spelling
    steps = seq.segment_tokens(root, ordered_tokens, max_expr_len=max_expr_len)

    return steps, meta, ordered_tokens


# ----------------------------
# Lecture / animation
# ----------------------------

def play_steps(
    sigml_dir: Path,
    steps: List[seq.Step],
    host: str,
    port: int,
    delay_sign: float,
    delay_letter: float,
) -> None:
    for st in steps:
        if st.kind == "SKIP":
            continue

        if st.kind == "SIGN":
            p = seq.resolve_local_sigml(sigml_dir, st.value)
            send_to_sigml_player(p.read_bytes(), host, port)
            time.sleep(delay_sign)
            continue

        if st.kind == "SPELL":
            for ch in st.value:
                if "a" <= ch <= "z":
                    p = seq.resolve_local_sigml(sigml_dir, f"{ch}.sigml")
                    send_to_sigml_player(p.read_bytes(), host, port)
                    time.sleep(delay_letter)
                elif ch.isdigit():
                    p = seq.resolve_local_sigml(sigml_dir, f"{ch}.sigml")
                    send_to_sigml_player(p.read_bytes(), host, port)
                    time.sleep(delay_letter)


# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Dossier modèle Vosk")
    ap.add_argument("--samplerate", type=int, default=16000)
    ap.add_argument("--device", type=int, default=None)

    ap.add_argument("--lex", default=DEFAULT_LEX)
    ap.add_argument("--sigml_dir", default=DEFAULT_SIGML_DIR)
    ap.add_argument("--max_expr_len", type=int, default=6)

    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8052)
    ap.add_argument("--delay_sign", type=float, default=1.15)
    ap.add_argument("--delay_letter", type=float, default=0.35)

    ap.add_argument("--start_player", action="store_true")
    ap.add_argument("--player_exe", default=DEFAULT_PLAYER_EXE)

    ap.add_argument("--show_partial", action="store_true")
    ap.add_argument("--show_plan", action="store_true")

    ap.add_argument("--min_words", type=int, default=1, help="Ignore les phrases finales trop courtes")
    ap.add_argument("--cooldown", type=float, default=0.8, help="Temps min entre 2 phrases (anti-spam)")

    args = ap.parse_args()

    model_path = Path(args.model)
    lex_path = Path(args.lex)
    sigml_dir = Path(args.sigml_dir)
    player_exe = Path(args.player_exe)

    if not model_path.exists():
        raise FileNotFoundError(f"Modèle Vosk introuvable: {model_path.resolve()}")
    if not lex_path.exists():
        raise FileNotFoundError(f"LexData introuvable: {lex_path.resolve()}")
    if not sigml_dir.exists():
        raise FileNotFoundError(f"Dossier sigml_fr introuvable: {sigml_dir.resolve()}")

    # Player
    if not can_connect(args.host, args.port, timeout=0.5):
        if args.start_player:
            maybe_start_player(player_exe, args.host, args.port)
        else:
            raise RuntimeError(
                f"SiGML-Player injoignable sur {args.host}:{args.port}. "
                f"Lance SiGML-Player.exe (ou --start_player --player_exe \"{player_exe}\")."
            )

    # Vosk
    model = Model(str(model_path))
    rec = KaldiRecognizer(model, args.samplerate)
    rec.SetWords(False)

    q: "queue.Queue[bytes]" = queue.Queue()

    def callback(indata, frames, time_info, status):
        q.put(bytes(indata))

    print("Listening... (Ctrl+C pour arrêter)")
    print(f"Model:  {model_path.resolve()}")
    print(f"Lex:    {lex_path.resolve()}")
    print(f"SigML:  {sigml_dir.resolve()}")
    print(f"Player: {args.host}:{args.port}\n")

    last_final_t = 0.0

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
                    if not text:
                        continue

                    if len(text.split()) < args.min_words:
                        continue

                    now = time.time()
                    if now - last_final_t < args.cooldown:
                        continue
                    last_final_t = now

                    print(f"\nFINAL: {text}")

                    steps, meta, ordered_tokens = build_steps(lex_path, sigml_dir, text, args.max_expr_len)

                    if args.show_plan:
                        print("META:", meta)
                        print("TOKENS:", ordered_tokens)
                        print("PLAN:")
                        for st in steps:
                            if st.kind == "SIGN":
                                print(f" - SIGN  {st.value}   ({st.raw})")
                            else:
                                print(f" - {st.kind:5s} {st.value}   ({st.raw})")

                    play_steps(sigml_dir, steps, args.host, args.port, args.delay_sign, args.delay_letter)

                else:
                    if args.show_partial:
                        res = json.loads(rec.PartialResult())
                        partial = (res.get("partial") or "").strip()
                        if partial:
                            print(f"PARTIAL: {partial}")

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
