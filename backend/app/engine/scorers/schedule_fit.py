"""Schedule fit scorer — penalizes courses with sections that conflict with already-selected courses."""

from app.engine.scorers.base import BaseScorer, ScoreResult, ScoringContext


class ScheduleFitScorer(BaseScorer):
    name = "schedule_fit"
    display_name = "Schedule Fit"
    default_weight = 0.10

    async def score(self, course_id: str, context: ScoringContext) -> ScoreResult:
        if not context.selected_sections:
            return ScoreResult(
                score=1.0,
                explanation="No schedule conflicts (no other courses selected)",
                confidence=1.0,
                factor_name=self.name,
            )

        course = context.course_data.get(course_id, {})
        sections = course.get("sections", [])

        if not sections:
            return ScoreResult(
                score=0.5,
                explanation="No section data available to check conflicts",
                confidence=0.3,
                factor_name=self.name,
            )

        # Check what fraction of sections have time conflicts
        conflict_free = 0
        for section in sections:
            has_conflict = False
            for meeting in section.get("meetings", []):
                for selected in context.selected_sections:
                    for sel_meeting in selected.get("meetings", []):
                        if (
                            meeting.get("day") == sel_meeting.get("day")
                            and meeting.get("start") < sel_meeting.get("end")
                            and sel_meeting.get("start") < meeting.get("end")
                        ):
                            has_conflict = True
                            break
                    if has_conflict:
                        break
                if has_conflict:
                    break
            if not has_conflict:
                conflict_free += 1

        if conflict_free == 0:
            return ScoreResult(
                score=0.0,
                explanation="All sections conflict with your current schedule",
                confidence=1.0,
                factor_name=self.name,
            )

        ratio = conflict_free / len(sections)
        return ScoreResult(
            score=ratio,
            explanation=f"{conflict_free}/{len(sections)} sections fit your schedule",
            confidence=1.0,
            factor_name=self.name,
        )
