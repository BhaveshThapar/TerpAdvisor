"""Tests for the DAG-based course prerequisite engine."""

import pytest

from app.engine.course_graph import CourseGraph, CourseNode, PrereqNode, PrereqType


def _build_test_graph() -> CourseGraph:
    """Build a small test graph: CMSC131 → CMSC132 → CMSC216 → CMSC330"""
    graph = CourseGraph()
    graph.add_course(CourseNode("CMSC131", "Intro I", 4, "CMSC"))
    graph.add_course(CourseNode("CMSC132", "Intro II", 4, "CMSC",
                                PrereqNode(PrereqType.ALL, ["CMSC131"])))
    graph.add_course(CourseNode("CMSC216", "Computer Org", 4, "CMSC",
                                PrereqNode(PrereqType.ALL, ["CMSC132"])))
    graph.add_course(CourseNode("CMSC250", "Discrete", 4, "CMSC",
                                PrereqNode(PrereqType.ALL, ["CMSC131"])))
    graph.add_course(CourseNode("CMSC330", "PLs", 3, "CMSC",
                                PrereqNode(PrereqType.ALL, ["CMSC216", "CMSC250"])))
    graph.add_course(CourseNode("CMSC351", "Algorithms", 3, "CMSC",
                                PrereqNode(PrereqType.ALL, ["CMSC216", "CMSC250"])))
    graph.add_course(CourseNode("MATH140", "Calc I", 4, "MATH"))
    return graph


class TestTopologicalSort:
    def test_valid_ordering(self):
        graph = _build_test_graph()
        order = graph.topological_sort()

        # CMSC131 must come before CMSC132
        assert order.index("CMSC131") < order.index("CMSC132")
        # CMSC132 must come before CMSC216
        assert order.index("CMSC132") < order.index("CMSC216")
        # Both CMSC216 and CMSC250 must come before CMSC330
        assert order.index("CMSC216") < order.index("CMSC330")
        assert order.index("CMSC250") < order.index("CMSC330")

    def test_all_courses_included(self):
        graph = _build_test_graph()
        order = graph.topological_sort()
        assert len(order) == 7
        assert set(order) == {"CMSC131", "CMSC132", "CMSC216", "CMSC250", "CMSC330", "CMSC351", "MATH140"}


class TestCycleDetection:
    def test_no_cycle(self):
        graph = _build_test_graph()
        assert graph.has_cycle() is False

    def test_detects_cycle(self):
        """Manually create a cycle: A → B → C → A"""
        graph = CourseGraph()
        graph.add_course(CourseNode("A", prereqs=PrereqNode(PrereqType.ALL, ["C"])))
        graph.add_course(CourseNode("B", prereqs=PrereqNode(PrereqType.ALL, ["A"])))
        graph.add_course(CourseNode("C", prereqs=PrereqNode(PrereqType.ALL, ["B"])))
        assert graph.has_cycle() is True


class TestAvailableCourses:
    def test_fresh_student(self):
        graph = _build_test_graph()
        available = graph.get_available_courses(completed=set())
        # Only courses with no prereqs: CMSC131 and MATH140
        assert set(available) == {"CMSC131", "MATH140"}

    def test_after_intro(self):
        graph = _build_test_graph()
        available = graph.get_available_courses(completed={"CMSC131"})
        # CMSC132 and CMSC250 now available (both require only CMSC131)
        assert "CMSC132" in available
        assert "CMSC250" in available
        assert "CMSC131" not in available  # Already completed

    def test_deep_progress(self):
        graph = _build_test_graph()
        completed = {"CMSC131", "CMSC132", "CMSC216", "CMSC250"}
        available = graph.get_available_courses(completed=completed)
        assert "CMSC330" in available
        assert "CMSC351" in available


class TestPrereqSatisfaction:
    def test_and_prereqs(self):
        """CMSC330 requires BOTH CMSC216 AND CMSC250."""
        graph = _build_test_graph()
        # Only one of the two prereqs completed
        available = graph.get_available_courses(completed={"CMSC131", "CMSC132", "CMSC216"})
        assert "CMSC330" not in available  # Missing CMSC250

    def test_or_prereqs(self):
        """Test OR prerequisite: need MATH240 OR MATH461."""
        graph = CourseGraph()
        graph.add_course(CourseNode("MATH240", "Linear Algebra", 4))
        graph.add_course(CourseNode("MATH461", "Linear Algebra II", 3))
        graph.add_course(CourseNode("STAT400", "Stats", 3,
                                    prereqs=PrereqNode(PrereqType.ANY, ["MATH240", "MATH461"])))

        available = graph.get_available_courses(completed={"MATH240"})
        assert "STAT400" in available  # MATH240 satisfies the OR

    def test_coreq(self):
        """Corequisites can be taken concurrently."""
        node = PrereqNode(PrereqType.COREQ, ["MATH141"])
        assert node.is_satisfied(completed=set(), in_progress={"MATH141"}) is True
        assert node.is_satisfied(completed=set(), in_progress=set()) is False


class TestPathFinding:
    def test_shortest_path_to_available_course(self):
        graph = _build_test_graph()
        path = graph.shortest_path_to("CMSC132", completed={"CMSC131"})
        assert path == ["CMSC132"]

    def test_shortest_path_with_prereqs(self):
        graph = _build_test_graph()
        path = graph.shortest_path_to("CMSC330", completed=set())
        # Must include CMSC131, CMSC132, CMSC216, CMSC250, and CMSC330
        assert "CMSC131" in path
        assert "CMSC330" in path
        assert path.index("CMSC131") < path.index("CMSC330")

    def test_already_completed(self):
        graph = _build_test_graph()
        path = graph.shortest_path_to("CMSC131", completed={"CMSC131"})
        assert path == []


