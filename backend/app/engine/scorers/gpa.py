"""GPA scorer — higher average GPA = easier/more generous grading = higher score."""

from app.engine.scorers.base import BaseScorer, ScoreResult, ScoringContext


class GPAScorer(BaseScorer):
    name = "gpa"
    display_name = "Average GPA"
    default_weight = 0.25

    async def score(self, course_id: str, context: ScoringContext) -> ScoreResult:
        course = context.course_data.get(course_id, {})
        avg_gpa = course.get("avg_gpa")

        if avg_gpa is None:
            return ScoreResult(
                score=0.5,
                explanation="No GPA data available",
                confidence=0.2,
                factor_name=self.name,
            )

        # Normalize GPA to 0-1 scale (2.0 = 0, 4.0 = 1.0)
        normalized = max(0.0, min(1.0, (avg_gpa - 2.0) / 2.0))

        # Confidence based on grade data volume.
        # grade_data is populated from PlanetTerp when available; fall back to 0.7
        # when avg_gpa comes from the DB (which itself aggregates PlanetTerp data).
        grades = context.grade_data.get(course_id, {})
        total_grades = sum(grades.values()) if grades else 0
        if total_grades > 0:
            confidence = min(1.0, total_grades / 100)
        else:
            confidence = 0.7  # DB avg_gpa is reliable; don't dampen to 0.3

        if avg_gpa >= 3.5:
            desc = f"High avg GPA of {avg_gpa:.2f} — generous grading"
        elif avg_gpa >= 3.0:
            desc = f"Solid avg GPA of {avg_gpa:.2f}"
        elif avg_gpa >= 2.5:
            desc = f"Moderate avg GPA of {avg_gpa:.2f} — tougher grading"
        else:
            desc = f"Low avg GPA of {avg_gpa:.2f} — historically difficult"

        return ScoreResult(
            score=normalized,
            explanation=desc,
            confidence=confidence,
            factor_name=self.name,
        )
