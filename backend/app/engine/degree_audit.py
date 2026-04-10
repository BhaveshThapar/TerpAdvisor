"""
Degree audit engine.

Maps a student's completed courses against their declared major's requirement tree
to compute progress, identify remaining requirements, and determine which courses
would make the most progress toward graduation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RequirementType(Enum):
    CORE = "core"              # Must take specific courses
    ELECTIVE = "elective"      # Choose N from a pool
    GENED = "gened"            # General education categories
    CONCENTRATION = "concentration"  # Major-specific track


class RequirementStatus(Enum):
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    INCOMPLETE = "incomplete"


@dataclass
class Requirement:
    """A single degree requirement (e.g., 'Complete CMSC131 and CMSC132')."""
    id: str
    name: str
    type: RequirementType
    course_options: list[str]  # Course IDs that can satisfy this
    credits_needed: int
    courses_needed: int = 1    # How many courses from options to complete
    description: str = ""
    prefix_patterns: list[str] = field(default_factory=list)
    # e.g. ["CMSC4"] matches any course_id starting with "CMSC4" (i.e. CMSC 4xx)


@dataclass
class RequirementGroup:
    """A group of related requirements (e.g., 'Lower Level CS Requirements')."""
    id: str
    name: str
    requirements: list[Requirement] = field(default_factory=list)
    description: str = ""
    min_requirements_satisfied: int | None = None  # group is complete when N of M reqs are done
    counts_toward_total: bool = True  # whether this group's courses are conceptually distinct from others


@dataclass
class DegreeRequirements:
    """Complete requirement tree for a major."""
    major: str
    catalog_year: str
    track: str = "General"
    groups: list[RequirementGroup] = field(default_factory=list)
    total_credits_required: int = 120


@dataclass
class RequirementResult:
    """Audit result for a single requirement."""
    requirement: Requirement
    status: RequirementStatus
    completed_courses: list[str]
    remaining_options: list[str]
    credits_completed: int
    credits_remaining: int


@dataclass
class GroupResult:
    """Audit result for a requirement group."""
    group: RequirementGroup
    results: list[RequirementResult]
    completed_count: int
    total_count: int
    progress_pct: float
    expected_courses_remaining: int = 0
    counts_toward_total: bool = True


@dataclass
class AuditResult:
    """Complete degree audit result."""
    major: str
    catalog_year: str
    group_results: list[GroupResult]
    total_credits_completed: int
    total_credits_required: int
    overall_progress_pct: float
    courses_remaining: list[str]  # All courses that could still count toward degree
    total_courses_remaining: int = 0


class DegreeAuditor:
    """Audits a student's progress toward their degree requirements."""

    def __init__(self, requirements: DegreeRequirements):
        self.requirements = requirements

    def audit(
        self,
        completed_courses: dict[str, int],  # course_id → credits
        in_progress: set[str] | None = None,
        course_gen_eds: dict[str, list[str]] | None = None,
    ) -> AuditResult:
        """Run a full degree audit.

        Args:
            completed_courses: Map of course_id → credits earned
            in_progress: Set of course IDs currently being taken
            course_gen_eds: Map of course_id → list of GenEd codes (e.g. ["DSNS", "DVUP"])
        """
        in_progress = in_progress or set()
        completed_set = set(completed_courses.keys())
        group_results = []
        all_remaining: set[str] = set()
        total_credits_completed = 0

        for group in self.requirements.groups:
            group_result = self._audit_group(group, completed_set, completed_courses, in_progress, course_gen_eds)
            group_results.append(group_result)
            total_credits_completed += sum(r.credits_completed for r in group_result.results)
            for r in group_result.results:
                # Only surface remaining options for requirements that aren't done yet.
                # Adding options from COMPLETE requirements would inflate courses_remaining
                # and mislead the planner into scheduling unnecessary courses.
                if r.status != RequirementStatus.COMPLETE:
                    all_remaining.update(r.remaining_options)

        # Total credits earned is the sum of credits across all passed completed courses.
        # But we must only grab courses that the user actually completed. 
        total_credits_completed = sum(completed_courses.values())

        overall_pct = min(
            100.0,
            (total_credits_completed / self.requirements.total_credits_required * 100)
            if self.requirements.total_credits_required > 0
            else 0.0,
        )

        import math
        total_expected_from_groups = sum(
            g.expected_courses_remaining 
            for g in group_results 
            if g.counts_toward_total
        )
        overall_credits_short = max(0, self.requirements.total_credits_required - total_credits_completed)
        overall_courses_short = math.ceil(overall_credits_short / 3.0)
        total_courses_remaining = max(total_expected_from_groups, overall_courses_short)

        return AuditResult(
            major=self.requirements.major,
            catalog_year=self.requirements.catalog_year,
            group_results=group_results,
            total_credits_completed=total_credits_completed,
            total_credits_required=self.requirements.total_credits_required,
            overall_progress_pct=round(overall_pct, 1),
            courses_remaining=sorted(all_remaining - completed_set),
            total_courses_remaining=total_courses_remaining,
        )

    def _audit_group(
        self,
        group: RequirementGroup,
        completed: set[str],
        credit_map: dict[str, int],
        in_progress: set[str],
        course_gen_eds: dict[str, list[str]] | None = None,
    ) -> GroupResult:
        results = []
        completed_count = 0

        for req in group.requirements:
            result = self._audit_requirement(req, completed, credit_map, in_progress, course_gen_eds)
            results.append(result)
            if result.status == RequirementStatus.COMPLETE:
                completed_count += 1

        total = len(results)
        target = group.min_requirements_satisfied if group.min_requirements_satisfied is not None else total
        progress = min(100.0, (completed_count / target * 100)) if target > 0 else 0.0

        expected_courses = 0
        if completed_count < target:
            needed = target - completed_count
            req_needs = []
            for r in results:
                if r.status != RequirementStatus.COMPLETE:
                    short = r.requirement.courses_needed - len(r.completed_courses)
                    if short <= 0 and r.credits_remaining > 0:
                        short = 1
                    req_needs.append(max(0, short))
            req_needs.sort()
            expected_courses = sum(req_needs[:needed])

        return GroupResult(
            group=group,
            results=results,
            completed_count=completed_count,
            total_count=total,
            progress_pct=round(progress, 1),
            expected_courses_remaining=expected_courses,
            counts_toward_total=group.counts_toward_total,
        )

    def _audit_requirement(
        self,
        req: Requirement,
        completed: set[str],
        credit_map: dict[str, int],
        in_progress: set[str],
        course_gen_eds: dict[str, list[str]] | None = None,
    ) -> RequirementResult:
        # Start with the explicitly listed options
        all_matching: set[str] = set(req.course_options)

        # Expand via prefix patterns (e.g. "CMSC4" matches CMSC414, CMSC422, ...)
        if req.prefix_patterns:
            for cid in (completed | in_progress):
                if any(cid.startswith(p) for p in req.prefix_patterns):
                    all_matching.add(cid)

        # Expand GENED requirements via course gen_ed tag metadata
        if req.type == RequirementType.GENED and course_gen_eds:
            # E.g., req.id "gened_dsns_dsnl" -> ["DSNS", "DSNL"]
            gened_codes = [c.upper() for c in req.id.split("_")[1:]]
            for cid, tags in course_gen_eds.items():
                if any(t.upper() in gened_codes for t in tags):
                    all_matching.add(cid)

        completed_in_req = [c for c in all_matching if c in completed]
        in_progress_in_req = [c for c in all_matching if c in in_progress]
        # remaining only shows the static course_options list (not dynamic pattern matches)
        remaining = [c for c in req.course_options if c not in completed and c not in in_progress]

        credits_done = sum(credit_map.get(c, 0) for c in completed_in_req)
        credits_remaining = max(0, req.credits_needed - credits_done)

        # Determine status
        courses_satisfied = len(completed_in_req) >= req.courses_needed
        credits_satisfied = credits_done >= req.credits_needed

        if courses_satisfied and credits_satisfied:
            status = RequirementStatus.COMPLETE
        elif in_progress_in_req or completed_in_req:
            status = RequirementStatus.IN_PROGRESS
        else:
            status = RequirementStatus.INCOMPLETE

        return RequirementResult(
            requirement=req,
            status=status,
            completed_courses=completed_in_req,
            remaining_options=remaining,
            credits_completed=credits_done,
            credits_remaining=credits_remaining,
        )

    def get_highest_impact_courses(
        self,
        completed_courses: dict[str, int],
        available_courses: list[str],
        top_n: int = 10,
    ) -> list[tuple[str, int]]:
        """Find courses that satisfy the most unfulfilled requirements.

        Returns (course_id, requirement_count) sorted by impact descending.
        Useful for the recommendation engine's RequirementScorer.
        """
        completed_set = set(completed_courses.keys())
        impact: dict[str, int] = {}

        for group in self.requirements.groups:
            for req in group.requirements:
                # Skip already-completed requirements
                completed_in_req = [c for c in req.course_options if c in completed_set]
                if len(completed_in_req) >= req.courses_needed:
                    continue
                # Count how many unfulfilled requirements each available course satisfies
                for course_id in available_courses:
                    if course_id in req.course_options and course_id not in completed_set:
                        impact[course_id] = impact.get(course_id, 0) + 1

        ranked = sorted(impact.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_n]


