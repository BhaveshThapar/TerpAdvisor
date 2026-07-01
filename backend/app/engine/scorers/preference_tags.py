"""
Preference tags scorer — matches courses against user-selected tags
like "project-based", "no final exam", "discussion-heavy", etc.

Tags are derived from review text analysis and course metadata.
"""

from app.engine.scorers.base import BaseScorer, ScoreResult, ScoringContext

# Keywords that map to each preference tag
TAG_KEYWORDS: dict[str, list[str]] = {
    "project-based": ["project", "group project", "final project", "team project", "build", "hands-on"],
    "no-final-exam": ["no final", "no exam", "take-home", "project instead of final"],
    "discussion-heavy": ["discussion", "seminar", "class discussion", "participate", "debate"],
    "light-workload": ["easy", "light", "manageable", "not much work", "chill"],
    "heavy-workload": ["hard", "difficult", "heavy workload", "time-consuming", "challenging"],
    "good-lectures": ["great lectures", "good lecturer", "engaging", "interesting lectures", "clear explanations"],
    "writing-intensive": ["writing", "essays", "papers", "write a lot", "research paper"],
    "math-heavy": ["math", "proofs", "mathematical", "calculus", "equations"],
    "online": [
        "fully online", "entirely online", "class is online", "course is online",
        "taught online", "asynchronous", "async class", "async course",
        "recorded lectures", "over zoom",
    ],
    "no-attendance": ["no attendance", "attendance not required", "don't need to go", "skip class", "never went", "didn't go to class", "never attended"],
    "easy-a": ["easy a", "easy class", "generous curve", "free a", "gpa booster", "boost your gpa", "easiest"],
}


def match_review_tags(combined_text: str) -> set[str]:
    """Return every preference tag whose keywords appear in the review text.

    Shared by the live fallback and scripts/backfill_sentiment.py so precomputed
    and on-the-fly tag matching stay identical.
    """
    text = combined_text.lower()
    return {
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(kw in text for kw in keywords)
    }


class PreferenceTagScorer(BaseScorer):
    name = "preference_tags"
    display_name = "Preference Match"
    default_weight = 0.05

    async def score(self, course_id: str, context: ScoringContext) -> ScoreResult:
        user_tags = getattr(context, "preference_tags", None) or []
        if not user_tags:
            return ScoreResult(
                score=0.5,
                explanation="No preference tags set",
                confidence=0.1,
                factor_name=self.name,
            )

        # Fast path: use precomputed per-course tags (backfill_sentiment.py) so we
        # don't rescan raw review text on every request.
        cd = context.course_data.get(course_id, {})
        precomputed = cd.get("review_tags")
        if precomputed is not None:
            review_count = cd.get("review_count") or 0
            if review_count == 0:
                return ScoreResult(
                    score=0.5,
                    explanation="No review data to match preferences against",
                    confidence=0.1,
                    factor_name=self.name,
                )
            return self._score_from_tags(user_tags, set(precomputed), review_count)

        # Fallback: match live against raw review text.
        reviews = context.review_data.get(course_id, [])
        if not reviews:
            return ScoreResult(
                score=0.5,
                explanation="No review data to match preferences against",
                confidence=0.1,
                factor_name=self.name,
            )

        course_tags = match_review_tags(" ".join(r.get("text", "") for r in reviews))
        return self._score_from_tags(user_tags, course_tags, len(reviews))

    def _score_from_tags(
        self, user_tags: list[str], course_tags: set[str], review_count: int
    ) -> ScoreResult:
        matched = [t for t in user_tags if t in course_tags]
        if not matched:
            return ScoreResult(
                score=0.3,
                explanation=f"Reviews don't mention your preferences: {', '.join(user_tags[:3])}",
                confidence=0.4,
                factor_name=self.name,
            )
        match_ratio = len(matched) / len(user_tags)
        return ScoreResult(
            score=min(1.0, 0.5 + match_ratio * 0.5),
            explanation=f"Matches your preferences: {', '.join(matched[:3])}",
            confidence=min(1.0, review_count / 5),
            factor_name=self.name,
        )
