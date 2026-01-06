# phrase_to_sigml_sequence.py
# Entrée: phrase FR
# Sortie: un "pack" texte contenant les SigML des signes dans l'ordre (sans animation),
#         i.e. le contenu du .sigml 1 puis .sigml 2 puis ...
#
# Prérequis:
# - LexData.xls (TSV UTF-16)
# - un dossier sigml_fr/ contenant TOUS les .sigml (mots + lettres), nommés par slug FR
#
# Exemple:
#   python phrase_to_sigml_sequence.py --lex LexData.xls --sigml_dir sigml_fr --text "je ne vais pas à Paris demain" --out out_sigml_sequence.txt --show_plan

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ----------------------------
# Normalisation / slug FR
# ----------------------------

def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("’", "'")
    s = re.sub(r"[^0-9a-zA-ZÀ-ÖØ-öø-ÿ' -]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize_fr(s: str) -> List[str]:
    s = normalize_text(s)
    parts: List[str] = []
    for chunk in s.split():
        for sub in chunk.split("-"):
            if "'" in sub:
                a, b = sub.split("'", 1)
                if a:
                    parts.append(a)
                if b:
                    parts.append(b)
            else:
                parts.append(sub)
    return [p for p in parts if p]

def canonical_token(t: str) -> str:
    t0 = strip_accents(t.lower())
    # contractions simples
    if t0 == "d":
        return "de"
    if t0 == "l":
        return "le"
    return t0

def slugify_fr(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("’", "'")
    s = re.sub(r"[^\w\s'-]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(" ", "_")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "inconnu"


# ----------------------------
# Lexique (LexData.xls = TSV UTF-16)
# ----------------------------

@dataclass(frozen=True)
class LexEntry:
    fr_name: str
    concept_en: str
    tokens: Tuple[str, ...]
    slug: str  # slug du fr_name

def read_lexdata_utf16_tsv(path: Path) -> List[LexEntry]:
    text = path.read_text(encoding="utf-16")
    lines = text.splitlines()
    if not lines:
        raise ValueError("LexData vide")

    header = lines[0].split("\t")
    col = {name: idx for idx, name in enumerate(header)}

    required = {"name", "concept"}
    missing = required - set(col.keys())
    if missing:
        raise ValueError(f"LexData: colonnes manquantes: {missing}")

    entries: List[LexEntry] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) <= max(col["name"], col["concept"]):
            continue

        fr_name = (parts[col["name"]] or "").strip()
        concept = (parts[col["concept"]] or "").strip()
        if not fr_name:
            continue

        toks = tuple(canonical_token(t) for t in tokenize_fr(fr_name))
        if not toks:
            continue

        entries.append(LexEntry(
            fr_name=fr_name,
            concept_en=concept,
            tokens=toks,
            slug=slugify_fr(fr_name),
        ))
    return entries


# ----------------------------
# Trie pour matching d'expressions
# ----------------------------

class TrieNode:
    __slots__ = ("children", "entries")
    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.entries: List[LexEntry] = []

def build_trie(entries: List[LexEntry]) -> TrieNode:
    root = TrieNode()
    for e in entries:
        node = root
        for tok in e.tokens:
            node = node.children.setdefault(tok, TrieNode())
        node.entries.append(e)
    return root

def possible_matches(root: TrieNode, tokens: List[str], start: int, max_len: int) -> List[Tuple[int, LexEntry]]:
    out = []
    node = root
    for j in range(start, min(len(tokens), start + max_len)):
        tok = tokens[j]
        if tok not in node.children:
            break
        node = node.children[tok]
        if node.entries:
            for e in node.entries:
                out.append((j + 1, e))
    return out


# ----------------------------
# Heuristique TEMPS / LIEU / SUJET / NEG / QUESTION
# ----------------------------

FR_STOPWORDS = {canonical_token(x) for x in {
    "le","la","les","un","une","des","du","de","d","l",
    "a","au","aux","à","dans","sur","sous","chez","pour","par","avec","sans","en",
    "et","ou","mais","donc","or","ni","car","que","qui","quoi",
    "ne","n"
}}

POSSESSIVES = {canonical_token(x) for x in {
    "mon","ma","mes","ton","ta","tes","son","sa","ses","notre","nos","votre","vos","leur","leurs"
}}

PRONOUNS_MAP = {
    "je": "moi", "j": "moi", "moi": "moi",
    "tu": "toi", "toi": "toi",
    "il": "il", "elle": "elle",
    "nous": "nous", "vous": "vous",
    "ils": "ils", "elles": "elles",
    "on": "nous",
}

QUESTION_WORDS = {"ou","quand","qui","quoi","comment","pourquoi","combien"}
NEG_WORDS = {"pas","jamais","plus","rien","personne","aucun","aucune","aucunes","aucuns"}

TIME_PHRASES = {
    ("ce","soir"),
    ("ce","matin"),
    ("cet","apres","midi"),
    ("tout","de","suite"),
    ("en","ce","moment"),
}
TIME_SINGLE = {
    "aujourdhui","demain","hier","maintenant","bientot","tard","tot",
    "lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche",
}

PLACE_PREPS = {"a","au","aux","dans","chez","sur","sous","en","vers"}

VERB_LEMMA = {
    # être
    "suis":"etre","es":"etre","est":"etre","sommes":"etre","etes":"etre","êtes":"etre","sont":"etre",
    "etais":"etre","étais":"etre","etait":"etre","était":"etre","etaient":"etre","étaient":"etre",
    "serai":"etre","seras":"etre","sera":"etre","serons":"etre","serez":"etre","seront":"etre",
    # avoir
    "ai":"avoir","as":"avoir","a":"avoir","avons":"avoir","avez":"avoir","ont":"avoir",
    "avais":"avoir","avait":"avoir","avaient":"avoir","aurai":"avoir","auras":"avoir","aura":"avoir",
    # aller
    "vais":"aller","vas":"aller","va":"aller","allons":"aller","allez":"aller","vont":"aller",
    "irai":"aller","iras":"aller","ira":"aller","irons":"aller","irez":"aller","iront":"aller",
    # faire
    "fais":"faire","fait":"faire","faisons":"faire","faites":"faire","font":"faire",
    # pouvoir / vouloir / devoir
    "peux":"pouvoir","peut":"pouvoir","pouvons":"pouvoir","pouvez":"pouvoir","peuvent":"pouvoir",
    "veux":"vouloir","veut":"vouloir","voulons":"vouloir","voulez":"vouloir","veulent":"vouloir",
    "dois":"devoir","doit":"devoir","devons":"devoir","devez":"devoir","doivent":"devoir",
}

HAVE_SPECIAL = {
    "faim":"faim",
    "soif":"soif",
    "peur":"peur",
    "froid":"froid",
    "chaud":"chaud",
}

def letters_from_token(tok: str) -> List[str]:
    t = strip_accents(tok.lower())
    t = re.sub(r"[^a-z0-9]", "", t)
    return list(t)

def transform_for_lsf(tokens: List[str], lex_vocab: set) -> Tuple[List[str], Dict[str, Optional[str]]]:
    """
    Applique la règle stable:
    TEMPS -> LIEU -> SUJET -> contenu -> NEG -> QUESTION
    + infinitif, suppression "être" copule, "mon/ma" si sujet moi/toi, etc.
    """
    tks = [canonical_token(t) for t in tokens]

    meta = {"time": None, "place": None, "subject": None, "neg": None, "q": None}

    # détecter question marker "est ce que"
    for i in range(len(tks) - 2):
        if tks[i:i+3] == ["est","ce","que"]:
            # retire ces 3 tokens
            tks = tks[:i] + tks[i+3:]
            meta["q"] = "quoi"  # fallback question
            break

    # question word
    q = None
    for w in tks:
        if w in QUESTION_WORDS:
            q = w
            break
    if q:
        meta["q"] = q
        tks = [x for x in tks if x != q]

    # négation
    neg = None
    for w in tks:
        if w in NEG_WORDS:
            neg = w
            break
    if neg:
        meta["neg"] = neg
        tks = [x for x in tks if x not in NEG_WORDS and x not in {"ne","n"}]
    else:
        tks = [x for x in tks if x not in {"ne","n"}]

    # temps (phrases)
    time_out: List[str] = []
    used = [False]*len(tks)
    for i in range(len(tks)):
        if used[i]:
            continue
        # 3-gram
        if i+2 < len(tks) and tuple(tks[i:i+3]) in TIME_PHRASES:
            time_out.extend(tks[i:i+3])
            used[i]=used[i+1]=used[i+2]=True
            continue
        # 2-gram
        if i+1 < len(tks) and tuple(tks[i:i+2]) in TIME_PHRASES:
            time_out.extend(tks[i:i+2])
            used[i]=used[i+1]=True
            continue
        # single
        if tks[i] in TIME_SINGLE:
            time_out.append(tks[i])
            used[i]=True
    tks2 = [tks[i] for i in range(len(tks)) if not used[i]]
    if time_out:
        meta["time"] = " ".join(time_out)

    # lieu (après prépositions)
    place_out: List[str] = []
    i = 0
    used = [False]*len(tks2)
    while i < len(tks2):
        if tks2[i] in PLACE_PREPS:
            # prendre jusqu'à 3 tokens suivants "porteurs"
            j = i + 1
            chunk: List[str] = []
            while j < len(tks2) and len(chunk) < 3:
                if tks2[j] in FR_STOPWORDS:
                    break
                if tks2[j] in QUESTION_WORDS or tks2[j] in NEG_WORDS:
                    break
                chunk.append(tks2[j])
                used[j] = True
                j += 1
            used[i] = True  # supprime la préposition
            if chunk:
                place_out.extend(chunk)
            i = j
        else:
            i += 1
    tks3 = [tks2[i] for i in range(len(tks2)) if not used[i]]
    if place_out:
        meta["place"] = " ".join(place_out)

    # sujet (premier pronom)
    subject = None
    for w in tks3:
        if w in PRONOUNS_MAP:
            subject = PRONOUNS_MAP[w]
            break
    if subject:
        meta["subject"] = subject
        tks3 = [w for w in tks3 if w not in PRONOUNS_MAP]  # retire pronoms du flux

    # lemmatisation verbes + règles avoir/être
    out: List[str] = []
    i = 0
    while i < len(tks3):
        w = tks3[i]

        # stopwords
        if w in FR_STOPWORDS:
            i += 1
            continue

        # possessifs: si sujet moi/toi, on les supprime
        if w in POSSESSIVES and subject in {"moi","toi"}:
            i += 1
            continue

        # verb lemma
        w2 = VERB_LEMMA.get(w, w)

        # supprimer "etre" (copule) de base
        if w2 == "etre":
            i += 1
            continue

        # gérer "avoir faim/soif/peur/froid/chaud"
        if w2 == "avoir" and i+1 < len(tks3):
            nxt = VERB_LEMMA.get(tks3[i+1], tks3[i+1])
            if nxt in HAVE_SPECIAL:
                out.append(nxt)
                i += 2
                continue

        # gérer "avoir + possessif + nom" -> posseder + nom (si possible)
        if w2 == "avoir" and i+1 < len(tks3) and tks3[i+1] in POSSESSIVES:
            poss = "posseder" if "posseder" in lex_vocab else "avoir"
            out.append(poss)
            i += 2
            continue

        # "avoir" générique -> posseder si dispo
        if w2 == "avoir":
            out.append("posseder" if "posseder" in lex_vocab else "avoir")
            i += 1
            continue

        out.append(w2)
        i += 1

    # ordre final
    ordered: List[str] = []
    ordered += time_out
    ordered += place_out
    if subject:
        ordered.append(subject)
    ordered += out
    if neg:
        ordered.append(neg)
    if q:
        ordered.append(q)

    return ordered, meta


# ----------------------------
# Segmentation DP
# ----------------------------

@dataclass
class Step:
    kind: str                 # SIGN | SPELL | SKIP
    value: str                # slug (SIGN) ou lettres/digits (SPELL) ou token (SKIP)
    raw: Optional[str] = None # fr_name (SIGN) ou token original

def segment_tokens(root: TrieNode, tokens: List[str], max_expr_len: int = 6) -> List[Step]:
    n = len(tokens)

    REWARD_PER_TOKEN = 12.0
    COST_PER_SIGN = 6.0
    COST_SPELL_LETTER = 2.0
    COST_SPELL_WORD = 10.0
    COST_SKIP_OTHER = 80.0

    dp_score = [-1e18] * (n + 1)
    dp_next: List[Optional[Tuple[int, Step]]] = [None] * (n + 1)
    dp_score[n] = 0.0

    for i in range(n - 1, -1, -1):
        # 1) expressions
        for j, entry in possible_matches(root, tokens, i, max_expr_len):
            L = j - i
            score = dp_score[j] + (REWARD_PER_TOKEN * L) - COST_PER_SIGN
            if score > dp_score[i]:
                dp_score[i] = score
                dp_next[i] = (j, Step(kind="SIGN", value=entry.slug + ".sigml", raw=entry.fr_name))

        # 2) spell fallback
        letters = letters_from_token(tokens[i])
        if letters:
            score_spell = dp_score[i + 1] - (COST_SPELL_WORD + COST_SPELL_LETTER * len(letters))
            if score_spell > dp_score[i]:
                dp_score[i] = score_spell
                dp_next[i] = (i + 1, Step(kind="SPELL", value="".join(letters), raw=tokens[i]))

        # 3) skip (très pénalisé)
        score_skip = dp_score[i + 1] - COST_SKIP_OTHER
        if score_skip > dp_score[i]:
            dp_score[i] = score_skip
            dp_next[i] = (i + 1, Step(kind="SKIP", value=tokens[i], raw=tokens[i]))

    # reconstruct
    steps: List[Step] = []
    idx = 0
    while idx < n:
        nxt = dp_next[idx]
        if not nxt:
            steps.append(Step(kind="SPELL", value="".join(letters_from_token(tokens[idx])), raw=tokens[idx]))
            idx += 1
            continue
        j, st = nxt
        steps.append(st)
        idx = j
    return steps


# ----------------------------
# Résolution locale + sortie
# ----------------------------

def resolve_local_sigml(sigml_dir: Path, filename: str) -> Path:
    """
    filename attendu: "un_peu.sigml"
    Si collisions (un_peu_2.sigml...), on prend le premier trouvé.
    """
    p = sigml_dir / filename
    if p.exists():
        return p
    stem = Path(filename).stem
    hits = sorted(sigml_dir.glob(stem + "*.sigml"))
    if hits:
        return hits[0]
    raise FileNotFoundError(f"SigML introuvable dans {sigml_dir}: {filename}")

def read_sigml_text(p: Path) -> str:
    b = p.read_bytes()
    # la plupart sont UTF-8; fallback permissif
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lex", default="LexData.xls", help="LexData.xls (TSV UTF-16)")
    ap.add_argument("--sigml_dir", default="sigml_fr", help="Dossier contenant tous les .sigml FR (mots + lettres)")
    ap.add_argument("--text", required=True, help="Phrase en français")
    ap.add_argument("--out", default="", help="Fichier de sortie (sinon stdout)")
    ap.add_argument("--show_plan", action="store_true", help="Affiche tokens transformés + plan")
    ap.add_argument("--max_expr_len", type=int, default=6)
    args = ap.parse_args()

    lex_path = Path(args.lex)
    sigml_dir = Path(args.sigml_dir)

    if not lex_path.exists():
        raise FileNotFoundError(f"Introuvable: {lex_path.resolve()}")
    if not sigml_dir.exists():
        raise FileNotFoundError(f"Dossier introuvable: {sigml_dir.resolve()}")

    entries = read_lexdata_utf16_tsv(lex_path)
    root = build_trie(entries)
    lex_vocab = set(tok for e in entries for tok in e.tokens)

    # 1) phrase -> tokens
    raw_tokens = tokenize_fr(args.text)
    tokens = [canonical_token(t) for t in raw_tokens]

    # 2) heuristique LSF (temps/lieu/sujet/neg/question + infinitif + suppression)
    ordered_tokens, meta = transform_for_lsf(tokens, lex_vocab)

    # 3) segmentation en signes (expressions longues) + spelling si inconnu
    steps = segment_tokens(root, ordered_tokens, max_expr_len=args.max_expr_len)

    if args.show_plan:
        print("META:", meta)
        print("TOKENS:", ordered_tokens)
        print("PLAN:")
        for st in steps:
            if st.kind == "SIGN":
                print(f" - SIGN  {st.value}   ({st.raw})")
            else:
                print(f" - {st.kind:5s} {st.value}   ({st.raw})")

    # 4) sortie: concat des SigML dans l'ordre (sans animation)
    out_parts: List[str] = []
    for st in steps:
        if st.kind == "SKIP":
            continue

        if st.kind == "SIGN":
            p = resolve_local_sigml(sigml_dir, st.value)
            out_parts.append(read_sigml_text(p))
            continue

        if st.kind == "SPELL":
            for ch in st.value:
                if "a" <= ch <= "z":
                    p = resolve_local_sigml(sigml_dir, f"{ch}.sigml")
                    out_parts.append(read_sigml_text(p))
                elif ch.isdigit():
                    # si tu as 0.sigml..9.sigml dans sigml_fr
                    p = resolve_local_sigml(sigml_dir, f"{ch}.sigml")
                    out_parts.append(read_sigml_text(p))
                else:
                    pass

    out_text = "\n\n".join(out_parts).strip() + "\n"

    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
    else:
        print(out_text, end="")

if __name__ == "__main__":
    main()

# python phrase_to_sigml_sequence.py --lex LexData.xls --sigml_dir sigml_fr --text "daphnee" --out sequence.txt --show_plan
