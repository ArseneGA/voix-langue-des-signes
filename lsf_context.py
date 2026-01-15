# lsf_context.py
# Contexte LSF: charge LexData + indexe les fichiers sigml_fr renommés en français
# et remappe automatiquement les entrées LexData vers les fichiers réellement présents.
#
# Objectifs:
# - éviter de dépendre de la colonne LexData["sigml"] si tu as renommé localement
# - jouer le fichier local correspondant à "name" (français)
# - garder une logique clean: le trie contient des LexEntry dont sigml = nom local existant si possible

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import phrase_to_sigml_sequence as seq

# spaCy est optionnel (utile surtout pour la voix). Si absent, ça marche quand même.
try:
    import spacy  # type: ignore
    _NLP = spacy.load("fr_core_news_sm")
except Exception:
    _NLP = None


# ----------------------------
# Context object
# ----------------------------

@dataclass(frozen=True)
class LSFContext:
    lex_path: Path
    sigml_dir: Path

    entries: List[seq.LexEntry]
    root: seq.TrieNode

    # vocab "token-level" (mots) issu du lexique
    lex_vocab: Set[str]

    # index "sign-level" (clé canonique -> fichier .sigml)
    sigml_index: Dict[str, Path]

    # utile pour normalisations (voix / infinitifs)
    known_vocab: Set[str]


# ----------------------------
# Utils: clés canoniques (phrase ou nom de fichier) -> "key"
# ----------------------------

def _key_from_text(text: str) -> str:
    """
    Transforme un texte (mot ou expression) en clé canonique:
      tokenize_fr + canonical_token + join("_")
    Ex:
      "à l'étranger" -> "a_l'etranger"
      "au-dessous"   -> "au_dessous"
      "bœuf"         -> "buf" (ligature normalisée par canonical_token)
    """
    toks = [seq.canonical_token(t) for t in seq.tokenize_fr(str(text))]
    toks = [t for t in toks if t]
    return "_".join(toks)


def build_sigml_index(sigml_dir: Path) -> Dict[str, Path]:
    """
    Indexe tous les .sigml du dossier local.
    Retourne: key canonique -> Path réel du fichier.
    """
    sigml_dir = Path(sigml_dir)
    idx: Dict[str, Path] = {}
    if not sigml_dir.exists():
        return idx

    for p in sigml_dir.glob("*.sigml"):
        stem = p.stem

        # Pour que "au-dessous" et "au_dessous" matchent pareil, on neutralise _ et - en espaces
        stem_norm = stem.replace("_", " ").replace("-", " ")

        key = _key_from_text(stem_norm)
        if key:
            # Si collision, on garde le premier (ou tu peux choisir une règle différente)
            idx.setdefault(key, p)

    return idx


# ----------------------------
# Cache LexData (sans dépendre du sigml_dir)
# ----------------------------

@lru_cache(maxsize=8)
def _load_lex_entries_cached(lex_path_resolved: str) -> List[seq.LexEntry]:
    """
    Charge LexData et renvoie des LexEntry (sigml = valeur brute LexData["sigml"]).
    Le remapping vers les fichiers locaux se fait ensuite dans make_context().
    """
    return seq.read_lexdata_utf16_tsv(Path(lex_path_resolved))


# ----------------------------
# Normalisations voix (optionnelles)
# ----------------------------

def drop_elided_clitics(tokens: List[str]) -> List[str]:
    drop = {"j", "d", "l", "t", "n", "m", "s", "c", "qu"}
    return [t for t in tokens if t not in drop]


def apply_small_synonyms(tokens: List[str], known: Set[str]) -> List[str]:
    syn = {
        "vais": "aller", "va": "aller", "allais": "aller", "allait": "aller",
        "étais": "etre", "était": "etre", "suis": "etre", "es": "etre",
        "sommes": "etre", "êtes": "etre",
    }
    out: List[str] = []
    for t in tokens:
        rep = syn.get(t, t)
        out.append(rep if rep in known else t)
    return out


def looks_like_infinitive(tok: str) -> bool:
    return tok.endswith(("er", "ir", "re", "oir"))


def to_infinitive_if_possible(tok: str, known: Set[str]) -> str:
    if looks_like_infinitive(tok):
        return tok
    if tok.endswith("e") and (tok + "r") in known:
        return tok + "r"          # mange -> manger
    if tok.endswith("es") and (tok[:-1] + "r") in known:
        return tok[:-1] + "r"
    if tok.endswith("ons") and (tok[:-3] + "er") in known:
        return tok[:-3] + "er"
    return tok


def force_known_infinitives(tokens: List[str], known: Set[str]) -> List[str]:
    out: List[str] = []
    for t in tokens:
        cand = to_infinitive_if_possible(t, known)
        out.append(cand if cand in known else t)
    return out


def lemmatize_with_spacy_robust(tokens: List[str], known: Set[str]) -> List[str]:
    if _NLP is None:
        return tokens
    doc = _NLP(" ".join(tokens))
    out: List[str] = []
    for w in doc:
        lemma = (w.lemma_ or "").lower()
        out.append(lemma if lemma in known else w.text.lower())
    return out


# ----------------------------
# Construction du contexte
# ----------------------------

