"""Shared fuzzy-match utilities for all scrapers.

The motivating bug (Day 4): PharmEasy returned 25/25 successes for our
catalogue but quietly matched "Volini Gel" to a 5g pack variant priced
at ~₹11 instead of the 30g tube priced at ~₹170. Name-only fuzzy match
ranks both as "Volini Gel ..." with similar scores, so we need a
secondary signal.

This module adds a pack-size tiebreaker: among the top-tier name-matches
(within 0.15 of the best), prefer the candidate whose pack size matches
the target's pack size.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Callable, TypeVar

T = TypeVar("T")

# Maps raw unit tokens to a normalised form. Order matters: longer first.
_UNIT_NORMALISE = [
    (re.compile(r"\bcapsules?\b|\bcaps?\b"), "cap"),
    (re.compile(r"\btablets?\b|\btab\b|\b\d+'s\b"), "tab"),  # "15's" usually = tablets
    (re.compile(r"\bml\b"), "ml"),
    (re.compile(r"\bmg\b"), "mg"),
    (re.compile(r"\bg\b|\bgm\b|\bgrams?\b"), "g"),
    (re.compile(r"\bsachets?\b"), "sachet"),
    (re.compile(r"\bdrops?\b"), "drops"),
    (re.compile(r"\bsprays?\b"), "spray"),
]


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def extract_pack_hint(*texts: str | None) -> tuple[float, str] | None:
    """Try to extract a (quantity, unit) pair from one or more free-text
    strings. Returns the FIRST successful match across the inputs.

    Examples:
        "Tube of 30g"           -> (30.0, 'g')
        "Strip of 15 tablets"   -> (15.0, 'tab')
        "Bottle of 100ml"       -> (100.0, 'ml')
        "Dolo 650 Tablet 15's"  -> (15.0, 'tab')
        "Volini Gel 5g"         -> (5.0, 'g')

    Note: we IGNORE the milligram dose ("650mg", "500mg") since that's
    strength-per-unit, not pack size. We prefer counts and volumes.
    """
    for raw in texts:
        if not raw:
            continue
        lower = raw.lower()
        # Strip strength expressions like "650mg", "10 mg", "0.5 mg".
        cleaned = re.sub(r"\d+(?:\.\d+)?\s*mg\b", "", lower)
        # Find (number) followed by a unit token within ~12 chars.
        # Try each unit pattern in order, take first hit.
        for unit_re, normalised in _UNIT_NORMALISE:
            for num_match in re.finditer(r"(\d+(?:\.\d+)?)\s*([a-z']{1,12})", cleaned):
                num_str, unit_str = num_match.group(1), num_match.group(2)
                if unit_re.search(unit_str):
                    return (float(num_str), normalised)
    return None


def _tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def name_score(target_name: str, candidate_name: str) -> float:
    """0..1 fuzzy similarity. Two signals combined:

    1. Slug-level SequenceMatcher ratio (good when names are similar length).
    2. Token-containment bonus: fraction of the target's tokens that appear
       in the candidate's tokens. Handles the common case where the candidate
       is a longer, descriptive listing — e.g. target "Volini Gel" vs
       candidate "Volini Pain Relief Gel for Sprain, ...". SequenceMatcher
       would score that ~0.22 because of the length gap, but every target
       token IS present in the candidate, so this signal returns 1.0.

    We take the MAX so the looser signal can't penalise a tight match.
    Prefix boost (candidate starts with target) still wins outright.
    """
    t_slug = slugify(target_name)
    c_slug = slugify(candidate_name)
    if not t_slug or not c_slug:
        return 0.0

    ratio = SequenceMatcher(None, t_slug, c_slug).ratio()

    # Strong-prefix boost dominates everything.
    if c_slug.startswith(t_slug):
        return max(ratio, 0.92)

    # Token-containment signal.
    target_tokens = _tokens(target_name)
    candidate_tokens = set(_tokens(candidate_name))
    if target_tokens:
        contained = sum(1 for t in target_tokens if t in candidate_tokens)
        token_signal = contained / len(target_tokens)
        # Scale to be comparable with SequenceMatcher ratios. A perfect
        # containment match (every target token present) caps at 0.85 — high
        # enough to clear our default 0.50 threshold but lower than a true
        # prefix match.
        token_score = 0.30 + 0.55 * token_signal
        if contained < len(target_tokens):
            # Partial containment: discount.
            token_score *= (contained / len(target_tokens))
        ratio = max(ratio, token_score)

    return ratio


def pick_best(
    items: list[T],
    target_name: str,
    target_pack: str | None,
    name_of: Callable[[T], str],
    pack_text_of: Callable[[T], str] | None = None,
    threshold: float = 0.50,
    top_tier_slack: float = 0.15,
) -> tuple[T | None, float]:
    """Pick the best item for `target_name`. Among items in the top tier
    (within `top_tier_slack` of the best score), prefer one whose pack size
    matches `target_pack`.

    Args:
        items:             candidates to score.
        target_name:       the medicine name we're searching for.
        target_pack:       our seed's pack string (e.g. "Tube of 30g"). May be None.
        name_of:           callable returning the candidate's display name.
        pack_text_of:      callable returning extra text (description, tags) that
                           might also contain pack hints. May be None.
        threshold:         minimum top-score to accept a match.
        top_tier_slack:    how close to the best score a candidate must be to be
                           considered in the tiebreaker pool.

    Returns:
        (best_item_or_None, score_of_returned_item).
    """
    if not items:
        return None, 0.0

    scored = [(name_score(target_name, name_of(it)), it) for it in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    top_score = scored[0][0]
    if top_score < threshold:
        return None, top_score

    top_tier = [(s, it) for s, it in scored if s >= top_score - top_tier_slack]

    if len(top_tier) == 1 or not target_pack:
        return top_tier[0][1], top_tier[0][0]

    target_pack_info = extract_pack_hint(target_pack)
    if target_pack_info is None:
        return top_tier[0][1], top_tier[0][0]

    target_qty, target_unit = target_pack_info

    # Prefer exact-match (qty + unit). Fall back to unit-only match.
    exact_unit_qty: tuple[float, T] | None = None
    unit_only: tuple[float, T] | None = None
    for score, item in top_tier:
        texts: list[str] = [name_of(item)]
        if pack_text_of is not None:
            extra = pack_text_of(item)
            if extra:
                texts.append(extra)
        info = extract_pack_hint(*texts)
        if info is None:
            continue
        qty, unit = info
        if unit == target_unit and abs(qty - target_qty) < 0.01:
            if exact_unit_qty is None:
                exact_unit_qty = (score, item)
        elif unit == target_unit and unit_only is None:
            unit_only = (score, item)

    if exact_unit_qty:
        return exact_unit_qty[1], exact_unit_qty[0]
    if unit_only:
        return unit_only[1], unit_only[0]
    # No pack-aware winner; fall through to the highest name score.
    return top_tier[0][1], top_tier[0][0]