# ──────────────────────────────────────────────
# CS Major Requirements (UMD)
# ──────────────────────────────────────────────

def build_cs_requirements(track: str = "General") -> DegreeRequirements:
    """Build the Computer Science B.S. degree requirements for UMD."""
    _LINEAR_ALGEBRA_TRACKS = ("Data Science", "Machine Learning", "Quantum Information")

    # Build track-specific upper_cs requirements
    _UPPER_ELECTIVE_OPTIONS = [
        "CMSC320", "CMSC330", "CMSC335", "CMSC389",
        "CMSC411", "CMSC412", "CMSC414", "CMSC416", "CMSC417",
        "CMSC420", "CMSC421", "CMSC422", "CMSC423",
        "CMSC424", "CMSC425", "CMSC426", "CMSC427",
        "CMSC430", "CMSC431", "CMSC433", "CMSC434", "CMSC435", "CMSC436",
        "CMSC451", "CMSC452", "CMSC454", "CMSC456", "CMSC457",
        "CMSC460", "CMSC466", "CMSC470", "CMSC471",
        "CMSC472", "CMSC473", "CMSC474", "CMSC475",
    ]

    if track == "Cybersecurity":
        upper_cs_reqs = [
            Requirement(
                id="cs_security_net", name="Computer Security (CMSC414)",
                type=RequirementType.CORE, course_options=["CMSC414"],
                credits_needed=3, courses_needed=1,
            ),
            Requirement(
                id="cs_security_crypto", name="Cryptology (CMSC456)",
                type=RequirementType.CORE, course_options=["CMSC456"],
                credits_needed=3, courses_needed=1,
            ),
            Requirement(
                id="cs_general_electives", name="Upper-Level CMSC Electives (2 courses)",
                type=RequirementType.ELECTIVE,
                course_options=_UPPER_ELECTIVE_OPTIONS,
                prefix_patterns=["CMSC38", "CMSC39", "CMSC4"],
                credits_needed=6, courses_needed=2,
                description="2 additional upper-level CMSC electives",
            ),
        ]
    elif track == "Data Science":
        upper_cs_reqs = [
            Requirement(
                id="cs_ds_data", name="Intro to Data Science (CMSC320)",
                type=RequirementType.CORE, course_options=["CMSC320"],
                credits_needed=3, courses_needed=1,
            ),
            Requirement(
                id="cs_ds_ml", name="Machine Learning (CMSC422)",
                type=RequirementType.CORE, course_options=["CMSC422"],
                credits_needed=3, courses_needed=1,
            ),
            Requirement(
                id="cs_ds_db", name="Database Design (CMSC424)",
                type=RequirementType.CORE, course_options=["CMSC424"],
                credits_needed=3, courses_needed=1,
            ),
        ]
    elif track == "Machine Learning":
        upper_cs_reqs = [
            Requirement(
                id="cs_ml_data", name="Intro to Data Science (CMSC320)",
                type=RequirementType.CORE, course_options=["CMSC320"],
                credits_needed=3, courses_needed=1,
            ),
            Requirement(
                id="cs_ml_ai", name="Artificial Intelligence (CMSC421)",
                type=RequirementType.CORE, course_options=["CMSC421"],
                credits_needed=3, courses_needed=1,
            ),
            Requirement(
                id="cs_ml_ml", name="Machine Learning (CMSC422)",
                type=RequirementType.CORE, course_options=["CMSC422"],
                credits_needed=3, courses_needed=1,
            ),
        ]
    elif track == "Quantum Information":
        upper_cs_reqs = [
            Requirement(
                id="cs_qi_quantum", name="Quantum Computing (CMSC457)",
                type=RequirementType.CORE, course_options=["CMSC457"],
                credits_needed=3, courses_needed=1,
            ),
            Requirement(
                id="cs_general_electives", name="Upper-Level CMSC Electives (2 courses)",
                type=RequirementType.ELECTIVE,
                course_options=_UPPER_ELECTIVE_OPTIONS,
                prefix_patterns=["CMSC38", "CMSC39", "CMSC4"],
                credits_needed=6, courses_needed=2,
                description="2 additional upper-level CMSC electives",
            ),
        ]
    else:
        # General track
        upper_cs_reqs = [
            Requirement(
                id="cs_general_electives", name="Upper-Level CMSC Electives (2 courses)",
                type=RequirementType.ELECTIVE,
                course_options=_UPPER_ELECTIVE_OPTIONS,
                prefix_patterns=["CMSC38", "CMSC39", "CMSC4"],
                credits_needed=6, courses_needed=2,
                description="2 additional upper-level CMSC electives",
            ),
        ]

    # Math requirements differ by track
    math_reqs = [
        Requirement(
            id="math_calc1", name="Calculus I",
            type=RequirementType.CORE,
            course_options=["MATH140"],
            credits_needed=4, courses_needed=1,
        ),
        Requirement(
            id="math_calc2", name="Calculus II",
            type=RequirementType.CORE,
            course_options=["MATH141"],
            credits_needed=4, courses_needed=1,
        ),
        Requirement(
            id="math_stats", name="Statistics",
            type=RequirementType.CORE,
            course_options=["STAT400"],
            credits_needed=3, courses_needed=1,
        ),
    ]
    if track in _LINEAR_ALGEBRA_TRACKS:
        math_reqs.insert(2, Requirement(
            id="math_linear", name="Linear Algebra",
            type=RequirementType.CORE,
            course_options=["MATH240", "MATH461"],
            credits_needed=3, courses_needed=1,
        ))
    else:
        # General/Cybersecurity: one additional MATH or STAT elective (300/400-level)
        math_reqs.append(Requirement(
            id="math_elective", name="Additional Math/Stat Elective",
            type=RequirementType.ELECTIVE,
            course_options=["MATH241", "MATH246", "MATH340", "MATH401", "MATH403",
                            "MATH406", "MATH410", "MATH411", "MATH412", "MATH416",
                            "MATH420", "MATH424", "MATH430", "MATH431", "MATH432",
                            "MATH461", "MATH240", "STAT401", "STAT410", "STAT420"],
            prefix_patterns=["MATH3", "MATH4", "STAT4"],
            credits_needed=3, courses_needed=1,
            description="One additional MATH or STAT course (300/400-level, not cross-listed with CMSC)",
        ))

    cs = DegreeRequirements(
        major="Computer Science",
        catalog_year="2024-2025",
        total_credits_required=120,
        groups=[
            RequirementGroup(
                id="lower_cs",
                name="Lower-Level CS Requirements",
                requirements=[
                    Requirement(
                        id="cs_intro_1", name="Intro to CS I",
                        type=RequirementType.CORE,
                        course_options=["CMSC131"],
                        credits_needed=4, courses_needed=1,
                    ),
                    Requirement(
                        id="cs_intro_2", name="Intro to CS II",
                        type=RequirementType.CORE,
                        course_options=["CMSC132"],
                        credits_needed=4, courses_needed=1,
                    ),
                    Requirement(
                        id="cs_discrete", name="Discrete Structures",
                        type=RequirementType.CORE,
                        course_options=["CMSC250"],
                        credits_needed=4, courses_needed=1,
                    ),
                    Requirement(
                        id="cs_org", name="Computer Organization",
                        type=RequirementType.CORE,
                        course_options=["CMSC216"],
                        credits_needed=4, courses_needed=1,
                    ),
                    Requirement(
                        id="cs_org_lang", name="Organization of Programming Languages",
                        type=RequirementType.CORE,
                        course_options=["CMSC330"],
                        credits_needed=3, courses_needed=1,
                    ),
                    Requirement(
                        id="cs_algorithms", name="Algorithms",
                        type=RequirementType.CORE,
                        course_options=["CMSC351"],
                        credits_needed=3, courses_needed=1,
                    ),
                ],
            ),
            RequirementGroup(
                id="upper_cs",
                name="Upper-Level CS Requirements",
                requirements=upper_cs_reqs,
            ),
            RequirementGroup(
                id="cs_areas",
                name="CS Upper-Level Areas (at least 3 of 5)",
                min_requirements_satisfied=3,
                description="Complete at least 1 course in 3 of the 5 upper-level CS areas",
                requirements=[
                    Requirement(
                        id="cs_area1", name="Area 1: Systems",
                        type=RequirementType.ELECTIVE,
                        course_options=["CMSC411", "CMSC412", "CMSC414", "CMSC416", "CMSC417"],
                        credits_needed=3, courses_needed=1,
                        description="Computer systems and networks",
                    ),
                    Requirement(
                        id="cs_area2", name="Area 2: Information Processing",
                        type=RequirementType.ELECTIVE,
                        course_options=["CMSC420", "CMSC421", "CMSC422", "CMSC423",
                                        "CMSC424", "CMSC425", "CMSC426", "CMSC427",
                                        "CMSC470", "CMSC471", "CMSC472"],
                        credits_needed=3, courses_needed=1,
                        description="Data, AI, databases, and graphics",
                    ),
                    Requirement(
                        id="cs_area3", name="Area 3: Software Engineering & PL",
                        type=RequirementType.ELECTIVE,
                        course_options=["CMSC430", "CMSC431", "CMSC433", "CMSC434", "CMSC435", "CMSC436"],
                        credits_needed=3, courses_needed=1,
                        description="Programming languages, compilers, and SE",
                    ),
                    Requirement(
                        id="cs_area4", name="Area 4: Theory",
                        type=RequirementType.ELECTIVE,
                        course_options=["CMSC451", "CMSC452", "CMSC454", "CMSC456", "CMSC457", "CMSC474"],
                        credits_needed=3, courses_needed=1,
                        description="Algorithms, cryptography, complexity, and quantum",
                    ),
                    Requirement(
                        id="cs_area5", name="Area 5: Numerical & Scientific Computing",
                        type=RequirementType.ELECTIVE,
                        course_options=["CMSC460", "CMSC466"],
                        credits_needed=3, courses_needed=1,
                        description="Numerical methods and scientific computing",
                    ),
                ],
            ),
            RequirementGroup(
                id="math",
                name="Mathematics Requirements",
                requirements=math_reqs,
            ),
            RequirementGroup(
                id="cs_400_level",
                name="400-Level CMSC Requirement",
                description="5 total CMSC 400-level courses required for the CS B.S.",
                counts_toward_total=False,  # these overlap fully with upper_cs and cs_areas
                requirements=[
                    Requirement(
                        id="cs_400_total",
                        name="Five 400-Level CMSC Courses",
                        type=RequirementType.ELECTIVE,
                        course_options=[],
                        prefix_patterns=["CMSC4"],
                        credits_needed=15,
                        courses_needed=5,
                        description="5 CMSC 400-level courses required (3 credits × 5)",
                    ),
                ],
            ),
            RequirementGroup(
                id="ulc",
                name="Upper-Level Concentration (ULC)",
                description="12 credits from an approved external discipline or declared minor",
                requirements=[
                    Requirement(
                        id="ulc_credits",
                        name="ULC – 12 Credits External Discipline",
                        type=RequirementType.CONCENTRATION,
                        course_options=[],
                        prefix_patterns=[],  # populated at audit time from selected discipline
                        credits_needed=12,
                        courses_needed=4,
                        description="12 credits from an approved external discipline. A declared minor fulfills this.",
                    ),
                ],
            ),
            RequirementGroup(
                id="gen_ed",
                name="General Education Requirements",
                requirements=[
                    Requirement(
                        id="gened_fsaw", name="Academic Writing (FSAW)",
                        type=RequirementType.GENED, course_options=["ENGL101"], credits_needed=3, courses_needed=1,
                    ),
                    Requirement(
                        id="gened_fspw", name="Professional Writing (FSPW)",
                        type=RequirementType.GENED, course_options=["ENGL390", "ENGL391", "ENGL392", "ENGL393", "ENGL394", "ENGL395"], credits_needed=3, courses_needed=1,
                    ),
                    Requirement(
                        id="gened_dsns_dsnl", name="Natural Sciences (DSNS/DSNL)",
                        type=RequirementType.GENED, course_options=["BSCI170", "CHEM131", "ASTR100", "ASTR101", "PHYS161", "GEOL100"], credits_needed=6, courses_needed=2,
                        description="Two natural science courses (at least one with lab)",
                    ),
                    Requirement(
                        id="gened_dshu", name="Humanities (DSHU)",
                        type=RequirementType.GENED, course_options=["PHIL100", "HIST200", "ARTH200", "MUSC210", "ENGL201"], credits_needed=6, courses_needed=2,
                    ),
                    Requirement(
                        id="gened_dshs", name="History & Social Sciences (DSHS)",
                        type=RequirementType.GENED, course_options=["ECON200", "ECON201", "PSYC100", "GVPT170", "SOCY100"], credits_needed=6, courses_needed=2,
                    ),
                    Requirement(
                        id="gened_dvup_dvcc", name="Diversity (DVUP/DVCC)",
                        type=RequirementType.GENED, course_options=["AASP100", "ANTH222", "SOCY105"], credits_needed=3, courses_needed=1,
                    ),
                    Requirement(
                        id="gened_scis", name="Scholarship in Practice (SCIS)",
                        type=RequirementType.GENED, course_options=["ENES101", "INST201", "JOUR175", "CMSC122"], credits_needed=6, courses_needed=2,
                    ),
                ],
            ),
        ],
    )
    # Filter out None requirements from conditionally skipped list
    for group in cs.groups:
        group.requirements = [r for r in group.requirements if r is not None]
    
    return cs


