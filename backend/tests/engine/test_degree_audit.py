"""Tests for the degree audit engine."""

from app.engine.degree_audit import (
    DegreeAuditor,
    RequirementStatus,
    build_cs_requirements,
)


def _build_auditor() -> DegreeAuditor:
    return DegreeAuditor(build_cs_requirements())


class TestDegreeAudit:
    def test_fresh_student(self):
        auditor = _build_auditor()
        result = auditor.audit({})
        assert result.overall_progress_pct == 0.0
        assert result.total_credits_completed == 0
        assert len(result.courses_remaining) > 0

    def test_partial_progress(self):
        auditor = _build_auditor()
        completed = {
            "CMSC131": 4,
            "CMSC132": 4,
            "MATH140": 4,
            "MATH141": 4,
        }
        result = auditor.audit(completed)
        assert result.total_credits_completed == 16
        assert result.overall_progress_pct > 0

        # Check that CMSC131 requirement is marked complete
        lower_cs = next(g for g in result.group_results if g.group.name == "Lower-Level CS Requirements")
        intro1 = next(r for r in lower_cs.results if r.requirement.name == "Intro to CS I")
        assert intro1.status == RequirementStatus.COMPLETE

    def test_cs_elective_tracking(self):
        auditor = _build_auditor()
        completed = {
            "CMSC131": 4, "CMSC132": 4, "CMSC216": 4, "CMSC250": 4,
            "CMSC351": 3,
            "CMSC412": 3,  # 1 of 2 needed general electives; Area 1 satisfied
            "MATH140": 4, "MATH141": 4,
        }
        result = auditor.audit(completed)

        # General electives: 1 course done, need 2 → IN_PROGRESS
        upper_cs = next(g for g in result.group_results if g.group.name == "Upper-Level CS Requirements")
        electives = next(r for r in upper_cs.results if "Electives" in r.requirement.name)
        assert electives.status == RequirementStatus.IN_PROGRESS
        assert len(electives.completed_courses) == 1
        assert electives.credits_remaining > 0

        # Area requirements: only Area 1 covered (CMSC412), need 3 of 5 → IN_PROGRESS
        cs_areas = next(g for g in result.group_results if g.group.id == "cs_areas")
        assert cs_areas.completed_count == 1
        area3 = next(r for r in cs_areas.results if r.requirement.id == "cs_area3")
        # CMSC430 satisfies Area 3 — not yet taken, so incomplete
        assert area3.status == RequirementStatus.INCOMPLETE
        assert "CMSC430" in area3.remaining_options

    def test_requirement_with_options(self):
        """Linear Algebra can be satisfied by MATH240 OR MATH461 (Data Science track requires it)."""
        # Linear Algebra is only required for DS/ML/Quantum tracks, not General
        ds_auditor = DegreeAuditor(build_cs_requirements(track="Data Science"))
        completed_with_240 = {"MATH240": 4}
        completed_with_461 = {"MATH461": 4}

        result_240 = ds_auditor.audit(completed_with_240)
        result_461 = ds_auditor.audit(completed_with_461)

        math_group_240 = next(g for g in result_240.group_results if g.group.name == "Mathematics Requirements")
        linear_240 = next(r for r in math_group_240.results if r.requirement.name == "Linear Algebra")
        assert linear_240.status == RequirementStatus.COMPLETE

        math_group_461 = next(g for g in result_461.group_results if g.group.name == "Mathematics Requirements")
        linear_461 = next(r for r in math_group_461.results if r.requirement.name == "Linear Algebra")
        assert linear_461.status == RequirementStatus.COMPLETE


class TestHighestImpactCourses:
    def test_recommends_unfulfilled_requirements(self):
        auditor = _build_auditor()
        completed = {"CMSC131": 4, "MATH140": 4}
        available = ["CMSC132", "CMSC250", "MATH141", "CMSC335", "ECON200"]

        impact = auditor.get_highest_impact_courses(completed, available)
        impact_courses = [c for c, _ in impact]

        # CMSC132, MATH141 should be high impact (directly fulfill core requirements)
        assert "CMSC132" in impact_courses
        assert "MATH141" in impact_courses

    def test_no_impact_for_completed(self):
        auditor = _build_auditor()
        completed = {"CMSC131": 4}
        # CMSC131 is already done — it shouldn't show impact
        impact = auditor.get_highest_impact_courses(completed, ["CMSC131"])
        assert len(impact) == 0
