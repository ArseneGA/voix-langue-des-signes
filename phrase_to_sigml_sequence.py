# phrase_to_sigml_sequence.py
# Entrée: phrase FR
# Sortie: une séquence (plan) de signes (fichiers .sigml) + épellation si inconnu
#
# Exemples:
#   python phrase_to_sigml_sequence.py --lex LexData.xls --sigml_dir sigml_fr --text "je ne vais pas à Paris demain" --out sequence.txt --show_plan
#   python phrase_to_sigml_sequence.py --lex LexData.xls --sigml_dir sigml_fr --text "daphnee" --out sequence.txt --show_plan

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd


# ----------------------------
# Data structures
# ----------------------------

@dataclass(frozen=True)
class LexEntry:
    name: str
    sigml: str
    tokens: Tuple[str, ...]  # canonical tokens


@dataclass
class TrieNode:
    children: Dict[str, "TrieNode"]
    value: Optional[LexEntry] = None

    def __init__(self):
        self.children = {}
        self.value = None


@dataclass(frozen=True)
class Step:
    kind: str   # "SIGN" | "SPELL" | "SKIP"
    value: str  # for SIGN: filename.sigml ; for SPELL: token string
    raw: str = ""


# ----------------------------
# IO: LexData
# ----------------------------

def read_lexdata_utf16_tsv(lex_path: Path) -> List[LexEntry]:
    """
    Lit LexData.xls (souvent un TSV encodé UTF-16) et retourne des entrées tokenisées.
    Colonnes attendues: name, sigml (minimum).
    """
    lex_path = Path(lex_path)
    if not lex_path.exists():
        raise FileNotFoundError(f"LexData introuvable: {lex_path.resolve()}")

    # LexData.xls est souvent un TSV UTF-16 (malgré l'extension .xls)
    try:
        df = pd.read_csv(lex_path, sep="\t", encoding="utf-16")
    except Exception:
        # fallback: parfois UTF-8 tab
        df = pd.read_csv(lex_path, sep="\t", encoding="utf-8")

    for col in ("name", "sigml"):
        if col not in df.columns:
            raise ValueError(f"Colonne '{col}' manquante dans LexData: colonnes={list(df.columns)}")

    entries: List[LexEntry] = []
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        sigml = str(row["sigml"]).strip()
        if not name or not sigml or sigml.lower() == "nan":
            continue
        toks = tuple(canonical_token(t) for t in tokenize_fr(name))
        toks = tuple(t for t in toks if t)  # drop empty
        if not toks:
            continue
        entries.append(LexEntry(name=name, sigml=sigml, tokens=toks))

    return entries


# ----------------------------
# Tokenization / normalization
# ----------------------------

_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+(?:'[A-Za-zÀ-ÖØ-öø-ÿ0-9]+)?", re.UNICODE)

def tokenize_fr(text: str) -> List[str]:
    """
    Tokenizer simple FR: récupère les mots / nombres et garde les apostrophes internes.
    """
    if not text:
        return []
    return _WORD_RE.findall(text)


def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def canonical_token(tok: str) -> str:
    """
    Canonicalisation pour matching:
      - minuscule
      - retire accents
      - garde apostrophes mais normalise
    """
    tok = tok.strip().lower()
    tok = tok.replace("’", "'")
    tok = strip_accents(tok)
    tok = re.sub(r"[^a-z0-9']+", "", tok)
    return tok


# ----------------------------
# Trie build / match
# ----------------------------

def build_trie(entries: List[LexEntry]) -> TrieNode:
    """
    Construit un trie sur tokens -> LexEntry (permet match d'expressions multi-mots).
    """
    root = TrieNode()
    for e in entries:
        node = root
        for t in e.tokens:
            node = node.children.setdefault(t, TrieNode())
        node.value = e
    return root


# ----------------------------
# LSF transforms (re-order / negation / etc.)
# ----------------------------

_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l",
    "a", "au", "aux", "ce", "cet", "cette", "ces",
    "et", "ou", "mais",
    "que", "qui", "quoi", "dont",
    "en", "y",
}

