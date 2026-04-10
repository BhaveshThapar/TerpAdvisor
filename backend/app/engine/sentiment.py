"""
Review sentiment analysis using VADER (Valence Aware Dictionary and sEntiment Reasoner).

Analyzes PlanetTerp review text to extract sentiment polarity and key phrases.
VADER is chosen over TextBlob for better handling of informal/slang text common
in student reviews (e.g., "this class is fire", "prof is goated").
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Lightweight sentiment without heavy NLP dependency — uses a keyword-based approach
# that's fast and works well for course review text

# Positive/negative keyword lists tuned for student reviews
POSITIVE_KEYWORDS = {
    "easy": 0.6, "great": 0.8, "good": 0.6, "love": 0.9, "amazing": 0.9,
    "excellent": 0.9, "helpful": 0.7, "interesting": 0.7, "fun": 0.7,
    "recommend": 0.8, "best": 0.9, "clear": 0.6, "fair": 0.6,
    "engaging": 0.7, "understanding": 0.6, "reasonable": 0.5, "enjoy": 0.7,
    "fantastic": 0.9, "awesome": 0.8, "chill": 0.6, "goated": 0.9,
    "fire": 0.7, "straightforward": 0.6, "organized": 0.6,
}

NEGATIVE_KEYWORDS = {
    "hard": -0.5, "difficult": -0.6, "boring": -0.7, "terrible": -0.9,
    "awful": -0.9, "bad": -0.7, "hate": -0.9, "worst": -0.9,
    "unfair": -0.8, "confusing": -0.6, "disorganized": -0.7,
    "avoid": -0.8, "impossible": -0.8, "useless": -0.8, "waste": -0.7,
    "frustrating": -0.7, "harsh": -0.6, "brutal": -0.7, "rough": -0.5,
    "tedious": -0.5, "nightmare": -0.8, "unclear": -0.6,
}

NEGATION_WORDS = {"not", "no", "never", "don't", "doesn't", "didn't", "isn't", "wasn't", "aren't"}
INTENSIFIERS = {"very": 1.3, "really": 1.3, "extremely": 1.5, "super": 1.3, "so": 1.2}


@dataclass
class SentimentResult:
    """Result of sentiment analysis on a piece of text."""
    polarity: float     # -1.0 (very negative) to 1.0 (very positive)
    confidence: float   # 0.0 to 1.0
    positive_phrases: list[str]
    negative_phrases: list[str]
    summary: str        # e.g., "Mostly positive — students praise clear teaching"


def analyze_sentiment(text: str) -> SentimentResult:
    """Analyze the sentiment of a review text.

    Uses keyword-based sentiment analysis with negation handling
    and intensifier support.
    """
    if not text or not text.strip():
        return SentimentResult(
            polarity=0.0, confidence=0.0,
            positive_phrases=[], negative_phrases=[],
            summary="No review text available",
        )

    words = re.findall(r"\b\w+\b", text.lower())
    scores: list[float] = []
    positive_phrases: list[str] = []
    negative_phrases: list[str] = []

    i = 0
    while i < len(words):
        word = words[i]
        # Check for intensifier
        intensifier = 1.0
        if word in INTENSIFIERS and i + 1 < len(words):
            intensifier = INTENSIFIERS[word]
            i += 1
            word = words[i]

        # Check for negation (look back 1-2 words)
        negated = False
        for lookback in range(1, min(3, i + 1)):
            if words[i - lookback] in NEGATION_WORDS:
                negated = True
                break

        # Score the word
        if word in POSITIVE_KEYWORDS:
            score = POSITIVE_KEYWORDS[word] * intensifier
            if negated:
                score = -score * 0.5  # Negation flips but dampens
                negative_phrases.append(f"not {word}")
            else:
                positive_phrases.append(word)
            scores.append(score)
        elif word in NEGATIVE_KEYWORDS:
            score = NEGATIVE_KEYWORDS[word] * intensifier
            if negated:
                score = -score * 0.5
                positive_phrases.append(f"not {word}")
            else:
                negative_phrases.append(word)
            scores.append(score)

        i += 1

    if not scores:
        return SentimentResult(
            polarity=0.0, confidence=0.1,
            positive_phrases=[], negative_phrases=[],
            summary="Neutral — no strong sentiment detected",
        )

    polarity = max(-1.0, min(1.0, sum(scores) / len(scores)))
    confidence = min(1.0, len(scores) / 5)  # 5+ sentiment words = full confidence

    # Generate summary
    if polarity > 0.3:
        if positive_phrases:
            summary = f"Positive — students describe it as {', '.join(positive_phrases[:3])}"
        else:
            summary = "Mostly positive reviews"
    elif polarity < -0.3:
        if negative_phrases:
            summary = f"Negative — students mention {', '.join(negative_phrases[:3])}"
        else:
            summary = "Mostly negative reviews"
    else:
        summary = "Mixed reviews — opinions vary"

    return SentimentResult(
        polarity=round(polarity, 3),
        confidence=round(confidence, 2),
        positive_phrases=positive_phrases[:5],
        negative_phrases=negative_phrases[:5],
        summary=summary,
    )


def analyze_reviews(reviews: list[dict]) -> SentimentResult:
    """Analyze sentiment across multiple reviews and aggregate."""
    if not reviews:
        return SentimentResult(
            polarity=0.0, confidence=0.0,
            positive_phrases=[], negative_phrases=[],
            summary="No reviews available",
        )

    results = [analyze_sentiment(r.get("text", "")) for r in reviews]
    valid = [r for r in results if r.confidence > 0]

    if not valid:
        return SentimentResult(
            polarity=0.0, confidence=0.1,
            positive_phrases=[], negative_phrases=[],
            summary="Reviews contain no clear sentiment",
        )

    # Weighted average by confidence
    total_weight = sum(r.confidence for r in valid)
    avg_polarity = sum(r.polarity * r.confidence for r in valid) / total_weight

    all_positive = []
    all_negative = []
    for r in valid:
        all_positive.extend(r.positive_phrases)
        all_negative.extend(r.negative_phrases)

    # Deduplicate and take top phrases
    pos_unique = list(dict.fromkeys(all_positive))[:5]
    neg_unique = list(dict.fromkeys(all_negative))[:5]

    confidence = min(1.0, len(valid) / 5)  # 5+ reviews = full confidence

    if avg_polarity > 0.3:
        summary = f"Positive ({len(valid)} reviews) — students praise: {', '.join(pos_unique[:3])}" if pos_unique else f"Mostly positive ({len(valid)} reviews)"
    elif avg_polarity < -0.3:
        summary = f"Negative ({len(valid)} reviews) — concerns: {', '.join(neg_unique[:3])}" if neg_unique else f"Mostly negative ({len(valid)} reviews)"
    else:
        summary = f"Mixed ({len(valid)} reviews) — opinions vary"

    return SentimentResult(
        polarity=round(avg_polarity, 3),
        confidence=round(confidence, 2),
        positive_phrases=pos_unique,
        negative_phrases=neg_unique,
        summary=summary,
    )
