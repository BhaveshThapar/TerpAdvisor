"""
Multi-semester plan generator.

Uses the course DAG and degree audit to generate feasible multi-semester plans
that satisfy all degree requirements. Combines BFS-based course ordering with
credit-per-semester constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.engine.course_graph import CourseGraph
from app.engine.degree_audit import AuditResult, DegreeAuditor, DegreeRequirements


@dataclass
class SemesterPlan:
    """A single semester's course plan."""
    semester_number: int
    semester_label: str  # e.g., "Fall 2026"
    courses: list[str]
    total_credits: int


@dataclass
class MultiSemesterPlan:
    """A complete multi-semester graduation plan."""
    semesters: list[SemesterPlan]
    total_semesters: int
    total_credits: int
    all_courses: list[str]
    warnings: list[str] = field(default_factory=list)


class PlanGenerator:
    """Generates multi-semester plans using the course DAG and degree audit.

    Algorithm:
    1. Run degree audit to find remaining required courses
    2. Use topological sort on the subgraph of remaining courses
    3. Greedily assign courses to semesters respecting:
       - Prerequisites (topological order)
       - Credit limits per semester
       - Max courses per semester
    """

    def __init__(
        self,
        graph: CourseGraph,
        auditor: DegreeAuditor,
        credit_map: dict[str, int] | None = None,
    ):
        self.graph = graph
        self.auditor = auditor
        self.credit_map = credit_map or {}

    def generate_plan(
        self,
        completed_courses: dict[str, int],
        max_credits_per_semester: int = 16,
        max_courses_per_semester: int = 5,
        start_semester: str = "Fall 2026",
        prioritize: list[str] | None = None,
    ) -> MultiSemesterPlan:
        """Generate a multi-semester plan to complete remaining requirements.

        Args:
            completed_courses: course_id → credits for courses already done
            max_credits_per_semester: Credit cap per semester
            max_courses_per_semester: Course count cap per semester
            start_semester: Label for the first planned semester
            prioritize: Course IDs to schedule as early as possible
        """
        # 1. Run audit to find what's needed
        audit = self.auditor.audit(completed_courses)
        remaining = set(audit.courses_remaining)

        if not remaining:
            return MultiSemesterPlan(
                semesters=[], total_semesters=0, total_credits=0, all_courses=[],
                warnings=["All requirements satisfied — no courses remaining!"],
            )

        # 2. Get topologically-valid ordering for remaining courses.
        # Courses not in the prerequisite graph (GenEds, free electives, etc.) are
        # appended after the topological order so they are still scheduled.
        remaining_in_graph = remaining & set(self.graph.courses)
        remaining_not_in_graph = remaining - remaining_in_graph
        completed_set = set(completed_courses.keys())

        ordered = self._topological_order_remaining(remaining_in_graph, completed_set)
        ordered += sorted(remaining_not_in_graph)

        # 3. Boost prioritized courses
        if prioritize:
            priority_set = set(prioritize) & set(ordered)
            ordered = [c for c in ordered if c in priority_set] + [
                c for c in ordered if c not in priority_set
            ]

        # 4. Greedily assign to semesters
        semesters: list[SemesterPlan] = []
        assigned: set[str] = set()
        semester_labels = self._generate_semester_labels(start_semester, 12)

        for sem_idx in range(12):  # Max 12 semesters (safety)
            if not (set(ordered) - assigned):
                break

            sem_courses: list[str] = []
            sem_credits = 0

            for course_id in ordered:
                if course_id in assigned:
                    continue

                credits = self.credit_map.get(course_id, 3)

                # Check constraints
                if len(sem_courses) >= max_courses_per_semester:
                    break
                if sem_credits + credits > max_credits_per_semester:
                    continue

                # Check that all prereqs are completed or assigned in earlier semesters
                prereqs = self.graph.get_all_prerequisites(course_id)
                prereqs_met = prereqs.issubset(completed_set | assigned)
                if not prereqs_met:
                    continue

                sem_courses.append(course_id)
                sem_credits += credits

            if not sem_courses:
                # Nothing fit this semester — check whether we're truly stuck (all
                # remaining courses have unsatisfied prereqs) or just full on credits.
                # Either way, advance to the next semester rather than aborting.
                unassigned_remaining = set(ordered) - assigned
                if not unassigned_remaining:
                    break
                # Check if any unassigned course could ever become schedulable
                # (i.e., its prereqs will eventually be met as we assign more).
                # If none could ever be scheduled, stop to avoid infinite loop.
                can_progress = any(
                    self.graph.get_all_prerequisites(c).issubset(completed_set | set(ordered))
                    for c in unassigned_remaining
                    if c in self.graph.courses
                )
                if not can_progress and not (unassigned_remaining - set(self.graph.courses)):
                    # All remaining courses are in the graph with unsatisfiable prereqs
                    break
                continue

            for c in sem_courses:
                assigned.add(c)

            semesters.append(SemesterPlan(
                semester_number=sem_idx + 1,
                semester_label=semester_labels[sem_idx] if sem_idx < len(semester_labels) else f"Semester {sem_idx + 1}",
                courses=sem_courses,
                total_credits=sem_credits,
            ))

        # Warnings
        warnings = []
        unassigned = set(ordered) - assigned
        if unassigned:
            warnings.append(
                f"{len(unassigned)} courses could not be scheduled: {', '.join(sorted(unassigned)[:5])}"
            )

        all_planned = [c for s in semesters for c in s.courses]
        return MultiSemesterPlan(
            semesters=semesters,
            total_semesters=len(semesters),
            total_credits=sum(s.total_credits for s in semesters),
            all_courses=all_planned,
            warnings=warnings,
        )

    def _topological_order_remaining(
        self, remaining: set[str], completed: set[str]
    ) -> list[str]:
        """Get a topological ordering of remaining courses."""
        # Build subgraph of just remaining courses
        subgraph = CourseGraph()
        for cid in remaining:
            node = self.graph.get_course(cid)
            if node:
                subgraph.add_course(node)

        try:
            return subgraph.topological_sort()
        except ValueError:
            # If cycle detected, fall back to simple ordering
            return sorted(remaining)

    @staticmethod
    def _generate_semester_labels(start: str, count: int) -> list[str]:
        """Generate semester labels like 'Fall 2026', 'Spring 2027', etc."""
        parts = start.split()
        if len(parts) != 2:
            return [f"Semester {i+1}" for i in range(count)]

        season, year_str = parts
        year = int(year_str)
        labels = []
        current_season = season

        for _ in range(count):
            labels.append(f"{current_season} {year}")
            if current_season == "Fall":
                current_season = "Spring"
                year += 1
            else:
                current_season = "Fall"

        return labels
