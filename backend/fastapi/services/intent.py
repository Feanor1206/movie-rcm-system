import re
import unicodedata


_PATCH_RE = re.compile(r"^(?:khong|bo |loai |them |chi |it |nhieu |con |doi |tranh |tru |only |without |exclude |instead |before |after |canh sau do\b)")
_YEAR_RE = re.compile(r"(truoc|sau|tu|den|nam|before|after)\s*(?:nam\s*)?(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b")
_COUNT_RE = re.compile(r"(?:\btop\s*|\bchi\s+)(\d{1,3})\b|\b(\d{1,3})\s+(?:ket qua|phim|goi y)\b")
_CHITCHAT_RE = re.compile(r"(?:xin chao|chao|hi|hello|cam on|thanks|ban la ai)[.!?\s]*")
_EXCLUDE_PREFIX_RE = re.compile(r"(?:khong|tranh|bo|loai|tru|without|exclude)[^,.!?;]{0,32}$")
_RECOMMEND_HINT_RE = re.compile(r"goi y|recommend")
_MOMENT_HINT_RE = re.compile(r"\b(?:canh|doan|scene|moment)\b")

GENRE_ALIASES = {
    "animation": ["hoat hinh", "animation", "cartoon"],
    "comedy": ["hai huoc", "phim hai", "comedy"],
    "horror": ["kinh di", "horror"],
    "sci-fi": ["vien tuong", "sci-fi", "science fiction"],
    "family": ["gia dinh", "family"],
    "adventure": ["phieu luu", "adventure"],
    "romance": ["lang man", "romance"],
    "action": ["hanh dong", "action"],
    "drama": ["chinh kich", "drama"],
}
GENRE_PATTERNS = {
    genre: re.compile("|".join(re.escape(alias) for alias in aliases))
    for genre, aliases in GENRE_ALIASES.items()
}


def fold_text(text):
    return "".join(char for char in unicodedata.normalize("NFD", text.casefold().replace("đ", "d")) if unicodedata.category(char) != "Mn")


def _is_patch(query):
    return bool(_PATCH_RE.match(fold_text(query).strip()))


def deterministic_intent(query, history=None):
    previous = []
    for message in history or []:
        content = message.get("content") or message.get("text") or ""
        if message.get("role") == "user" and isinstance(content, str) and content.strip() and content.strip() != query.strip():
            if not _is_patch(content):
                previous = []
            previous.append(content)
    patch = bool(previous and _is_patch(query))
    semantic = " ".join(previous + [query]) if patch else query
    folded = fold_text(semantic)
    constraints = {}
    include, exclude = [], []
    for genre, pattern in GENRE_PATTERNS.items():
        matches = list(pattern.finditer(folded))
        if not matches:
            continue
        if any(_EXCLUDE_PREFIX_RE.search(folded[max(0, match.start() - 40):match.start()]) for match in matches):
            exclude.append(genre)
        else:
            include.append(genre)
    if include:
        constraints["include_genres"] = include
    if exclude:
        constraints["exclude_genres"] = exclude
    for match in _YEAR_RE.finditer(folded):
        relation, year_text = match.groups()
        year = int(year_text)
        if relation in {"truoc", "before"}:
            constraints["year_max"] = year - 1
        elif relation in {"sau", "after"}:
            constraints["year_min"] = year + 1
        elif relation == "tu":
            constraints["year_min"] = year
        elif relation == "den":
            constraints["year_max"] = year
        else:
            constraints["year_min"] = constraints["year_max"] = year
    count = _COUNT_RE.search(fold_text(query))
    requested = max(1, min(100, int(count.group(1) or count.group(2)))) if count else 8
    chitchat = bool(_CHITCHAT_RE.fullmatch(fold_text(query).strip()))
    mode = "chitchat" if chitchat else "recommend" if _RECOMMEND_HINT_RE.search(folded) else "find_moment"
    return {
        "intent_type": "CONVERSATIONAL_PATCH" if patch else "NO_OP" if chitchat else "DISCOVERY",
        "mode": mode,
        "scope": "scene" if _MOMENT_HINT_RE.search(folded) else "episode",
        "semantic_query": semantic,
        "constraints": constraints,
        "requested_k": requested,
        "include_genres": include,
        "exclude_genres": exclude,
    }
