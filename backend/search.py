"""
Fuzzy name matching for the Pantry App.

Pure, dependency-free logic (stdlib ``difflib``/``re`` only) so it can be unit
tested in isolation and run inside Lambda without extra packaging. Used by the
service layer's advanced search to rank items by how well their name matches a
free-text query and to surface highlight spans for the UI.

Matching rules (see the design discussion):
- The query is split into terms; **every** term must match (AND semantics), so
  "milk whole" matches "Whole Milk" but "milk bread" does not.
- Matching is **word vs word** and **order independent**: each query term is
  compared against each word of the item name. A term matches a name word when
  the term is a substring of it, or when their similarity ratio meets the
  threshold (typo tolerance).
- Highlight spans are **whole words** (character offsets into the original name),
  deduplicated and sorted, so the UI can bold the matched words in place.
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

# Default similarity threshold for a fuzzy (non-substring) word match. Tunable
# per request via the ``min_score`` search parameter.
DEFAULT_MIN_SCORE = 0.7

# Query terms shorter than this are dropped: a 1-character term matches almost
# anything and only adds noise.
MIN_TERM_LENGTH = 2

_WORD_RE = re.compile(r"\w+")


def _name_words(name: str) -> List[Tuple[str, int, int]]:
    """Split a name into (lowercased word, start, end) tuples.

    Offsets index the *original* string, so they can be used directly as
    highlight spans regardless of the name's casing.
    """
    return [(m.group().lower(), m.start(), m.end()) for m in _WORD_RE.finditer(name)]


def _query_terms(query: str) -> List[str]:
    """Split a query into usable lowercased terms (dropping too-short ones)."""
    return [t for t in query.lower().split() if len(t) >= MIN_TERM_LENGTH]


def match_name(
    name: str,
    query: str,
    min_score: float = DEFAULT_MIN_SCORE,
) -> Optional[Dict[str, Any]]:
    """Score how well ``name`` matches ``query`` and locate the matched words.

    Returns ``None`` when the query has no usable terms, the name has no words,
    or any query term fails to match a name word above ``min_score`` (AND rule).
    Otherwise returns ``{"score": float, "spans": [{"start", "end"}, ...]}`` with
    the mean per-term score and whole-word highlight spans (deduped, sorted).
    """
    terms = _query_terms(query)
    if not terms:
        return None

    words = _name_words(name)
    if not words:
        return None

    total_score = 0.0
    spans: set = set()

    for term in terms:
        best_score = 0.0
        best_span: Optional[Tuple[int, int]] = None
        for word, start, end in words:
            # An exact substring is a perfect word match; otherwise fall back to
            # fuzzy similarity for typo tolerance.
            score = 1.0 if term in word else SequenceMatcher(None, term, word).ratio()
            if score > best_score:
                best_score = score
                best_span = (start, end)

        # AND semantics: one unmatched term disqualifies the whole item.
        if best_score < min_score or best_span is None:
            return None

        total_score += best_score
        spans.add(best_span)

    ordered = sorted(spans)
    return {
        "score": round(total_score / len(terms), 4),
        "spans": [{"start": start, "end": end} for start, end in ordered],
    }