def make_context(lex_path: Path, sigml_dir: Path) -> LSFContext:
    """
    Construit le contexte complet:
    - charge LexData
    - indexe sigml_fr (clé canonique -> fichier)
    - remappe chaque LexEntry.sigml vers le fichier local correspondant à LexEntry.name si possible
    - reconstruit le trie sur les entrées remappées
    """
    lex_path = Path(lex_path)
    sigml_dir = Path(sigml_dir)

    if not lex_path.exists():
        raise FileNotFoundError(f"LexData introuvable: {lex_path.resolve()}")
    if not sigml_dir.exists():
        raise FileNotFoundError(f"Dossier sigml introuvable: {sigml_dir.resolve()}")

    entries_raw = _load_lex_entries_cached(str(lex_path.resolve()))
    sigml_index = build_sigml_index(sigml_dir)

    # Remapping LexEntry.sigml -> fichier local (si on trouve un match sur "name")
    entries_mapped: List[seq.LexEntry] = []
    for e in entries_raw:
        key = _key_from_text(e.name)
        if key in sigml_index:
            local_filename = sigml_index[key].name  # ex: "je.sigml"
            entries_mapped.append(seq.LexEntry(name=e.name, sigml=local_filename, tokens=e.tokens))
        else:
            # fallback: on garde la valeur LexData["sigml"] (utile si tu n'as pas renommé certains fichiers)
            entries_mapped.append(e)

    root = seq.build_trie(entries_mapped)
    lex_vocab = {tok for e in entries_mapped for tok in e.tokens}

    # known_vocab contient surtout les "mots" jouables comme signes (key sans underscore aussi)
    # Ex: "manger" sera présent si manger.sigml existe
    known_vocab = set(lex_vocab) | set(sigml_index.keys())

    return LSFContext(
        lex_path=lex_path,
        sigml_dir=sigml_dir,
        entries=entries_mapped,
        root=root,
        lex_vocab=lex_vocab,
        sigml_index=sigml_index,
        known_vocab=known_vocab,
    )


# ----------------------------
# Fallback: SPELL -> SIGN si le fichier local existe
# ----------------------------

def steps_with_local_fallback(ctx: LSFContext, steps: List[seq.Step]) -> List[seq.Step]:
    """
    Remplace certains SPELL par SIGN si un fichier local correspondant existe.
    On passe par la clé canonique, donc "bœuf" / "boeuf" etc. peuvent matcher.
    """
    out: List[seq.Step] = []
    for st in steps:
        if st.kind == "SPELL":
            key = _key_from_text(st.value)
            p = ctx.sigml_index.get(key)
            if p is not None:
                out.append(seq.Step(kind="SIGN", value=p.name, raw=st.raw))
            else:
                out.append(st)
        else:
            out.append(st)
    return out


# ----------------------------
# Pipeline texte tapé
# ----------------------------

def build_steps_basic(
    ctx: LSFContext,
    text: str,
    max_expr_len: int = 6,
) -> Tuple[List[seq.Step], Dict[str, Optional[str]], List[str]]:
    """
    Pipeline "texte":
      text -> tokenize -> canonicalize -> transform_for_lsf
           -> petites normalisations (infinitif) -> segment -> local_fallback
    """
    raw_tokens = seq.tokenize_fr(text)
    tokens = [seq.canonical_token(t) for t in raw_tokens]

    ordered_tokens, meta = seq.transform_for_lsf(tokens, ctx.lex_vocab)

    # Petit bonus sans spaCy: mange -> manger si "manger" est jouable
    ordered_tokens = apply_small_synonyms([t.lower() for t in ordered_tokens], ctx.known_vocab)
    ordered_tokens = force_known_infinitives(ordered_tokens, ctx.known_vocab)

    steps = seq.segment_tokens(ctx.root, ordered_tokens, max_expr_len=max_expr_len)
    steps = steps_with_local_fallback(ctx, steps)

    return steps, meta, ordered_tokens


# ----------------------------
# Pipeline voix (optionnel)
# ----------------------------

def build_steps_voice(
    ctx: LSFContext,
    text: str,
    max_expr_len: int = 6,
) -> Tuple[List[seq.Step], Dict[str, Optional[str]], List[str]]:
    """
    Pipeline "voix" (plus agressif):
      transform_for_lsf -> clitiques -> synonymes -> lemmes -> infinitifs -> segment -> local_fallback
    """
    raw_tokens = seq.tokenize_fr(text)
    tokens = [seq.canonical_token(t) for t in raw_tokens]

    ordered_tokens, meta = seq.transform_for_lsf(tokens, ctx.lex_vocab)

    ordered_tokens = drop_elided_clitics([t.lower() for t in ordered_tokens])
    ordered_tokens = apply_small_synonyms(ordered_tokens, ctx.known_vocab)
    ordered_tokens = lemmatize_with_spacy_robust(ordered_tokens, ctx.known_vocab)
    ordered_tokens = force_known_infinitives(ordered_tokens, ctx.known_vocab)

    steps = seq.segment_tokens(ctx.root, ordered_tokens, max_expr_len=max_expr_len)
    steps = steps_with_local_fallback(ctx, steps)

    return steps, meta, ordered_tokens