def transform_for_lsf(tokens: List[str], lex_vocab: Set[str]) -> Tuple[List[str], Dict[str, Optional[str]]]:
    """
    Transformations simples:
      - gère 'ne ... pas' -> ajoute un marqueur NEG si connu
      - supprime certains stopwords
    Retourne (ordered_tokens, meta)
    """
    meta: Dict[str, Optional[str]] = {}

    toks = [t for t in tokens if t]
    toks = [t.lower() for t in toks]

    # Négation: détecter "ne ... pas"
    # On supprime "ne" et on conserve "pas" comme négation si le vocab le permet.
    # (à adapter selon ton LexData: parfois "pas" ou "ne_pas" etc)
    out: List[str] = []
    has_ne = False
    for t in toks:
        if t == "ne":
            has_ne = True
            continue
        if has_ne and t == "pas":
            meta["negation"] = "ne...pas"
            if "pas" in lex_vocab:
                out.append("pas")
            has_ne = False
            continue
        out.append(t)

    # Remove stopwords (sauf si le mot est dans le lexique)
    filtered: List[str] = []
    for t in out:
        if t in _STOPWORDS and t not in lex_vocab:
            continue
        filtered.append(t)

    return filtered, meta


# ----------------------------
# Segmentation (tokens -> Steps)
# ----------------------------

def segment_tokens(root: TrieNode, tokens: List[str], max_expr_len: int = 6) -> List[Step]:
    """
    Segmente en Steps via "longest match" (jusqu'à max_expr_len).
    - si expression trouvée: SIGN(<sigml>)
    - sinon: SPELL(<token>)
    """
    steps: List[Step] = []
    i = 0
    n = len(tokens)

    while i < n:
        best_entry: Optional[LexEntry] = None
        best_len = 0

        # Cherche le plus long match à partir de i
        node = root
        for L in range(1, max_expr_len + 1):
            if i + L > n:
                break
            t = tokens[i + L - 1]
            if t not in node.children:
                break
            node = node.children[t]
            if node.value is not None:
                best_entry = node.value
                best_len = L

        if best_entry is not None and best_len > 0:
            steps.append(Step(kind="SIGN", value=best_entry.sigml, raw=" ".join(tokens[i:i+best_len])))
            i += best_len
        else:
            tok = tokens[i]
            if tok:
                steps.append(Step(kind="SPELL", value=tok, raw=tok))
            else:
                steps.append(Step(kind="SKIP", value="", raw=""))
            i += 1

    return steps


def resolve_local_sigml(sigml_dir: Path, filename: str) -> Path:
    """
    Résout un fichier .sigml dans le dossier local (sigml_fr).
    """
    sigml_dir = Path(sigml_dir)
    p = sigml_dir / filename
    if not p.exists():
        raise FileNotFoundError(f"SigML introuvable: {p.resolve()}")
    return p


# ----------------------------
# CLI
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lex", default="LexData.xls", help="LexData (TSV UTF-16 malgré l'extension .xls)")
    ap.add_argument("--sigml_dir", default="sigml_fr", help="Dossier des .sigml (mots + alphabet)")
    ap.add_argument("--text", required=True, help="Phrase FR à convertir")
    ap.add_argument("--out", default="sequence.txt", help="Fichier sortie (plan Steps)")
    ap.add_argument("--max_expr_len", type=int, default=6, help="Longueur max d'une expression (en tokens)")
    ap.add_argument("--show_plan", action="store_true", help="Affiche le plan dans le terminal")

    args = ap.parse_args()

    lex_path = Path(args.lex)
    sigml_dir = Path(args.sigml_dir)

    entries = read_lexdata_utf16_tsv(lex_path)
    root = build_trie(entries)
    lex_vocab = {tok for e in entries for tok in e.tokens}

    raw_tokens = tokenize_fr(args.text)
    tokens = [canonical_token(t) for t in raw_tokens]
    ordered_tokens, meta = transform_for_lsf(tokens, lex_vocab)

    steps = segment_tokens(root, ordered_tokens, max_expr_len=args.max_expr_len)

    # Write plan
    lines: List[str] = []
    lines.append(f"TEXT: {args.text}")
    lines.append(f"TOKENS: {ordered_tokens}")
    if meta:
        lines.append(f"META: {meta}")
    lines.append("STEPS:")
    for st in steps:
        lines.append(f" - {st.kind}\t{st.value}\t(raw={st.raw})")

    Path(args.out).write_text("\n".join(lines), encoding="utf-8")

    if args.show_plan:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