def build_math_requirements() -> DegreeRequirements:
    """Build the Mathematics B.S. degree requirements for UMD."""
    return DegreeRequirements(
        major="Mathematics",
        catalog_year="2024-2025",
        total_credits_required=120,
        groups=[
            RequirementGroup(
                id="math_core",
                name="Core Mathematics",
                requirements=[
                    Requirement(id="m_calc1", name="Calculus I", type=RequirementType.CORE,
                                course_options=["MATH140"], credits_needed=4),
                    Requirement(id="m_calc2", name="Calculus II", type=RequirementType.CORE,
                                course_options=["MATH141"], credits_needed=4),
                    Requirement(id="m_calc3", name="Calculus III", type=RequirementType.CORE,
                                course_options=["MATH241"], credits_needed=4),
                    Requirement(id="m_diffeq", name="Differential Equations", type=RequirementType.CORE,
                                course_options=["MATH246"], credits_needed=3),
                    Requirement(id="m_linalg", name="Linear Algebra", type=RequirementType.CORE,
                                course_options=["MATH240", "MATH461"], credits_needed=4),
                    Requirement(id="m_analysis", name="Introduction to Analysis", type=RequirementType.CORE,
                                course_options=["MATH410"], credits_needed=3),
                    Requirement(id="m_algebra", name="Abstract Algebra", type=RequirementType.CORE,
                                course_options=["MATH403"], credits_needed=3),
                ],
            ),
            RequirementGroup(
                id="math_upper",
                name="Upper-Level Math Electives",
                requirements=[
                    Requirement(
                        id="m_electives", name="Math Electives (4 courses)",
                        type=RequirementType.ELECTIVE,
                        course_options=[
                            "MATH401", "MATH402", "MATH404", "MATH405", "MATH406",
                            "MATH411", "MATH414", "MATH420", "MATH430", "MATH431",
                            "MATH432", "MATH436", "MATH445", "MATH446", "MATH452",
                            "MATH456", "MATH462", "MATH463", "STAT400", "STAT401",
                        ],
                        credits_needed=12, courses_needed=4,
                        description="Choose 4 upper-level math electives (400-level)",
                    ),
                ],
            ),
            RequirementGroup(
                id="math_gened",
                name="General Education Requirements",
                requirements=[
                    Requirement(id="mg_dsns", name="Natural Sciences (DSNS)", type=RequirementType.GENED,
                                course_options=["PHYS161", "PHYS171", "CHEM131", "CHEM135",
                                                "BSCI170", "BSCI171", "GEOL100", "ASTR101"],
                                credits_needed=7, courses_needed=2),
                    Requirement(id="mg_dshu", name="Humanities (DSHU)", type=RequirementType.GENED,
                                course_options=["ENGL101", "PHIL100", "HIST200", "ARTH200",
                                                "MUSC210", "THET110"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="mg_dshs", name="History & Social Sciences (DSHS)", type=RequirementType.GENED,
                                course_options=["ECON200", "PSYC100", "SOCY100", "GVPT100", "ANTH222"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="mg_dvup", name="Understanding Plural Societies (DVUP)", type=RequirementType.GENED,
                                course_options=["AASP100", "AMST298", "WMST250"],
                                credits_needed=3, courses_needed=1),
                ],
            ),
        ],
    )


def build_infosci_requirements() -> DegreeRequirements:
    """Build the Information Science B.S. degree requirements for UMD."""
    return DegreeRequirements(
        major="Information Science",
        catalog_year="2024-2025",
        total_credits_required=120,
        groups=[
            RequirementGroup(
                id="inst_core",
                name="Core Information Science",
                requirements=[
                    Requirement(id="i_intro", name="Introduction to Information Science", type=RequirementType.CORE,
                                course_options=["INST126"], credits_needed=3),
                    Requirement(id="i_tic", name="Object-Oriented Programming", type=RequirementType.CORE,
                                course_options=["INST201"], credits_needed=3),
                    Requirement(id="i_inforg", name="Information Organization", type=RequirementType.CORE,
                                course_options=["INST311"], credits_needed=3),
                    Requirement(id="i_intic", name="Information Architecture", type=RequirementType.CORE,
                                course_options=["INST362"], credits_needed=3),
                    Requirement(id="i_data", name="Data Science", type=RequirementType.CORE,
                                course_options=["INST314"], credits_needed=3),
                    Requirement(id="i_hci", name="Human-Computer Interaction", type=RequirementType.CORE,
                                course_options=["INST352"], credits_needed=3),
                    Requirement(id="i_stats", name="Statistics for Info Science", type=RequirementType.CORE,
                                course_options=["INST314", "STAT100"], credits_needed=3),
                    Requirement(id="i_capstone", name="Capstone", type=RequirementType.CORE,
                                course_options=["INST490"], credits_needed=3),
                ],
            ),
            RequirementGroup(
                id="inst_electives",
                name="Information Science Electives",
                requirements=[
                    Requirement(
                        id="i_electives", name="INST Electives (3 courses)",
                        type=RequirementType.ELECTIVE,
                        course_options=[
                            "INST327", "INST335", "INST346", "INST354",
                            "INST377", "INST408", "INST414", "INST447",
                            "INST462", "INST466", "INST490",
                        ],
                        credits_needed=9, courses_needed=3,
                    ),
                ],
            ),
            RequirementGroup(
                id="inst_gened",
                name="General Education Requirements",
                requirements=[
                    Requirement(id="ig_dsns", name="Natural Sciences (DSNS)", type=RequirementType.GENED,
                                course_options=["PHYS161", "PHYS171", "CHEM131", "BSCI170", "GEOL100"],
                                credits_needed=7, courses_needed=2),
                    Requirement(id="ig_dshu", name="Humanities (DSHU)", type=RequirementType.GENED,
                                course_options=["ENGL101", "PHIL100", "HIST200", "ARTH200"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="ig_dshs", name="History & Social Sciences (DSHS)", type=RequirementType.GENED,
                                course_options=["ECON200", "PSYC100", "SOCY100", "GVPT100"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="ig_dvup", name="Understanding Plural Societies (DVUP)", type=RequirementType.GENED,
                                course_options=["AASP100", "AMST298", "WMST250"],
                                credits_needed=3, courses_needed=1),
                ],
            ),
        ],
    )


def build_econ_requirements() -> DegreeRequirements:
    """Build the Economics B.A. degree requirements for UMD."""
    return DegreeRequirements(
        major="Economics",
        catalog_year="2024-2025",
        total_credits_required=120,
        groups=[
            RequirementGroup(
                id="econ_core",
                name="Core Economics",
                requirements=[
                    Requirement(id="e_micro", name="Principles of Microeconomics", type=RequirementType.CORE,
                                course_options=["ECON200"], credits_needed=3),
                    Requirement(id="e_macro", name="Principles of Macroeconomics", type=RequirementType.CORE,
                                course_options=["ECON201"], credits_needed=3),
                    Requirement(id="e_inter_micro", name="Intermediate Microeconomics", type=RequirementType.CORE,
                                course_options=["ECON300"], credits_needed=3),
                    Requirement(id="e_inter_macro", name="Intermediate Macroeconomics", type=RequirementType.CORE,
                                course_options=["ECON301"], credits_needed=3),
                    Requirement(id="e_stats", name="Statistics for Economics", type=RequirementType.CORE,
                                course_options=["ECON305", "STAT400"], credits_needed=3),
                ],
            ),
            RequirementGroup(
                id="econ_math",
                name="Mathematics Requirements",
                requirements=[
                    Requirement(id="em_calc1", name="Calculus I", type=RequirementType.CORE,
                                course_options=["MATH140"], credits_needed=4),
                    Requirement(id="em_calc2", name="Calculus II", type=RequirementType.CORE,
                                course_options=["MATH141"], credits_needed=4),
                ],
            ),
            RequirementGroup(
                id="econ_electives",
                name="Economics Electives",
                requirements=[
                    Requirement(
                        id="e_electives", name="ECON Electives (4 courses)",
                        type=RequirementType.ELECTIVE,
                        course_options=[
                            "ECON311", "ECON315", "ECON321", "ECON325",
                            "ECON330", "ECON340", "ECON350", "ECON355",
                            "ECON370", "ECON381", "ECON385", "ECON390",
                            "ECON406", "ECON411", "ECON412", "ECON415",
                            "ECON420", "ECON422", "ECON423", "ECON424",
                        ],
                        credits_needed=12, courses_needed=4,
                    ),
                ],
            ),
            RequirementGroup(
                id="econ_gened",
                name="General Education Requirements",
                requirements=[
                    Requirement(id="eg_dsns", name="Natural Sciences (DSNS)", type=RequirementType.GENED,
                                course_options=["PHYS161", "PHYS171", "CHEM131", "BSCI170", "GEOL100"],
                                credits_needed=7, courses_needed=2),
                    Requirement(id="eg_dshu", name="Humanities (DSHU)", type=RequirementType.GENED,
                                course_options=["ENGL101", "PHIL100", "HIST200", "ARTH200"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="eg_dvup", name="Understanding Plural Societies (DVUP)", type=RequirementType.GENED,
                                course_options=["AASP100", "AMST298", "WMST250"],
                                credits_needed=3, courses_needed=1),
                ],
            ),
        ],
    )


def build_biology_requirements() -> DegreeRequirements:
    """Build the Biological Sciences B.S. degree requirements for UMD."""
    return DegreeRequirements(
        major="Biological Sciences",
        catalog_year="2024-2025",
        total_credits_required=120,
        groups=[
            RequirementGroup(
                id="bio_core",
                name="Core Biology",
                requirements=[
                    Requirement(id="b_cell", name="Cell Biology and Genetics", type=RequirementType.CORE,
                                course_options=["BSCI170"], credits_needed=4),
                    Requirement(id="b_ecology", name="Ecology and Evolution", type=RequirementType.CORE,
                                course_options=["BSCI171"], credits_needed=3),
                    Requirement(id="b_genetics", name="Genetics", type=RequirementType.CORE,
                                course_options=["BSCI222"], credits_needed=3),
                    Requirement(id="b_cellbio", name="Molecular Cell Biology", type=RequirementType.CORE,
                                course_options=["BSCI330"], credits_needed=3),
                    Requirement(id="b_ecology2", name="General Ecology", type=RequirementType.CORE,
                                course_options=["BSCI340"], credits_needed=3),
                    Requirement(id="b_biochem", name="Biochemistry", type=RequirementType.CORE,
                                course_options=["BCHM461", "BCHM462"], credits_needed=3),
                ],
            ),
            RequirementGroup(
                id="bio_chem_phys",
                name="Chemistry and Physics Requirements",
                requirements=[
                    Requirement(id="bc_chem1", name="General Chemistry I", type=RequirementType.CORE,
                                course_options=["CHEM131"], credits_needed=3),
                    Requirement(id="bc_chem2", name="General Chemistry II", type=RequirementType.CORE,
                                course_options=["CHEM132"], credits_needed=3),
                    Requirement(id="bc_ochem1", name="Organic Chemistry I", type=RequirementType.CORE,
                                course_options=["CHEM231"], credits_needed=3),
                    Requirement(id="bc_ochem2", name="Organic Chemistry II", type=RequirementType.CORE,
                                course_options=["CHEM232"], credits_needed=3),
                    Requirement(id="bc_phys1", name="Physics I", type=RequirementType.CORE,
                                course_options=["PHYS161", "PHYS171"], credits_needed=3),
                    Requirement(id="bc_phys2", name="Physics II", type=RequirementType.CORE,
                                course_options=["PHYS162", "PHYS172"], credits_needed=3),
                ],
            ),
            RequirementGroup(
                id="bio_math",
                name="Mathematics Requirements",
                requirements=[
                    Requirement(id="bm_calc1", name="Calculus I", type=RequirementType.CORE,
                                course_options=["MATH140"], credits_needed=4),
                    Requirement(id="bm_calc2", name="Calculus II", type=RequirementType.CORE,
                                course_options=["MATH141"], credits_needed=4),
                    Requirement(id="bm_stats", name="Biostatistics", type=RequirementType.CORE,
                                course_options=["STAT100", "STAT400", "BIOM301"], credits_needed=3),
                ],
            ),
            RequirementGroup(
                id="bio_electives",
                name="Biology Electives",
                requirements=[
                    Requirement(
                        id="b_electives", name="Biology Electives (3 courses)",
                        type=RequirementType.ELECTIVE,
                        course_options=[
                            "BSCI338", "BSCI339", "BSCI353", "BSCI361",
                            "BSCI370", "BSCI402", "BSCI410", "BSCI411",
                            "BSCI413", "BSCI415", "BSCI416", "BSCI417",
                            "BSCI422", "BSCI430", "BSCI440", "BSCI447",
                        ],
                        credits_needed=9, courses_needed=3,
                    ),
                ],
            ),
            RequirementGroup(
                id="bio_gened",
                name="General Education Requirements",
                requirements=[
                    Requirement(id="bg_dshu", name="Humanities (DSHU)", type=RequirementType.GENED,
                                course_options=["ENGL101", "PHIL100", "HIST200", "ARTH200"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="bg_dshs", name="History & Social Sciences (DSHS)", type=RequirementType.GENED,
                                course_options=["ECON200", "PSYC100", "SOCY100", "GVPT100"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="bg_dvup", name="Understanding Plural Societies (DVUP)", type=RequirementType.GENED,
                                course_options=["AASP100", "AMST298", "WMST250"],
                                credits_needed=3, courses_needed=1),
                ],
            ),
        ],
    )


def build_engineering_requirements() -> DegreeRequirements:
    """Build the Mechanical Engineering B.S. degree requirements for UMD."""
    return DegreeRequirements(
        major="Mechanical Engineering",
        catalog_year="2024-2025",
        total_credits_required=120,
        groups=[
            RequirementGroup(
                id="engr_core",
                name="Core Engineering",
                requirements=[
                    Requirement(id="en_intro", name="Introduction to Engineering", type=RequirementType.CORE,
                                course_options=["ENES100"], credits_needed=3),
                    Requirement(id="en_statics", name="Statics", type=RequirementType.CORE,
                                course_options=["ENES102"], credits_needed=3),
                    Requirement(id="en_dynamics", name="Dynamics", type=RequirementType.CORE,
                                course_options=["ENME271"], credits_needed=3),
                    Requirement(id="en_thermo", name="Thermodynamics", type=RequirementType.CORE,
                                course_options=["ENME232"], credits_needed=3),
                    Requirement(id="en_fluids", name="Fluid Mechanics", type=RequirementType.CORE,
                                course_options=["ENME331"], credits_needed=3),
                    Requirement(id="en_heat", name="Heat Transfer", type=RequirementType.CORE,
                                course_options=["ENME332"], credits_needed=3),
                    Requirement(id="en_materials", name="Materials Science", type=RequirementType.CORE,
                                course_options=["ENME382"], credits_needed=3),
                    Requirement(id="en_controls", name="Controls", type=RequirementType.CORE,
                                course_options=["ENME403"], credits_needed=3),
                    Requirement(id="en_design", name="Senior Design", type=RequirementType.CORE,
                                course_options=["ENME472"], credits_needed=3),
                ],
            ),
            RequirementGroup(
                id="engr_math_sci",
                name="Math and Science Requirements",
                requirements=[
                    Requirement(id="enm_calc1", name="Calculus I", type=RequirementType.CORE,
                                course_options=["MATH140"], credits_needed=4),
                    Requirement(id="enm_calc2", name="Calculus II", type=RequirementType.CORE,
                                course_options=["MATH141"], credits_needed=4),
                    Requirement(id="enm_calc3", name="Calculus III", type=RequirementType.CORE,
                                course_options=["MATH241"], credits_needed=4),
                    Requirement(id="enm_diffeq", name="Differential Equations", type=RequirementType.CORE,
                                course_options=["MATH246"], credits_needed=3),
                    Requirement(id="enm_phys1", name="Physics I", type=RequirementType.CORE,
                                course_options=["PHYS161", "PHYS171"], credits_needed=3),
                    Requirement(id="enm_phys2", name="Physics II", type=RequirementType.CORE,
                                course_options=["PHYS162", "PHYS172"], credits_needed=3),
                    Requirement(id="enm_chem", name="Chemistry", type=RequirementType.CORE,
                                course_options=["CHEM131", "CHEM135"], credits_needed=3),
                ],
            ),
            RequirementGroup(
                id="engr_electives",
                name="Engineering Electives",
                requirements=[
                    Requirement(
                        id="en_electives", name="Engineering Electives (3 courses)",
                        type=RequirementType.ELECTIVE,
                        course_options=[
                            "ENME400", "ENME414", "ENME416", "ENME423",
                            "ENME432", "ENME440", "ENME441", "ENME442",
                            "ENME444", "ENME470", "ENME474", "ENME489",
                        ],
                        credits_needed=9, courses_needed=3,
                    ),
                ],
            ),
            RequirementGroup(
                id="engr_gened",
                name="General Education Requirements",
                requirements=[
                    Requirement(id="eng_dshu", name="Humanities (DSHU)", type=RequirementType.GENED,
                                course_options=["ENGL101", "PHIL100", "HIST200", "ARTH200"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="eng_dshs", name="History & Social Sciences (DSHS)", type=RequirementType.GENED,
                                course_options=["ECON200", "PSYC100", "SOCY100", "GVPT100"],
                                credits_needed=6, courses_needed=2),
                    Requirement(id="eng_dvup", name="Understanding Plural Societies (DVUP)", type=RequirementType.GENED,
                                course_options=["AASP100", "AMST298", "WMST250"],
                                credits_needed=3, courses_needed=1),
                ],
            ),
        ],
    )


MAJOR_BUILDERS = {
    "Computer Science": build_cs_requirements,
    "Mathematics": build_math_requirements,
    "Information Science": build_infosci_requirements,
    "Economics": build_econ_requirements,
    "Biological Sciences": build_biology_requirements,
    "Mechanical Engineering": build_engineering_requirements,
}


def build_requirements_for_major(major: str, track: str = "General") -> DegreeRequirements:
    """Build degree requirements for the given major and track, falling back to CS."""
    builder = MAJOR_BUILDERS.get(major, build_cs_requirements)
    if builder == build_cs_requirements:
        return builder(track=track)
    return builder()