class TestUnlockedCourses:
    def test_courses_unlocked_by(self):
        graph = _build_test_graph()
        unlocked = graph.get_courses_unlocked_by("CMSC131", completed=set())
        # Completing CMSC131 unlocks CMSC132 and CMSC250
        assert "CMSC132" in unlocked
        assert "CMSC250" in unlocked

    def test_transitive_prerequisites(self):
        graph = _build_test_graph()
        all_prereqs = graph.get_all_prerequisites("CMSC330")
        assert "CMSC216" in all_prereqs
        assert "CMSC250" in all_prereqs
        assert "CMSC132" in all_prereqs
        assert "CMSC131" in all_prereqs


class _StubCourse:
    def __init__(self, course_id: str, department: str, credits: int = 3):
        self.course_id = course_id
        self.name = course_id
        self.department = department
        self.credits = credits
        self.prerequisites_raw = None


class _StubScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _StubExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _StubScalarResult(self._rows)


class _StubDB:
    """Fake AsyncSession that captures the department filter and returns stub rows."""

    def __init__(self, courses_by_dept: dict[str, list[_StubCourse]]):
        self._by_dept = courses_by_dept
        self.last_departments: list[str] | None = None

    async def execute(self, stmt):
        depts: list[str] = []
        try:
            clause = stmt.whereclause
            if clause is not None and hasattr(clause, "right"):
                val = clause.right.value
                if isinstance(val, (list, tuple, set)):
                    depts = list(val)
        except Exception:
            pass
        self.last_departments = depts
        rows: list[_StubCourse] = []
        for d in depts:
            rows.extend(self._by_dept.get(d, []))
        return _StubExecuteResult(rows)


class TestDepartmentsFromRequirements:
    def test_extracts_from_course_options(self):
        from app.engine.degree_audit import build_cs_requirements
        reqs = build_cs_requirements()
        depts = CourseGraph._departments_from_requirements(reqs)
        assert "CMSC" in depts
        assert "MATH" in depts

    def test_extracts_from_prefix_patterns(self):
        from app.engine.degree_audit import (
            DegreeRequirements, Requirement, RequirementGroup, RequirementType,
        )
        reqs = DegreeRequirements(
            major="Test",
            catalog_year="2025",
            track="General",
            total_credits_required=120,
            groups=[
                RequirementGroup(
                    id="ulc", name="ULC", description="",
                    requirements=[
                        Requirement(
                            id="ulc1", name="ULC", type=RequirementType.ELECTIVE,
                            course_options=[], credits_needed=3,
                            prefix_patterns=["INST3", "INST4"],
                        ),
                    ],
                ),
            ],
        )
        depts = CourseGraph._departments_from_requirements(reqs)
        assert depts == ["INST"]


class TestBuildFromUmdCatalogDynamic:
    @pytest.mark.asyncio
    async def test_cs_uses_cmsc_courses(self):
        from app.engine.degree_audit import build_cs_requirements
        reqs = build_cs_requirements()
        db = _StubDB({
            "CMSC": [_StubCourse("CMSC131", "CMSC", 4), _StubCourse("CMSC132", "CMSC", 4)],
            "MATH": [_StubCourse("MATH140", "MATH", 4)],
        })
        graph = await CourseGraph.build_from_umd_catalog(db, "Computer Science", requirements=reqs)
        assert "CMSC131" in graph.courses
        assert "MATH140" in graph.courses
        assert "CMSC" in db.last_departments
        assert "MATH" in db.last_departments

    @pytest.mark.asyncio
    async def test_information_science_pulls_inst_courses(self):
        """Sprint 4 regression: pre-fix, InfoSci worked but any major outside the
        hardcoded 6 got an empty graph. Dynamic derivation must pull INST."""
        from app.engine.degree_audit import build_requirements_for_major
        reqs = build_requirements_for_major("Information Science")
        db = _StubDB({
            "INST": [_StubCourse("INST126", "INST"), _StubCourse("INST155", "INST")],
        })
        graph = await CourseGraph.build_from_umd_catalog(
            db, "Information Science", requirements=reqs,
        )
        assert "INST" in db.last_departments
        assert "INST126" in graph.courses
        assert "INST155" in graph.courses

    @pytest.mark.asyncio
    async def test_empty_graph_logs_error(self, caplog):
        from app.engine.degree_audit import build_cs_requirements
        reqs = build_cs_requirements()
        db = _StubDB({})  # nothing for any dept
        with caplog.at_level("ERROR"):
            graph = await CourseGraph.build_from_umd_catalog(
                db, "Computer Science", requirements=reqs,
            )
        assert len(graph.courses) == 0
        assert any("empty course set" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_fallback_to_static_map_when_no_requirements(self):
        db = _StubDB({
            "CMSC": [_StubCourse("CMSC131", "CMSC", 4)],
            "MATH": [_StubCourse("MATH140", "MATH", 4)],
        })
        graph = await CourseGraph.build_from_umd_catalog(db, "Computer Science")
        assert "CMSC131" in graph.courses
