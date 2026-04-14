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
    "online": ["online", "asynchronous", "async", "recorded lectures", "fully online", "remote", "zoom"],
    "no-attendance": ["no attendance", "attendance not required", "don't need to go", "skip class", "never went", "didn't go to class", "never attended"],
    "easy-a": ["easy a", "easy class", "generous curve", "free a", "gpa booster", "boost your gpa", "easiest"],
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

        reviews = context.review_data.get(course_id, [])
        if not reviews:
            return ScoreResult(
                score=0.5,
                explanation="No review data to match preferences against",
                confidence=0.1,
                factor_name=self.name,
            )

        # Combine all review text
        combined_text = " ".join(r.get("text", "") for r in reviews).lower()

        matched_tags = []
        for tag in user_tags:
            keywords = TAG_KEYWORDS.get(tag, [])
            if any(kw in combined_text for kw in keywords):
                matched_tags.append(tag)

        if not matched_tags:
            return ScoreResult(
                score=0.3,
                explanation=f"Reviews don't mention your preferences: {', '.join(user_tags[:3])}",
                confidence=0.4,
                factor_name=self.name,
            )

        match_ratio = len(matched_tags) / len(user_tags)
        tag_list = ", ".join(matched_tags[:3])
        return ScoreResult(
            score=min(1.0, 0.5 + match_ratio * 0.5),
            explanation=f"Matches your preferences: {tag_list}",
            confidence=min(1.0, len(reviews) / 5),
            factor_name=self.name,
        )
