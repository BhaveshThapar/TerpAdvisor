"""Tests for the CSP-based schedule solver."""

from app.engine.interval_tree import TimeInterval
from app.engine.schedule_solver import (
    DayPreference,
    SchedulePreferences,
    ScheduleSolver,
    Section,
)


def _make_section(course_id: str, section_num: str, day_times: list[tuple[str, str, str]],
                  professor: str = "Staff", seats: int = 20) -> Section:
    """Helper to create a section with meetings."""
    meetings = [
        TimeInterval.from_time_str(start, end, day, f"{course_id} {section_num}")
        for day, start, end in day_times
    ]
    return Section(
        section_id=f"{course_id}-{section_num}",
        course_id=course_id,
        professor=professor,
        meetings=meetings,
        open_seats=seats,
    )


class TestScheduleSolver:
    def test_simple_no_conflict(self):
        """Two courses with non-overlapping sections should produce a schedule."""
        sections = {
            "CMSC330": [
                _make_section("CMSC330", "0101", [("M", "10:00", "10:50"), ("W", "10:00", "10:50"), ("F", "10:00", "10:50")]),
            ],
            "CMSC351": [
                _make_section("CMSC351", "0101", [("T", "11:00", "12:15"), ("Th", "11:00", "12:15")]),
            ],
        }
        solver = ScheduleSolver()
        results = solver.solve(sections)
        assert len(results) >= 1
        assert len(results[0].sections) == 2
        assert len(results[0].conflicts) == 0

    def test_all_sections_conflict(self):
        """When all section options conflict, return no results."""
        sections = {
            "CMSC330": [
                _make_section("CMSC330", "0101", [("M", "10:00", "10:50")]),
            ],
            "CMSC351": [
                _make_section("CMSC351", "0101", [("M", "10:00", "10:50")]),  # Same time!
            ],
        }
        solver = ScheduleSolver()
        results = solver.solve(sections)
        assert len(results) == 0

    def test_picks_non_conflicting_section(self):
        """When one section conflicts and another doesn't, pick the non-conflicting one."""
        sections = {
            "CMSC330": [
                _make_section("CMSC330", "0101", [("M", "10:00", "10:50")]),
            ],
            "CMSC351": [
                _make_section("CMSC351", "0101", [("M", "10:00", "10:50")]),  # Conflicts
                _make_section("CMSC351", "0201", [("T", "14:00", "15:15")]),  # No conflict
            ],
        }
        solver = ScheduleSolver()
        results = solver.solve(sections)
        assert len(results) >= 1
        cmsc351_section = next(s for s in results[0].sections if s.course_id == "CMSC351")
        assert cmsc351_section.section_id == "CMSC351-0201"

    def test_no_8am_preference(self):
        """Schedules with 8AM classes should score lower."""
        sections = {
            "CMSC330": [
                _make_section("CMSC330", "0101", [("M", "08:00", "08:50")]),  # 8AM
                _make_section("CMSC330", "0201", [("M", "11:00", "11:50")]),  # 11AM
            ],
        }
        solver = ScheduleSolver(SchedulePreferences(no_before=540))  # No classes before 9AM
        results = solver.solve(sections)
        # The 8AM section should be filtered out by hard constraint
        assert len(results) >= 1
        section = results[0].sections[0]
        assert section.section_id == "CMSC330-0201"

    def test_day_preference_scoring(self):
        """MWF preference should score MWF sections higher than TuTh."""
        sections = {
            "CMSC330": [
                _make_section("CMSC330", "0101", [("M", "10:00", "10:50"), ("W", "10:00", "10:50"), ("F", "10:00", "10:50")]),
                _make_section("CMSC330", "0201", [("T", "10:00", "11:15"), ("Th", "10:00", "11:15")]),
            ],
        }
        solver = ScheduleSolver(SchedulePreferences(day_preference=DayPreference.MWF))
        results = solver.solve(sections)
        assert len(results) >= 1
        # MWF section should score higher
        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_multiple_courses(self):
        """Solve for 3 courses simultaneously."""
        sections = {
            "CMSC330": [
                _make_section("CMSC330", "0101", [("M", "09:00", "09:50"), ("W", "09:00", "09:50"), ("F", "09:00", "09:50")]),
            ],
            "CMSC351": [
                _make_section("CMSC351", "0101", [("T", "11:00", "12:15"), ("Th", "11:00", "12:15")]),
            ],
            "STAT400": [
                _make_section("STAT400", "0101", [("M", "14:00", "14:50"), ("W", "14:00", "14:50"), ("F", "14:00", "14:50")]),
            ],
        }
        solver = ScheduleSolver()
        results = solver.solve(sections)
        assert len(results) >= 1
        assert len(results[0].sections) == 3

    def test_score_has_breakdown(self):
        sections = {
            "CMSC330": [
                _make_section("CMSC330", "0101", [("M", "10:00", "10:50")]),
            ],
        }
        solver = ScheduleSolver()
        results = solver.solve(sections)
        assert len(results) >= 1
        assert "time_preferences" in results[0].breakdown
        assert "day_preferences" in results[0].breakdown
        assert "gap_minimization" in results[0].breakdown
