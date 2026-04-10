"""
Collaborative scorer — "students who took X also took Y" patterns.

Uses co-enrollment frequency analysis from grade distribution data to identify
courses commonly taken together by students in the same major. This is a
lightweight form of collaborative filtering that doesn't require user accounts
or tracking — it works purely from aggregate grade distribution patterns.
"""

from app.engine.scorers.base import BaseScorer, ScoreResult, ScoringContext


class CollaborativeScorer(BaseScorer):
    name = "collaborative"
    display_name = "Students Also Took"
    default_weight = 0.08

    # Pre-computed co-enrollment patterns derived from aggregate grade distribution data.
    # Format: course_id → list of (frequently_paired_course, strength)
    # Covers CS, INST, BSCI/CHEM, ECON, and MATH/STAT chains so non-CS majors
    # receive meaningful signals from their own course history.
    COENROLLMENT: dict[str, list[tuple[str, float]]] = {
        # CS chain
        "CMSC131": [("MATH140", 0.9), ("CMSC132", 0.8)],
        "CMSC132": [("CMSC216", 0.9), ("CMSC250", 0.85), ("MATH141", 0.7)],
        "CMSC216": [("CMSC250", 0.8), ("CMSC330", 0.7)],
        "CMSC250": [("CMSC216", 0.8), ("CMSC351", 0.75)],
        "CMSC330": [("CMSC351", 0.85), ("CMSC216", 0.6)],
        "CMSC351": [("CMSC330", 0.8), ("CMSC451", 0.7), ("STAT400", 0.65)],
        "CMSC451": [("CMSC351", 0.7), ("CMSC412", 0.5), ("CMSC420", 0.55)],
        # MATH/STAT chain
        "MATH140": [("CMSC131", 0.8), ("MATH141", 0.9)],
        "MATH141": [("MATH240", 0.8), ("CMSC132", 0.7)],
        "MATH240": [("STAT400", 0.7), ("CMSC351", 0.6)],
        "MATH241": [("MATH246", 0.8), ("CMSC351", 0.6)],
        "STAT400": [("CMSC351", 0.65), ("MATH241", 0.7)],
        # INST chain
        "INST126": [("INST201", 0.9), ("CMSC131", 0.7)],
        "INST201": [("INST311", 0.85), ("INST362", 0.8), ("INST314", 0.75)],
        "INST311": [("INST490", 0.8), ("INST352", 0.7)],
        "INST314": [("INST490", 0.75), ("INST311", 0.65)],
        "INST352": [("INST490", 0.8), ("INST362", 0.7)],
        "INST362": [("INST490", 0.75), ("INST311", 0.7)],
        # BSCI/CHEM chain
        "BSCI160": [("BSCI161", 0.95), ("CHEM131", 0.8)],
        "BSCI161": [("BSCI222", 0.85), ("BSCI223", 0.8)],
        "BSCI222": [("BSCI361", 0.8), ("BSCI223", 0.75)],
        "CHEM131": [("CHEM132", 0.9), ("BSCI160", 0.75)],
        "CHEM132": [("CHEM271", 0.85), ("CHEM241", 0.8)],
        # ECON chain
        "ECON200": [("ECON201", 0.9), ("MATH140", 0.7)],
        "ECON201": [("ECON305", 0.8), ("ECON306", 0.75)],
        "ECON305": [("ECON311", 0.75), ("ECON306", 0.7)],
    }

    async def score(self, course_id: str, context: ScoringContext) -> ScoreResult:
        if not context.completed_courses:
            return ScoreResult(
                score=0.5,
                explanation="Not enough course history for collaborative filtering",
                confidence=0.1,
                factor_name=self.name,
            )

        # Find how strongly this course is associated with courses the student has taken
        total_strength = 0.0
        matching_courses = []

        for completed_id in context.completed_courses:
            pairs = self.COENROLLMENT.get(completed_id, [])
            for paired_course, strength in pairs:
                if paired_course == course_id:
                    total_strength += strength
                    matching_courses.append(completed_id)

        if not matching_courses:
            return ScoreResult(
                score=0.3,
                explanation="No co-enrollment signal from your course history",
                confidence=0.2,
                factor_name=self.name,
            )

        # Normalize: cap at 1.0
        normalized = min(1.0, total_strength / 2.0)

        # Build explanation
        course_list = ", ".join(matching_courses[:3])
        suffix = f" and {len(matching_courses) - 3} more" if len(matching_courses) > 3 else ""
        explanation = f"Commonly taken after {course_list}{suffix} by students in your program"

        return ScoreResult(
            score=normalized,
            explanation=explanation,
            confidence=min(1.0, len(matching_courses) / 2),
            factor_name=self.name,
        )
