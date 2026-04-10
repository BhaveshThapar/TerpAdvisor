"""Sentiment scorer — NLP sentiment analysis on student reviews."""

from app.engine.scorers.base import BaseScorer, ScoreResult, ScoringContext
from app.engine.sentiment import analyze_reviews


class SentimentScorer(BaseScorer):
    name = "sentiment"
    display_name = "Review Sentiment"
    default_weight = 0.10

    async def score(self, course_id: str, context: ScoringContext) -> ScoreResult:
        reviews = context.review_data.get(course_id, [])

        if not reviews:
            return ScoreResult(
                score=0.5,
                explanation="No student reviews available",
                confidence=0.1,
                factor_name=self.name,
            )

        result = analyze_reviews(reviews)

        # Convert polarity (-1 to 1) to score (0 to 1)
        normalized = (result.polarity + 1.0) / 2.0

        return ScoreResult(
            score=normalized,
            explanation=result.summary,
            confidence=result.confidence,
            factor_name=self.name,
        )
