"""
sentiment_engine.py — scores headline sentiment entirely locally.
No API key, no network call.

Combines two signals:
1. VADER (lexicon-based, word-level) — general tone.
2. A finance PHRASE scanner — VADER's lexicon is keyed by single
   tokens, so multi-word market terms ("rate hike", "beats
   estimates") never match it. This scanner checks for those
   phrases directly and folds their score in.
"""
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

# Single-word finance terms VADER's default lexicon doesn't cover well.
_WORD_LEXICON = {
    "hawkish": -1.5, "dovish": 1.5, "downgrade": -2.0, "downgraded": -2.0,
    "upgrade": 2.0, "upgraded": 2.0, "layoffs": -2.0, "bankruptcy": -3.0,
    "recession": -2.5, "tariffs": -1.3, "tariff": -1.3, "sanctions": -1.5,
    "lawsuit": -1.2, "surge": 1.5, "surges": 1.5, "plunge": -2.0,
    "plunges": -2.0, "crash": -2.8, "crashes": -2.8, "rally": 1.8,
    "rallies": 1.8, "selloff": -1.8,
}
_analyzer.lexicon.update(_WORD_LEXICON)

# Multi-word phrases: score is added on top of VADER's compound
# contribution whenever the phrase is found (case-insensitive).
_PHRASE_LEXICON: dict[str, float] = {
    "rate hike": -1.8, "rate hikes": -1.8, "raises rates": -1.5,
    "rate cut": 1.5, "rate cuts": 1.5, "cuts rates": 1.5,
    "beat expectations": 2.2, "beats expectations": 2.2,
    "beat estimates": 2.2, "beats estimates": 2.2,
    "miss expectations": -2.2, "misses expectations": -2.2,
    "miss estimates": -2.2, "misses estimates": -2.2,
    "inflation surges": -1.8, "inflation rises": -1.5,
    "inflation cools": 1.5, "inflation eases": 1.5, "inflation slows": 1.5,
    "soft landing": 1.5, "hard landing": -2.0,
    "guidance cut": -2.2, "cuts guidance": -2.2, "raises guidance": 2.0,
    "dividend increase": 1.2, "dividend cut": -2.0, "dividend cuts": -2.0,
    "record high": 1.8, "record highs": 1.8, "record low": -1.8,
    "sec investigation": -1.8, "under investigation": -1.4,
    "stock split": 0.8, "share buyback": 1.0, "buyback program": 1.0,
    "ceo resigns": -1.6, "ceo steps down": -1.2, "files for bankruptcy": -3.0,
}


def score_text(text: str) -> dict:
    """
    Returns polarity scores: {'neg', 'neu', 'pos', 'compound'} where
    compound is VADER's word-level score blended with phrase hits,
    clamped to [-1, 1].
    """
    base = _analyzer.polarity_scores(text)
    lowered = text.lower()

    phrase_score = 0.0
    matched = []
    for phrase, weight in _PHRASE_LEXICON.items():
        if phrase in lowered:
            phrase_score += weight
            matched.append(phrase)

    # Normalize phrase contribution onto roughly the same scale as
    # VADER's compound (-1..1), then blend it with VADER's score,
    # weighted toward the phrase signal when phrases are present —
    # explicit finance phrases are a stronger, less noisy signal than
    # generic word-level tone for this domain.
    if matched:
        norm_phrase = max(-1.0, min(1.0, phrase_score / 2.0))
        blended = 0.35 * base["compound"] + 0.65 * norm_phrase
    else:
        blended = base["compound"]

    blended = max(-1.0, min(1.0, blended))
    return {**base, "compound": blended, "matched_phrases": matched}


def bias_label(compound: float, threshold: float = 0.25) -> str:
    if compound >= threshold:
        return "BULLISH"
    if compound <= -threshold:
        return "BEARISH"
    return "NEUTRAL"


if __name__ == "__main__":
    samples = [
        "Fed signals rate hike as inflation surges",
        "Company beats earnings expectations, raises guidance",
        "Stock plunges after CEO resigns amid investigation",
        "Central bank delivers dovish rate cut, inflation cools",
    ]
    for s in samples:
        sc = score_text(s)
        print(f"{s!r}\n  -> compound={sc['compound']:.3f} ({bias_label(sc['compound'])}) matched={sc['matched_phrases']}")
