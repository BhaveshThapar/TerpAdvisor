"""
Abstract base for recommendation scorers.

Each scorer evaluates courses on one dimension and returns a normalized score
plus a human-readable explanation. The Strategy pattern allows scorers to be
plugged in/out and weighted dynamically.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ScoreResult:
    """Result from a single scorer for a single course."""
    score: float          # 0.0 to 1.0, normalized
    explanation: str      # Human-readable reason, e.g., "High avg GPA of 3.5"
    confidence: float     # 0.0 to 1.0, how reliable this score is (low data = low confidence)
    factor_name: str      # Name of the scoring factor, e.g., "gpa"

    @property
    def weighted_score(self) -> float:
        """Score adjusted by confidence — low-data scores are dampened."""
        return self.score * self.confidence


class BaseScorer(ABC):
    """Abstract base class for recommendation scorers.

    Each scorer implements `score()` which evaluates a single course
    and returns a ScoreResult with a normalized score and explanation.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this scorer (e.g., 'gpa', 'requirement')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g., 'GPA Score', 'Requirement Fulfillment')."""
        ...

    @property
    def default_weight(self) -> float:
        """Default weight for this scorer (0.0 to 1.0). Override per scorer."""
        return 0.1

    @abstractmethod
    async def score(self, course_id: str, context: ScoringContext) -> ScoreResult:
        """Score a single course. Returns normalized 0-1 score with explanation."""
        ...


@dataclass
class ScoringContext:
    """Shared context passed to all scorers for a recommendation request.

    Contains everything scorers need to evaluate courses without
    making their own database/API calls.
    """
    user_id: str
    completed_courses: set[str]
    in_progress_courses: set[str]
    major: str
    # Pre-loaded data to avoid N+1 queries
    course_data: dict[str, dict]      # course_id → {avg_gpa, credits, department, ...}
    professor_data: dict[str, dict]   # professor_name → {avg_rating, review_count, ...}
    review_data: dict[str, list]      # course_id → [{rating, text, professor}, ...]
    grade_data: dict[str, dict]       # course_id → {A: count, B: count, ...}
    requirement_impact: dict[str, int]  # course_id → number of requirements it fulfills
    selected_sections: list[dict]     # Already-selected sections for schedule fit
    # User preference overrides
    weight_overrides: dict[str, float] = None  # scorer_name → custom weight
    preference_tags: list[str] = None  # e.g., ["project-based", "no-final-exam"]

    def __post_init__(self):
        if self.weight_overrides is None:
            self.weight_overrides = {}
        if self.preference_tags is None:
            self.preference_tags = []
