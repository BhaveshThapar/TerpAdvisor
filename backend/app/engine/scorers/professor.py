"""Professor rating scorer — factors in instructor quality for available sections."""

from app.engine.scorers.base import BaseScorer, ScoreResult, ScoringContext


class ProfessorScorer(BaseScorer):
    name = "professor"
    display_name = "Professor Rating"
    default_weight = 0.15

    async def score(self, course_id: str, context: ScoringContext) -> ScoreResult:
        course = context.course_data.get(course_id, {})
        professors = course.get("professors", [])

        if not professors:
            return ScoreResult(
                score=0.5,
                explanation="No professor data available",
                confidence=0.2,
                factor_name=self.name,
            )

        # Get ratings for all professors teaching this course
        ratings = []
        prof_details = []
        for prof_name in professors:
            prof = context.professor_data.get(prof_name, {})
            rating = prof.get("avg_rating")
            if rating is not None:
                ratings.append(rating)
                prof_details.append((prof_name, rating))

        if not ratings:
            return ScoreResult(
                score=0.5,
                explanation="No professor ratings available",
                confidence=0.2,
                factor_name=self.name,
            )

        # Use the best professor's rating (student will likely pick that section)
        best_rating = max(ratings)
        best_prof = max(prof_details, key=lambda x: x[1])

        # Normalize: PlanetTerp ratings are 1-5
        normalized = max(0.0, min(1.0, (best_rating - 1.0) / 4.0))

        # Confidence based on review count
        review_count = sum(
            context.professor_data.get(p, {}).get("review_count", 0) for p in professors
        )
        confidence = min(1.0, review_count / 20)  # 20+ reviews = full confidence

        return ScoreResult(
            score=normalized,
            explanation=f"Best instructor: {best_prof[0]} ({best_prof[1]:.1f}/5.0 rating)",
            confidence=max(0.3, confidence),
            factor_name=self.name,
        )
