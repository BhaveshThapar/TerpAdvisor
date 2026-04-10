"""
Schedule builder as a Constraint Satisfaction Problem (CSP).

Models schedule construction as a CSP where:
- Variables: course slots to fill
- Domains: available sections for each course
- Constraints: no time conflicts, user preferences (no 8AMs, prefer MWF, etc.)

Uses backtracking search with constraint propagation (forward checking)
to generate feasible schedules, then ranks them by preference satisfaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.engine.interval_tree import IntervalTree, TimeInterval


class DayPreference(Enum):
    MWF = "mwf"
    TUTH = "tuth"
    NO_FRIDAY = "no_friday"
    BALANCED = "balanced"
    ANY = "any"


@dataclass
class SchedulePreferences:
    """User preferences for schedule optimization."""
    no_before: int = 0          # No classes before this time (minutes from midnight, e.g., 480 = 8AM)
    no_after: int = 1440        # No classes after this time
    day_preference: DayPreference = DayPreference.ANY
    max_classes_per_day: int = 5
    minimize_gaps: bool = True   # Prefer back-to-back classes
    max_gap_minutes: int = 120   # Max gap between classes before penalty
    preferred_days: list[str] = field(default_factory=list)  # e.g., ["M", "W", "F"]
    avoid_days: list[str] = field(default_factory=list)      # e.g., ["F"]


@dataclass
class Section:
    """A course section with meeting times."""
    section_id: str
    course_id: str
    professor: str
    meetings: list[TimeInterval]  # Multiple meetings per week (e.g., MWF 10-10:50)
    open_seats: int = 0

    @property
    def days(self) -> set[str]:
        return {m.day for m in self.meetings}


@dataclass
class ScheduleResult:
    """A complete schedule with its quality score."""
    sections: list[Section]
    score: float  # 0-100, higher = better fit with preferences
    conflicts: list[str]  # Human-readable constraint violations (empty = feasible)
    total_credits: int = 0
    breakdown: dict[str, float] = field(default_factory=dict)  # Score breakdown by factor


class ScheduleSolver:
    """CSP-based schedule optimizer.

    Finds all feasible schedules (no time conflicts) and ranks them
    by how well they satisfy user preferences.
    """

    def __init__(self, preferences: SchedulePreferences | None = None):
        self.preferences = preferences or SchedulePreferences()

    def solve(
        self,
        course_sections: dict[str, list[Section]],  # course_id → available sections
        max_results: int = 5,
    ) -> list[ScheduleResult]:
        """Generate top-K feasible schedules for the given courses.

        Args:
            course_sections: Map of course_id → list of available sections
            max_results: Maximum number of schedules to return

        Returns:
            List of ScheduleResult sorted by score descending
        """
        if not course_sections:
            return []

        courses = list(course_sections.keys())
        all_schedules: list[list[Section]] = []

        # Backtracking search with forward checking
        self._backtrack(
            courses=courses,
            course_sections=course_sections,
            index=0,
            current=[],
            tree=IntervalTree(),
            results=all_schedules,
            limit=max_results * 20,  # Increased search space
        )

        # Score and rank
        scored = [self._score_schedule(s) for s in all_schedules]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:max_results]

    def _backtrack(
        self,
        courses: list[str],
        course_sections: dict[str, list[Section]],
        index: int,
        current: list[Section],
        tree: IntervalTree,
        results: list[list[Section]],
        limit: int,
    ) -> None:
        """Backtracking search with constraint propagation."""
        if len(results) >= limit:
            return

        if index == len(courses):
            results.append(list(current))
            return

        course_id = courses[index]
        for section in course_sections[course_id]:
            # Forward checking: does this section conflict with current schedule?
            if self._has_conflict(section, tree):
                continue

            # Check hard constraints (time bounds)
            if not self._meets_hard_constraints(section):
                continue

            # Place this section
            current.append(section)
            for meeting in section.meetings:
                tree.insert(meeting)

            self._backtrack(courses, course_sections, index + 1, current, tree, results, limit)

            # Undo placement
            current.pop()
            for meeting in section.meetings:
                tree.remove(meeting)

    def _has_conflict(self, section: Section, tree: IntervalTree) -> bool:
        """Check if a section conflicts with any interval in the tree."""
        for meeting in section.meetings:
            if tree.has_conflict(meeting):
                return True
        return False

    def _meets_hard_constraints(self, section: Section) -> bool:
        """Check hard constraints that immediately disqualify a section."""
        for meeting in section.meetings:
            if meeting.start < self.preferences.no_before:
                return False
            if meeting.end > self.preferences.no_after:
                return False
        # Check avoided days
        if self.preferences.avoid_days:
            for meeting in section.meetings:
                if meeting.day in self.preferences.avoid_days:
                    return False
        return True

    def _score_schedule(self, sections: list[Section]) -> ScheduleResult:
        """Score a complete schedule against user preferences.

        Scoring factors (out of 100):
        - Time preference satisfaction (30 pts)
        - Day preference satisfaction (25 pts)
        - Gap minimization (20 pts)
        - Classes-per-day balance (15 pts)
        - Seat availability (10 pts)
        """
        breakdown: dict[str, float] = {}

        # Collect all meetings
        all_meetings: list[TimeInterval] = []
        for s in sections:
            all_meetings.extend(s.meetings)

        if not all_meetings:
            return ScheduleResult(sections=sections, score=0, conflicts=[], breakdown={})

        # 1. Time preference (30 pts) — penalize early/late classes
        time_score = self._score_time_preferences(all_meetings)
        breakdown["time_preferences"] = round(time_score / 30, 3)

        # 2. Day preference (25 pts)
        day_score = self._score_day_preferences(all_meetings)
        breakdown["day_preferences"] = round(day_score / 25, 3)

        # 3. Gap minimization (20 pts)
        gap_score = self._score_gaps(all_meetings)
        breakdown["gap_minimization"] = round(gap_score / 20, 3)

        # 4. Classes per day balance (15 pts)
        balance_score = self._score_daily_balance(all_meetings)
        breakdown["daily_balance"] = round(balance_score / 15, 3)

        # 5. Seat availability (10 pts)
        seat_score = self._score_seat_availability(sections)
        breakdown["seat_availability"] = round(seat_score / 10, 3)

        total = time_score + day_score + gap_score + balance_score + seat_score

        return ScheduleResult(
            sections=sections,
            score=round(total, 1),
            conflicts=[],
            total_credits=sum(getattr(s, 'credits', 3) for s in sections),
            breakdown=breakdown,
        )

    def _score_time_preferences(self, meetings: list[TimeInterval]) -> float:
        """Score based on how well meeting times match preferences (0-30)."""
        if not meetings:
            return 30.0

        penalties = 0
        for m in meetings:
            # Penalize classes before 9AM (540 min)
            if m.start < 540:
                penalties += (540 - m.start) / 60  # hours before 9AM
            # Penalize classes after 5PM (1020 min)
            if m.end > 1020:
                penalties += (m.end - 1020) / 60

        max_penalty = len(meetings) * 3  # Normalize
        return max(0, 30 * (1 - penalties / max(max_penalty, 1)))

    def _score_day_preferences(self, meetings: list[TimeInterval]) -> float:
        """Score based on day preference satisfaction (0-25)."""
        days_used = {m.day for m in meetings}
        pref = self.preferences.day_preference

        if pref == DayPreference.ANY:
            return 25.0
        elif pref == DayPreference.MWF:
            wanted = {"M", "W", "F"}
            unwanted = days_used - wanted
            return 25.0 * (1 - len(unwanted) / max(len(days_used), 1))
        elif pref == DayPreference.TUTH:
            wanted = {"T", "Th"}
            unwanted = days_used - wanted
            return 25.0 * (1 - len(unwanted) / max(len(days_used), 1))
        elif pref == DayPreference.NO_FRIDAY:
            return 0.0 if "F" in days_used else 25.0

        return 25.0

    def _score_gaps(self, meetings: list[TimeInterval]) -> float:
        """Score based on gaps between classes on the same day (0-20)."""
        if not self.preferences.minimize_gaps:
            return 20.0

        # Group meetings by day
        by_day: dict[str, list[TimeInterval]] = {}
        for m in meetings:
            by_day.setdefault(m.day, []).append(m)

        total_gap_penalty = 0
        total_gaps = 0

        for day, day_meetings in by_day.items():
            sorted_m = sorted(day_meetings, key=lambda x: x.start)
            for i in range(len(sorted_m) - 1):
                gap = sorted_m[i + 1].start - sorted_m[i].end
                if gap > self.preferences.max_gap_minutes:
                    total_gap_penalty += (gap - self.preferences.max_gap_minutes) / 60
                total_gaps += 1

        if total_gaps == 0:
            return 20.0

        return max(0, 20 * (1 - total_gap_penalty / max(total_gaps * 2, 1)))

    def _score_daily_balance(self, meetings: list[TimeInterval]) -> float:
        """Score based on even distribution of classes across days (0-15)."""
        by_day: dict[str, int] = {}
        for m in meetings:
            by_day[m.day] = by_day.get(m.day, 0) + 1

        if not by_day:
            return 15.0

        max_per_day = max(by_day.values())
        # Penalize if any day exceeds max_classes_per_day preference
        if max_per_day > self.preferences.max_classes_per_day:
            over = max_per_day - self.preferences.max_classes_per_day
            return max(0, 15 - over * 5)

        # Reward even distribution
        avg = sum(by_day.values()) / len(by_day)
        variance = sum((v - avg) ** 2 for v in by_day.values()) / len(by_day)
        return max(0, 15 * (1 - variance / 4))

    def _score_seat_availability(self, sections: list[Section]) -> float:
        """Score based on seat availability (0-10)."""
        if not sections:
            return 10.0

        total_score = 0
        for s in sections:
            if s.open_seats > 10:
                total_score += 1.0
            elif s.open_seats > 0:
                total_score += 0.5
            # 0 seats = 0 score

        return 10 * total_score / len(sections)
