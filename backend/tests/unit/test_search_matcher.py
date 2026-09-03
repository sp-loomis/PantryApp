"""
Unit tests for the fuzzy name matcher (``search.match_name``).

Pure-logic tests: no DynamoDB, no fixtures. Covers the matching rules agreed in
design — AND across terms, word-vs-word, order independence, substring vs fuzzy,
whole-word highlight spans, and the tunable threshold.
"""

from search import match_name, DEFAULT_MIN_SCORE


# ---------------------------------------------------------------------------
# Exact / substring matching
# ---------------------------------------------------------------------------

def test_exact_full_name_match_scores_one():
    result = match_name("Milk", "Milk")
    assert result is not None
    assert result["score"] == 1.0
    assert result["spans"] == [{"start": 0, "end": 4}]


def test_case_insensitive_match():
    assert match_name("Milk", "MILK") is not None


def test_substring_matches_and_highlights_whole_word():
    # "mil" is a substring of "Milk"; the *whole* word is highlighted.
    result = match_name("Milk", "mil")
    assert result is not None
    assert result["score"] == 1.0
    assert result["spans"] == [{"start": 0, "end": 4}]


# ---------------------------------------------------------------------------
# Multi-word: AND semantics + order independence
# ---------------------------------------------------------------------------

def test_multiword_and_order_independent():
    # "milk whole" must match "Whole Milk" (order independent), highlighting both.
    result = match_name("Whole Milk", "milk whole")
    assert result is not None
    assert result["score"] == 1.0
    assert result["spans"] == [{"start": 0, "end": 5}, {"start": 6, "end": 10}]


def test_and_rule_excludes_when_one_term_missing():
    # "bread" has no match in "Whole Milk", so the whole item is excluded.
    assert match_name("Whole Milk", "milk bread") is None


def test_partial_word_query_highlights_matched_words_only():
    result = match_name("Whole Milk", "who")
    assert result is not None
    assert result["spans"] == [{"start": 0, "end": 5}]


def test_duplicate_terms_dedupe_spans():
    result = match_name("Milk", "milk milk")
    assert result is not None
    assert result["spans"] == [{"start": 0, "end": 4}]


# ---------------------------------------------------------------------------
# Fuzzy / typo tolerance + threshold tuning
# ---------------------------------------------------------------------------

def test_typo_within_threshold_matches():
    # "chese" ~ "Cheese" scores well above the default threshold.
    result = match_name("Cheese", "chese")
    assert result is not None
    assert result["score"] >= DEFAULT_MIN_SCORE


def test_unrelated_query_excluded():
    assert match_name("Milk", "xylophone") is None


def test_higher_min_score_tightens_results():
    # The typo passes at the default threshold but fails a strict one.
    assert match_name("Cheese", "chese") is not None
    assert match_name("Cheese", "chese", min_score=0.99) is None


def test_lower_min_score_loosens_results():
    # A weak match excluded at the default is admitted at a permissive threshold.
    loose = match_name("Cheese", "chz", min_score=0.3)
    assert loose is not None


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------

def test_empty_query_returns_none():
    assert match_name("Milk", "") is None
    assert match_name("Milk", "   ") is None


def test_single_char_terms_are_dropped():
    # All terms too short to be usable -> no query -> no match.
    assert match_name("Milk", "a") is None
    assert match_name("Apple", "a a a") is None


def test_name_with_no_words_returns_none():
    assert match_name("!!!", "milk") is None
