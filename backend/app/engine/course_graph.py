"""
DAG-based course prerequisite engine.

Models all courses as nodes in a directed acyclic graph where edges represent
prerequisite relationships. Supports topological sorting, reachability queries,
and prerequisite validation.

Key algorithms:
- Topological sort (Kahn's algorithm) for valid course orderings
- BFS reachability to find all courses unlocked by completing a set
- Cycle detection via DFS to validate graph integrity
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class PrereqType(Enum):
    """How multiple prerequisites relate to each other."""
    ALL = "all"       # Must complete ALL listed prereqs (AND)
    ANY = "any"       # Must complete at least ONE (OR)
    COREQ = "coreq"  # Can be taken concurrently


@dataclass
class PrereqNode:
    """A node in a prerequisite expression tree.

    Prereqs can be nested: (CMSC131 AND MATH140) OR (CMSC133 AND MATH140)
    This tree structure handles arbitrary nesting.
    """
    type: PrereqType
    courses: list[str] = field(default_factory=list)
    children: list[PrereqNode] = field(default_factory=list)

    def is_satisfied(self, completed: set[str], in_progress: set[str] | None = None) -> bool:
        """Check if this prerequisite node is satisfied given completed courses."""
        in_progress = in_progress or set()
        available = completed | in_progress if self.type == PrereqType.COREQ else completed

        # Check direct course requirements
        course_results = [c in available for c in self.courses]
        # Check nested sub-requirements
        child_results = [child.is_satisfied(completed, in_progress) for child in self.children]
        all_results = course_results + child_results

        if not all_results:
            return True  # No requirements = satisfied

        if self.type in (PrereqType.ALL, PrereqType.COREQ):
            return all(all_results)
        else:  # ANY
            return any(all_results)


@dataclass
class CourseNode:
    """A course in the prerequisite graph."""
    course_id: str
    name: str = ""
    credits: int = 3
    department: str = ""
    prereqs: Optional[PrereqNode] = None


class CourseGraph:
    """Directed acyclic graph of course prerequisites.

    Nodes are courses, edges point from prerequisite → dependent course.
    If A is a prereq for B, there's an edge A → B (A must come before B).
    """

    def __init__(self):
        self._nodes: dict[str, CourseNode] = {}
        # Adjacency list: course_id → list of courses that depend on it
        self._dependents: dict[str, set[str]] = defaultdict(set)
        # Reverse adjacency: course_id → list of its prerequisites (direct edges only)
        self._prerequisites: dict[str, set[str]] = defaultdict(set)
        # Prereq expressions (for complex AND/OR logic)
        self._prereq_expressions: dict[str, PrereqNode] = {}

    def add_course(self, course: CourseNode) -> None:
        """Add a course node to the graph."""
        self._nodes[course.course_id] = course
        if course.prereqs:
            self._prereq_expressions[course.course_id] = course.prereqs
            self._index_prereq_edges(course.course_id, course.prereqs)

    def _index_prereq_edges(self, course_id: str, prereq: PrereqNode) -> None:
        """Recursively extract all prerequisite course IDs and build edge indices."""
        for prereq_course in prereq.courses:
            self._dependents[prereq_course].add(course_id)
            self._prerequisites[course_id].add(prereq_course)
        for child in prereq.children:
            self._index_prereq_edges(course_id, child)

    def get_course(self, course_id: str) -> Optional[CourseNode]:
        return self._nodes.get(course_id)

    @property
    def courses(self) -> list[str]:
        return list(self._nodes.keys())

    # ──────────────────────────────────────────────
    # Topological Sort (Kahn's Algorithm)
    # ──────────────────────────────────────────────

    def topological_sort(self) -> list[str]:
        """Return courses in a valid prerequisite ordering using Kahn's algorithm.

        Returns a list where for every edge (A → B), A appears before B.
        Raises ValueError if the graph contains a cycle.
        """
        in_degree: dict[str, int] = {cid: 0 for cid in self._nodes}
        for cid in self._nodes:
            in_degree[cid] = len(self._prerequisites[cid] & set(self._nodes.keys()))

        queue = deque(cid for cid, deg in in_degree.items() if deg == 0)
        result = []

        while queue:
            course = queue.popleft()
            result.append(course)
            for dependent in self._dependents[course]:
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(result) != len(self._nodes):
            cycle = self._find_cycle()
            raise ValueError(f"Prerequisite graph contains a cycle: {' → '.join(cycle)}")

        return result

    # ──────────────────────────────────────────────
    # Cycle Detection (DFS)
    # ──────────────────────────────────────────────

    def has_cycle(self) -> bool:
        """Check if the prerequisite graph contains any cycles."""
        return bool(self._find_cycle())

    def _find_cycle(self) -> list[str]:
        """Find a cycle in the graph using DFS. Returns the cycle path or empty list."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {cid: WHITE for cid in self._nodes}
        parent: dict[str, Optional[str]] = {cid: None for cid in self._nodes}

        def dfs(node: str) -> list[str]:
            color[node] = GRAY
            for dependent in self._dependents[node]:
                if dependent not in color:
                    continue
                if color[dependent] == GRAY:
                    # Found cycle — reconstruct it
                    cycle = [dependent, node]
                    current = node
                    while current != dependent and parent[current] is not None:
                        current = parent[current]
                        cycle.append(current)
                    return list(reversed(cycle))
                if color[dependent] == WHITE:
                    parent[dependent] = node
                    result = dfs(dependent)
                    if result:
                        return result
            color[node] = BLACK
            return []

        for cid in self._nodes:
            if color[cid] == WHITE:
                result = dfs(cid)
                if result:
                    return result
        return []

    # ──────────────────────────────────────────────
    # Reachability & Available Courses
    # ──────────────────────────────────────────────

    def get_available_courses(
        self, completed: set[str], in_progress: set[str] | None = None
    ) -> list[str]:
        """Find all courses the student can take given their completed coursework.

        A course is available if:
        1. It hasn't been completed yet
        2. It's not currently in progress
        3. All its prerequisites are satisfied
        """
        in_progress = in_progress or set()
        available = []

        for cid, node in self._nodes.items():
            if cid in completed or cid in in_progress:
                continue
            if self._is_prereq_satisfied(cid, completed, in_progress):
                available.append(cid)

        return available

    def _is_prereq_satisfied(
        self, course_id: str, completed: set[str], in_progress: set[str]
    ) -> bool:
        """Check if prerequisites for a course are satisfied."""
        expr = self._prereq_expressions.get(course_id)
        if expr is None:
            return True  # No prerequisites
        return expr.is_satisfied(completed, in_progress)

    def get_courses_unlocked_by(self, course_id: str, completed: set[str]) -> list[str]:
        """Find courses that become available after completing a specific course.

        Useful for showing students: "If you take X, you'll unlock Y and Z."
        """
        current_available = set(self.get_available_courses(completed))
        future_completed = completed | {course_id}
        future_available = set(self.get_available_courses(future_completed))
        return list(future_available - current_available - {course_id})

    # ──────────────────────────────────────────────
    # Path Finding
    # ──────────────────────────────────────────────

    def shortest_path_to(self, target: str, completed: set[str]) -> list[str]:
        """Find the shortest sequence of courses needed to reach a target course.

        Uses BFS on the reverse graph (from target back through prerequisites).
        Returns the path from first course to take → target.
        """
        if target in completed:
            return []
        if self._is_prereq_satisfied(target, completed, set()):
            return [target]

        # BFS backwards from target through prerequisites
        needed: set[str] = set()
        queue = deque([target])
        visited = {target}

        while queue:
            current = queue.popleft()
            needed.add(current)
            for prereq in self._prerequisites[current]:
                if prereq not in completed and prereq not in visited:
                    visited.add(prereq)
                    queue.append(prereq)

        # Topologically sort just the needed courses
        subgraph = CourseGraph()
        for cid in needed:
            if cid in self._nodes:
                subgraph.add_course(self._nodes[cid])

        try:
            return subgraph.topological_sort()
        except ValueError:
            return list(needed)  # Fallback if there's an issue

    def get_all_prerequisites(self, course_id: str) -> set[str]:
        """Get ALL prerequisites (transitive closure) for a course."""
        result: set[str] = set()
        queue = deque([course_id])
        visited = {course_id}

        while queue:
            current = queue.popleft()
            for prereq in self._prerequisites[current]:
                if prereq not in visited:
                    visited.add(prereq)
                    result.add(prereq)
                    queue.append(prereq)

        return result

    # ──────────────────────────────────────────────
    # Dynamic Graph Building from UMD Catalog
    # ──────────────────────────────────────────────

    @staticmethod
    async def build_from_umd_catalog(
        db: AsyncSession,
        major: str,
        requirements: "DegreeRequirements | None" = None,
    ) -> CourseGraph:
        """
        Build a CourseGraph dynamically from the database for a given major.

        If `requirements` is provided, the department list is derived from the
        course options and prefix patterns in the catalog — this is the
        preferred path and works for any major seeded in the `majors` table.
        Otherwise falls back to a hardcoded static map for back-compat.
        """
        from app.models import Course
        from app.engine.prerequisite_parser import parse_prerequisite_expression

        if requirements is not None:
            major_departments = CourseGraph._departments_from_requirements(requirements)
        else:
            major_departments = CourseGraph._get_departments_for_major(major)

        # Always include common gen-ed staples so planning can satisfy
        # non-major requirements pulled from catalog prefix patterns.
        major_departments = sorted(set(major_departments) | {"MATH", "STAT", "ENGL"})

        graph = CourseGraph()

        result = await db.execute(
            select(Course).where(Course.department.in_(major_departments))
        )
        courses = result.scalars().all()

        if not courses:
            logger.error(
                "build_from_umd_catalog: empty course set for major=%r depts=%s",
                major,
                major_departments,
            )

        # Parse and add each course to the graph
        for course in courses:
            # Parse prerequisites
            prereq_node = None
            if course.prerequisites_raw:
                try:
                    prereq_node = parse_prerequisite_expression(
                        course.prerequisites_raw
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to parse prerequisites for {course.course_id}: {e}"
                    )
                    prereq_node = None

            # Create CourseNode and add to graph
            course_node = CourseNode(
                course_id=course.course_id,
                name=course.name,
                credits=course.credits,
                department=course.department,
                prereqs=prereq_node,
            )
            graph.add_course(course_node)

        logger.info(
            f"Built dynamic graph for {major}: {len(graph.courses)} courses"
        )
        return graph

    @staticmethod
    def _departments_from_requirements(reqs: "DegreeRequirements") -> list[str]:
        """Extract department prefixes from a loaded DegreeRequirements tree."""
        depts: set[str] = set()
        for group in reqs.groups:
            for req in group.requirements:
                for cid in req.course_options:
                    prefix = "".join(c for c in cid if c.isalpha())
                    if prefix:
                        depts.add(prefix)
                for pat in req.prefix_patterns:
                    prefix = "".join(c for c in pat if c.isalpha())
                    if prefix:
                        depts.add(prefix)
        return sorted(depts)

    @staticmethod
    def _get_departments_for_major(major: str) -> list[str]:
        """
        Map a major to the departments whose courses count toward that degree.

        Returns a list of department codes (e.g., ["CMSC", "MATH", "STAT"]).
        If the major is not recognized, returns an empty list.

        This mapping is derived from UMD's official curriculum structure.
        It should be kept in sync with the degree requirements system.
        """
        # Normalize major name
        major_lower = major.lower()

        major_to_depts = {
            # Computer Science
            "computer science": ["CMSC", "MATH", "STAT", "ENGL", "INST"],
            # Information Science
            "information science": ["INST", "MATH", "STAT", "ENGL"],
            # Mathematics
            "mathematics": ["MATH", "STAT", "CMSC", "ENGL"],
            # Biological Sciences
            "biological sciences": ["BSCI", "CHEM", "MATH", "STAT", "PHYS", "ENGL"],
            # Economics
            "economics": ["ECON", "MATH", "STAT", "ENGL"],
            # Mechanical Engineering
            "mechanical engineering": ["ENME", "MATH", "PHYS", "CHEM", "ENGL"],
            # Add more majors as they're added to the system
            # This list will grow as degree requirements are implemented for each major
        }

        return major_to_depts.get(major_lower, [])
