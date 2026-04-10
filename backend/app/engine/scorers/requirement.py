"""Requirement fulfillment scorer — prioritizes courses that satisfy unmet degree requirements."""

from app.engine.scorers.base import BaseScorer, ScoreResult, ScoringContext


class RequirementScorer(BaseScorer):
    name = "requirement"
    display_name = "Requirement Fulfillment"
    default_weight = 0.35

    async def score(self, course_id: str, context: ScoringContext) -> ScoreResult:
        impact = context.requirement_impact.get(course_id, 0)

        if impact == 0:
            return ScoreResult(
                score=0.0,
                explanation="Does not fulfill any remaining requirements",
                confidence=1.0,
                factor_name=self.name,
            )

        # Normalize: 1 requirement = 0.5, 2+ = scaling toward 1.0
        score = min(1.0, 0.5 + (impact - 1) * 0.25)

        req_word = "requirement" if impact == 1 else "requirements"
        return ScoreResult(
            score=score,
            explanation=f"Fulfills {impact} unfulfilled degree {req_word}",
            confidence=1.0,
            factor_name=self.name,
        )
