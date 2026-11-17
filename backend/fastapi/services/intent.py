import re
import unicodedata


_PATCH_RE = re.compile(r"^(?:khong|bo |loai |them |chi |it |nhieu |con |doi |tranh |tru |only |without |exclude |instead |before |after |canh sau do\b)")
_YEAR_RE = re.compile(r"(truoc|sau|tu|den|nam|before|after)\s*(?:nam\s*)?(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b")
_COUNT_RE = re.compile(
    r"(?:\btop\s*|\bchi\s+)(\d{1,3}|mot)\b"
    r"|(?<!\btap )(?<!\bmua )(?<!\bphan )(?<!\bso )"
    r"\b(\d{1,3}|mot)\s+(?:tap|canh|doan|ket qua|(?:bo )?phim|goi y)\b"
)
_LIST_HINT_RE = re.compile(
    r"(?:^|\btim\s+)(?:cac|nhung|(?:mot )?vai|nhieu)\s+(?:tap|phim|canh|doan)\b"
    r"|\b(?:liet ke|danh sach)\s+(?:(?:cac|nhung)\s+)?(?:tap|phim|canh|doan)\b"
)
_CHITCHAT_RE = re.compile(r"(?:xin chao|chao|hi|hello|cam on|thanks|ban la ai)[.!?\s]*")
_EXCLUDE_PREFIX_RE = re.compile(r"(?:khong|tranh|bo|loai|tru|without|exclude)[^,.!?;]{0,32}$")
_RECOMMEND_HINT_RE = re.compile(r"goi y|recommend")
_MOMENT_HINT_RE = re.compile(r"\b(?:canh|doan|scene|moment)\b")
_MOOD_RE = re.compile(r"\b(?:vui|buon|hai huoc|giai tri|thu gian|stress|cang thang|cheerful|funny|sad)\b")
_EXACT_EPISODE_RE = re.compile(r"\b(?:(?:tap|ep|episode|mua|phan|season)\s*#?\s*\d+|s\d+e\d+)\b")
_SERIES_COUNT_RE = re.compile(r"\b(?:bao nhieu|may|so luong)\s+(tap|mua|phan)\b")
_SERIES_OVERVIEW_RE = re.compile(r"\b(?:la (?:phim |bo phim )?gi|noi ve (?:gi|cai gi)|gioi thieu|noi dung cua)\b")
_SERIES_CHARACTERS_RE = re.compile(r"\bnhan vat chinh\b|\bnhan vat\b.*\b(?:la ai|gom ai|co ai|nhung ai)\b")

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
    current = " ".join(fold_text(query).split())
    series_info = None
    moment = bool(_MOMENT_HINT_RE.search(folded))
    exact_episode = bool(_EXACT_EPISODE_RE.search(folded))
    recommend = bool(_RECOMMEND_HINT_RE.search(folded))
    if not (moment or exact_episode or recommend):
        series_count = _SERIES_COUNT_RE.search(current)
        if series_count:
            series_info = "episodes" if series_count[1] == "tap" else "seasons"
        elif _SERIES_CHARACTERS_RE.search(current):
            series_info = "characters"
        elif _SERIES_OVERVIEW_RE.search(current):
            series_info = "summary"
    if series_info:
        constraints["series_only"] = True
    chitchat = bool(_CHITCHAT_RE.fullmatch(current))
    mood = bool(_MOOD_RE.search(folded))
    mood_discovery = mood and not (series_info or moment or exact_episode or re.search(r"\b(?:ten|tua de)\b", folded))
    mode = "chitchat" if chitchat else "recommend" if recommend or mood_discovery else "find_moment"
    count = _COUNT_RE.search(current)
    if count:
        amount = count.group(1) or count.group(2)
        requested = 1 if amount == "mot" else max(1, min(100, int(amount)))
    else:
        requested = 8 if recommend or _LIST_HINT_RE.search(current) else 1
    return {
        "intent_type": "CONVERSATIONAL_PATCH" if patch else "NO_OP" if chitchat else "DISCOVERY",
        "mode": mode,
        "scope": "series" if series_info else "scene" if moment else "episode",
        "semantic_query": semantic,
        "constraints": constraints,
        "requested_k": requested,
        "series_info": series_info,
        "include_genres": include,
        "exclude_genres": exclude,
        "mood_recommendation": mood_discovery and mode == "recommend",
        "mood_target": "sad" if re.search(r"\b(?:phim|tap|bo phim)\s+buon\b", folded) else "cheerful",
    }
