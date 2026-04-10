"""
Recommendation engine orchestrator.

Aggregates scores from all pluggable scorers, applies user-defined weights,
and generates ranked recommendations with explainable reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.scorers.base import BaseScorer, ScoreResult, ScoringContext
from app.engine.scorers.collaborative import CollaborativeScorer
from app.engine.scorers.gpa import GPAScorer
from app.engine.scorers.preference_tags import PreferenceTagScorer
from app.engine.scorers.professor import ProfessorScorer
from app.engine.scorers.requirement import RequirementScorer
from app.engine.scorers.schedule_fit import ScheduleFitScorer
from app.engine.scorers.sentiment import SentimentScorer


@dataclass
class Explanation:
    """A single explanation factor for why a course was recommended."""
    factor: str          # e.g., "Requirement Fulfillment"
    score: float         # 0-1
    weight: float        # Applied weight
    contribution: float  # score * weight (how much this factor affected final rank)
    text: str            # Human-readable explanation


@dataclass
class Recommendation:
    """A single course recommendation with score and explanations."""
    course_id: str
    final_score: float  # 0-100 weighted aggregate
    rank: int
    explanations: list[Explanation]
    top_reason: str  # The single biggest contributing factor as a sentence
    confidence: float  # Overall confidence in this recommendation


@dataclass
class RecommendationResult:
    """Complete recommendation result set."""
    recommendations: list[Recommendation]
    total_candidates: int
    filters_applied: dict = field(default_factory=dict)
    weights_used: dict[str, float] = field(default_factory=dict)


class RecommendationEngine:
    """Orchestrates the scoring pipeline and generates ranked recommendations.

    Architecture (Strategy pattern):
    - Each scoring dimension is a pluggable `Scorer` implementing BaseScorer
    - Scorers are registered at init and can be added/removed dynamically
    - User-defined weight overrides are applied at aggregation time
    - Each recommendation includes explainable reasoning
    """

    def __init__(self, scorers: list[BaseScorer] | None = None):
        if scorers is None:
            scorers = self._default_scorers()
        self._scorers: dict[str, BaseScorer] = {s.name: s for s in scorers}

    @staticmethod
    def _default_scorers() -> list[BaseScorer]:
        return [
            RequirementScorer(),
            GPAScorer(),
            ProfessorScorer(),
            SentimentScorer(),
            CollaborativeScorer(),
            ScheduleFitScorer(),
            PreferenceTagScorer(),
        ]

    def register_scorer(self, scorer: BaseScorer) -> None:
        """Dynamically add a new scorer to the pipeline."""
        self._scorers[scorer.name] = scorer

    def remove_scorer(self, name: str) -> None:
        """Remove a scorer from the pipeline."""
        self._scorers.pop(name, None)

    async def recommend(
        self,
        candidate_courses: list[str],
        context: ScoringContext,
        top_n: int = 20,
    ) -> RecommendationResult:
        """Generate ranked recommendations for candidate courses.

        Args:
            candidate_courses: Course IDs to evaluate (pre-filtered by availability)
            context: Shared scoring context with pre-loaded data
            top_n: Number of recommendations to return
        """
        # Resolve weights: user overrides > scorer defaults
        weights = self._resolve_weights(context.weight_overrides)

        # Score all candidates
        scored: list[tuple[str, float, float, list[tuple[str, ScoreResult]]]] = []

        for course_id in candidate_courses:
            score_results: list[tuple[str, ScoreResult]] = []
            total_score = 0.0
            total_confidence = 0.0

            for name, scorer in self._scorers.items():
                result = await scorer.score(course_id, context)
                weight = weights.get(name, scorer.default_weight)
                contribution = result.weighted_score * weight
                total_score += contribution
                total_confidence += result.confidence * weight
                score_results.append((name, result))

            scored.append((course_id, total_score, total_confidence, score_results))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Build recommendation objects with explanations
        recommendations = []
        for rank, (course_id, total_score, confidence, score_results) in enumerate(
            scored[:top_n], start=1
        ):
            explanations = []
            for scorer_name, result in score_results:
                weight = weights.get(scorer_name, self._scorers[scorer_name].default_weight)
                explanations.append(
                    Explanation(
                        factor=self._scorers[scorer_name].display_name,
                        score=round(result.score, 3),
                        weight=round(weight, 3),
                        contribution=round(result.weighted_score * weight, 3),
                        text=result.explanation,
                    )
                )

            # Sort explanations by contribution (biggest impact first)
            explanations.sort(key=lambda e: e.contribution, reverse=True)

            # Top reason is the highest-contribution factor
            top_reason = explanations[0].text if explanations else "Recommended course"

            recommendations.append(
                Recommendation(
                    course_id=course_id,
                    final_score=round(total_score * 100, 1),
                    rank=rank,
                    explanations=explanations,
                    top_reason=top_reason,
                    confidence=round(confidence, 2),
                )
            )

        return RecommendationResult(
            recommendations=recommendations,
            total_candidates=len(candidate_courses),
            weights_used=weights,
        )

    def _resolve_weights(self, overrides: dict[str, float] | None) -> dict[str, float]:
        """Merge user weight overrides with defaults and normalize to sum to 1.0.

        User overrides are treated as desired final proportions: if the user sets
        gpa=0.6, gpa ends up at exactly 60% and the remaining scorers share the
        other 40% proportionally from their defaults.
        """
        weights = {name: s.default_weight for name, s in self._scorers.items()}
        if overrides:
            valid = {k: v for k, v in overrides.items() if k in weights}
            override_total = sum(valid.values())
            if override_total >= 1.0:
                # Overrides already consume 100%+; just plug them in and normalize
                for k, v in valid.items():
                    weights[k] = v
            else:
                # Scale non-overridden defaults to fill the remaining proportion
                remaining = 1.0 - override_total
                non_override_sum = sum(v for k, v in weights.items() if k not in valid)
                scale = (remaining / non_override_sum) if non_override_sum > 0 else 0.0
                for k in weights:
                    weights[k] = valid[k] if k in valid else weights[k] * scale

        # Final normalize to correct floating-point drift
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights
