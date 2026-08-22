from __future__ import annotations

import re
from datetime import datetime, timezone

POSITIVE = {"beat", "beats", "growth", "surge", "rally", "record", "approval", "approved", "upgrade", "bullish", "gain", "gains", "strong", "optimism", "partnership", "adoption", "easing", "cut", "cuts", "stimulus", "profit", "profits", "expands", "breakthrough"}
NEGATIVE = {"miss", "misses", "drop", "falls", "fall", "crash", "downgrade", "bearish", "loss", "losses", "weak", "ban", "lawsuit", "fraud", "hack", "war", "sanctions", "tariff", "inflation", "hike", "hikes", "recession", "default", "investigation", "layoffs"}
HIGH_IMPACT = {"fed", "federal reserve", "powell", "ecb", "central bank", "rate decision", "interest rate", "cpi", "inflation", "nfp", "jobs report", "gdp", "earnings", "guidance", "sec", "etf", "president", "sanctions", "war", "tariff", "regulation", "bankruptcy", "merger"}
RELIABLE = {"Reuters": 0.98, "Bloomberg": 0.97, "Financial Times": 0.96, "Associated Press": 0.96, "CNBC": 0.90, "Yahoo Finance": 0.88, "MarketWatch": 0.86, "Barrons.com": 0.90}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z'-]+", text.lower())


def headline_sentiment(title: str) -> float:
    tokens = _tokens(title)
    if not tokens:
        return 0.0
    pos = sum(t in POSITIVE for t in tokens)
    neg = sum(t in NEGATIVE for t in tokens)
    return max(-1.0, min(1.0, (pos - neg) / max(2, pos + neg)))


def analyze_news(articles: list[dict]) -> dict:
    now = datetime.now(timezone.utc)
    enriched = []
    weighted_sum = 0.0
    weight_total = 0.0
    high_count = 0
    for article in articles:
        title = article.get("title") or ""
        publisher = article.get("publisher") or "Unknown"
        lower = title.lower()
        sentiment = headline_sentiment(title)
        impact_hits = sum(phrase in lower for phrase in HIGH_IMPACT)
        relevance = 0.9 if impact_hits >= 2 else 0.75 if impact_hits == 1 else 0.5
        reliability = RELIABLE.get(publisher, 0.62)
        age_factor = 1.0
        published = article.get("published_at")
        if published:
            try:
                age_hours = max(0, (now - datetime.fromisoformat(published)).total_seconds() / 3600)
                age_factor = max(0.35, 1 - age_hours / 168)
            except ValueError:
                pass
        importance_score = relevance * reliability * age_factor
        level = "alta" if importance_score >= 0.62 else "media" if importance_score >= 0.4 else "baja"
        if level == "alta":
            high_count += 1
        weight = max(0.05, importance_score)
        weighted_sum += sentiment * weight
        weight_total += weight
        enriched.append({**article, "sentiment": round(sentiment, 3), "relevance": level, "credibility": round(reliability, 2)})
    aggregate = weighted_sum / weight_total if weight_total else 0.0
    score = max(-100, min(100, aggregate * 100))
    label = "alcista" if score >= 15 else "bajista" if score <= -15 else "mixto"
    return {"score": round(score, 2), "label": label, "high_impact_count": high_count, "articles": enriched[:12]}


def sentiment_component(news_result: dict) -> dict:
    articles = news_result.get("articles", [])
    values = [a.get("sentiment", 0) for a in articles]
    if not values:
        return {"score": 0.0, "label": "mixto", "state": "incertidumbre"}
    mean = sum(values) / len(values)
    extreme_ratio = sum(abs(v) >= 0.5 for v in values) / len(values)
    score = max(-100, min(100, mean * 100))
    if score >= 55 and extreme_ratio >= 0.4:
        state = "euforia"
    elif score <= -55 and extreme_ratio >= 0.4:
        state = "pánico"
    else:
        state = "optimismo" if score >= 15 else "pesimismo" if score <= -15 else "incertidumbre"
    return {"score": round(score, 2), "label": "alcista" if score >= 15 else "bajista" if score <= -15 else "mixto", "state": state}
