"""Recommendation and degree audit API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.engine.course_graph import CourseGraph, CourseNode, PrereqNode, PrereqType
from app.engine.degree_audit import DegreeAuditor, build_cs_requirements, build_requirements_for_major
from app.engine.planner import PlanGenerator
from app.engine.recommender import RecommendationEngine
from app.engine.scorers.base import ScoringContext
from app.models import Course, Professor, Review
from app.schemas.schemas import (
    AuditRequest,
    AuditResponse,
    GroupResultResponse,
    MultiSemesterPlanResponse,
    PlanRequest,
    RecommendationFilters,
    RecommendationListResponse,
    RecommendationRequest,
    RecommendationResponse,
    RequirementResultResponse,
    SemesterPlanResponse,
)

router = APIRouter(prefix="/api", tags=["recommendations"])

_engine = RecommendationEngine()


def _build_cs_graph() -> CourseGraph:
    """Build the CS prerequisite DAG."""
    graph = CourseGraph()
    courses = [
        CourseNode("CMSC131", "Object-Oriented Programming I", 4, "CMSC"),
        CourseNode("CMSC132", "Object-Oriented Programming II", 4, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC131"])),
        CourseNode("CMSC216", "Introduction to Computer Systems", 4, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC132"])),
        CourseNode("CMSC250", "Discrete Structures", 4, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC131"])),
        CourseNode("CMSC320", "Introduction to Data Science", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC216", "CMSC250"])),
        CourseNode("CMSC330", "Organization of Programming Languages", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC216", "CMSC250"])),
        CourseNode("CMSC335", "Web Application Development", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC216"])),
        CourseNode("CMSC351", "Algorithms", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC250", "CMSC216"])),
        CourseNode("CMSC411", "Computer Systems Architecture", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330"])),
        CourseNode("CMSC412", "Operating Systems", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC414", "Computer and Network Security", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC417", "Computer Networks", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC351"])),
        CourseNode("CMSC420", "Advanced Data Structures", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC421", "Introduction to Artificial Intelligence", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC422", "Introduction to Machine Learning", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC320", "CMSC330", "CMSC351"])),
        CourseNode("CMSC424", "Database Design", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC430", "Introduction to Compilers", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC433", "Programming Language Technologies and Paradigms", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330"])),
        CourseNode("CMSC434", "Human-Computer Interaction", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330"])),
        CourseNode("CMSC435", "Software Engineering", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC451", "Design and Analysis of Computer Algorithms", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC351"])),
        CourseNode("CMSC456", "Cryptography", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC351"])),
        CourseNode("CMSC460", "Computational Methods", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC470", "Introduction to Natural Language Processing", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330", "CMSC351"])),
        CourseNode("CMSC471", "Introduction to Data Visualization", 3, "CMSC",
                   PrereqNode(PrereqType.ALL, ["CMSC330"])),
        CourseNode("MATH140", "Calculus I", 4, "MATH"),
        CourseNode("MATH141", "Calculus II", 4, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH140"])),
        CourseNode("MATH240", "Linear Algebra", 4, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("MATH241", "Calculus III", 4, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("MATH461", "Linear Algebra for Scientists and Engineers", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("STAT400", "Applied Probability and Statistics I", 3, "STAT",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("ENGL101", "Academic Writing", 3, "ENGL"),
        CourseNode("INST126", "Introduction to Information Science", 3, "INST"),
    ]
    for c in courses:
        graph.add_course(c)
    return graph


def _build_infosci_graph() -> CourseGraph:
    """Build the Information Science prerequisite DAG."""
    graph = CourseGraph()
    courses = [
        # Core INST sequence
        CourseNode("INST126", "Introduction to Information Science", 3, "INST"),
        CourseNode("INST201", "Object-Oriented Programming for Information Science", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST126"])),
        CourseNode("INST311", "Information Organization", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST201"])),
        CourseNode("INST314", "Data Science for Information Science", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST201"])),
        CourseNode("INST352", "Human-Computer Interaction", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST201"])),
        CourseNode("INST362", "Information Architecture", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST311"])),
        # Upper-level electives (no prereqs within graph — just need 201)
        CourseNode("INST327", "Information Privacy", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST201"])),
        CourseNode("INST335", "Information Policy", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST201"])),
        CourseNode("INST346", "Technologies for Information Services", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST201"])),
        CourseNode("INST354", "Decision-Making for Information Science", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST201"])),
        CourseNode("INST377", "Dynamic Web Applications", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST201"])),
        CourseNode("INST408", "Special Topics in Information Science", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST311"])),
        CourseNode("INST414", "Data Science Techniques", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST314"])),
        CourseNode("INST447", "Data Analytics", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST314"])),
        CourseNode("INST462", "User Experience Research", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST352"])),
        CourseNode("INST466", "Information Systems Design", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST362"])),
        CourseNode("INST490", "Capstone in Information Science", 3, "INST",
                   PrereqNode(PrereqType.ALL, ["INST362", "INST314"])),
        # Supporting courses
        CourseNode("STAT100", "Elementary Statistics and Probability", 3, "STAT"),
        CourseNode("MATH115", "Precalculus", 3, "MATH"),
        CourseNode("ENGL101", "Academic Writing", 3, "ENGL"),
        CourseNode("ENGL393", "Technical Writing", 3, "ENGL",
                   PrereqNode(PrereqType.ALL, ["ENGL101"])),
    ]
    for c in courses:
        graph.add_course(c)
    return graph


def _build_math_graph() -> CourseGraph:
    """Build the Mathematics prerequisite DAG."""
    graph = CourseGraph()
    courses = [
        CourseNode("MATH140", "Calculus I", 4, "MATH"),
        CourseNode("MATH141", "Calculus II", 4, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH140"])),
        CourseNode("MATH240", "Linear Algebra", 4, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("MATH241", "Calculus III", 4, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("MATH246", "Differential Equations", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("MATH310", "Introduction to Mathematical Proof", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("MATH401", "Applications of Linear Algebra", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH240", "MATH241"])),
        CourseNode("MATH403", "Introduction to Abstract Algebra", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH310"])),
        CourseNode("MATH405", "Linear Algebra", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH240", "MATH310"])),
        CourseNode("MATH410", "Advanced Calculus I", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH241", "MATH310"])),
        CourseNode("MATH411", "Advanced Calculus II", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH410"])),
        CourseNode("MATH416", "Applied Harmonic Analysis", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH240", "MATH241"])),
        CourseNode("MATH420", "Mathematical Modeling", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH240", "MATH246"])),
        CourseNode("MATH461", "Linear Algebra for Scientists and Engineers", 3, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("STAT400", "Applied Probability and Statistics I", 3, "STAT",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("STAT401", "Applied Probability and Statistics II", 3, "STAT",
                   PrereqNode(PrereqType.ALL, ["STAT400"])),
        CourseNode("CMSC131", "Object-Oriented Programming I", 4, "CMSC"),
        CourseNode("ENGL101", "Academic Writing", 3, "ENGL"),
    ]
    for c in courses:
        graph.add_course(c)
    return graph


def _build_biology_graph() -> CourseGraph:
    """Build the Biological Sciences prerequisite DAG."""
    graph = CourseGraph()
    courses = [
        CourseNode("BSCI105", "Principles of Biology I", 3, "BSCI"),
        CourseNode("BSCI106", "Principles of Biology II", 3, "BSCI",
                   PrereqNode(PrereqType.ALL, ["BSCI105"])),
        CourseNode("BSCI207", "Principles of Biology III", 3, "BSCI",
                   PrereqNode(PrereqType.ALL, ["BSCI106"])),
        CourseNode("BSCI222", "Principles of Genetics", 3, "BSCI",
                   PrereqNode(PrereqType.ALL, ["BSCI106"])),
        CourseNode("BSCI330", "Cell Biology and Physiology", 3, "BSCI",
                   PrereqNode(PrereqType.ALL, ["BSCI207", "BSCI222"])),
        CourseNode("BSCI338", "Animal Physiology", 3, "BSCI",
                   PrereqNode(PrereqType.ALL, ["BSCI330"])),
        CourseNode("BSCI440", "Developmental Biology", 3, "BSCI",
                   PrereqNode(PrereqType.ALL, ["BSCI330"])),
        CourseNode("BSCI424", "Biochemistry I", 3, "BSCI",
                   PrereqNode(PrereqType.ALL, ["BSCI207"])),
        CourseNode("CHEM131", "General Chemistry I", 3, "CHEM"),
        CourseNode("CHEM132", "General Chemistry II", 3, "CHEM",
                   PrereqNode(PrereqType.ALL, ["CHEM131"])),
        CourseNode("CHEM241", "Organic Chemistry I", 3, "CHEM",
                   PrereqNode(PrereqType.ALL, ["CHEM132"])),
        CourseNode("CHEM242", "Organic Chemistry II", 3, "CHEM",
                   PrereqNode(PrereqType.ALL, ["CHEM241"])),
        CourseNode("MATH140", "Calculus I", 4, "MATH"),
        CourseNode("MATH141", "Calculus II", 4, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH140"])),
        CourseNode("STAT100", "Elementary Statistics and Probability", 3, "STAT"),
        CourseNode("PHYS141", "General Physics: Mechanics and Particle Dynamics", 3, "PHYS",
                   PrereqNode(PrereqType.ALL, ["MATH140"])),
        CourseNode("PHYS142", "General Physics: Vibrations, Waves, Heat, Electricity, and Magnetism", 3, "PHYS",
                   PrereqNode(PrereqType.ALL, ["PHYS141"])),
        CourseNode("ENGL101", "Academic Writing", 3, "ENGL"),
    ]
    for c in courses:
        graph.add_course(c)
    return graph


def _build_econ_graph() -> CourseGraph:
    """Build the Economics prerequisite DAG."""
    graph = CourseGraph()
    courses = [
        CourseNode("ECON200", "Principles of Micro-Economics", 3, "ECON"),
        CourseNode("ECON201", "Principles of Macro-Economics", 3, "ECON"),
        CourseNode("ECON305", "Intermediate Macroeconomic Theory and Policy", 3, "ECON",
                   PrereqNode(PrereqType.ALL, ["ECON200", "ECON201"])),
        CourseNode("ECON306", "Intermediate Microeconomic Theory", 3, "ECON",
                   PrereqNode(PrereqType.ALL, ["ECON200", "ECON201"])),
        CourseNode("ECON321", "Principles of Econometrics", 3, "ECON",
                   PrereqNode(PrereqType.ALL, ["ECON306"])),
        CourseNode("ECON330", "Money and Banking", 3, "ECON",
                   PrereqNode(PrereqType.ALL, ["ECON305"])),
        CourseNode("ECON340", "International Economics", 3, "ECON",
                   PrereqNode(PrereqType.ALL, ["ECON305", "ECON306"])),
        CourseNode("ECON380", "Economics of the Public Sector", 3, "ECON",
                   PrereqNode(PrereqType.ALL, ["ECON306"])),
        CourseNode("ECON422", "Econometric Methods", 3, "ECON",
                   PrereqNode(PrereqType.ALL, ["ECON321"])),
        CourseNode("ECON430", "Industrial Organization", 3, "ECON",
                   PrereqNode(PrereqType.ALL, ["ECON306"])),
        CourseNode("MATH140", "Calculus I", 4, "MATH"),
        CourseNode("MATH141", "Calculus II", 4, "MATH",
                   PrereqNode(PrereqType.ALL, ["MATH140"])),
        CourseNode("STAT400", "Applied Probability and Statistics I", 3, "STAT",
                   PrereqNode(PrereqType.ALL, ["MATH141"])),
        CourseNode("ENGL101", "Academic Writing", 3, "ENGL"),
    ]
    for c in courses:
        graph.add_course(c)
    return graph


def _build_graph_for_major(major: str) -> CourseGraph:
    """Return the prerequisite DAG for the given major."""
    builders = {
        "Information Science": _build_infosci_graph,
        "Mathematics": _build_math_graph,
        "Biological Sciences": _build_biology_graph,
        "Economics": _build_econ_graph,
    }
    return builders.get(major, _build_cs_graph)()


async def _get_completed_credits(
    completed_course_ids: list[str],
    db: AsyncSession,
    credit_overrides: dict[str, int] | None = None,
) -> dict[str, int]:
    """Look up credits for a list of completed course IDs.

    credit_overrides takes precedence — use it to pass transcript-parsed credit
    values for courses that may not be in the DB or may have wrong DB values.
    """
    completed: dict[str, int] = {}
    for course_id in completed_course_ids:
        # Transcript-provided override is authoritative
        if credit_overrides and course_id in credit_overrides:
            completed[course_id] = credit_overrides[course_id]
            continue

        if course_id.startswith("TR_"):
            try:
                # Format: TR_<credits>_<name>
                credits = int(float(course_id.split("_")[1]))
                completed[course_id] = credits
                continue
            except (IndexError, ValueError):
                pass

        course_result = await db.execute(
            select(Course.credits).where(Course.course_id == course_id)
        )
        db_credits = course_result.scalar_one_or_none()
        # Use 0 rather than a 3-credit guess for courses absent from the DB.
        # The frontend should supply credit_overrides for such courses.
        completed[course_id] = db_credits if db_credits is not None else 0
    return completed


async def _build_scoring_context(
    db: AsyncSession, available: list[str], completed: set[str], major: str,
    requirement_impact: dict[str, int], weight_overrides: dict | None,
    preference_tags: list[str] | None = None,
) -> ScoringContext:
    """Build scoring context with real data from DB."""
    # Fetch course data
    course_data = {}
    if available:
        result = await db.execute(select(Course).where(Course.course_id.in_(available)))
        for c in result.scalars().all():
            course_data[c.course_id] = {"avg_gpa": c.avg_gpa, "sections": [], "professors": []}

    # Fetch professor data
    professor_data = {}
    prof_result = await db.execute(select(Professor))
    for p in prof_result.scalars().all():
        professor_data[p.name] = {
            "avg_rating": p.avg_rating, "review_count": p.review_count,
        }

    # Fetch review data for available courses
    review_data: dict[str, list] = {}
    if available:
        rev_result = await db.execute(
            select(Review).where(Review.course_id.in_(available))
        )
        for r in rev_result.scalars().all():
            review_data.setdefault(r.course_id, []).append(
                {"rating": r.rating, "text": r.text or ""}
            )

    return ScoringContext(
        user_id="current-user",
        completed_courses=completed,
        in_progress_courses=set(),
        major=major,
        course_data=course_data,
        professor_data=professor_data,
        review_data=review_data,
        grade_data={},
        requirement_impact=requirement_impact,
        selected_sections=[],
        weight_overrides=weight_overrides,
        preference_tags=preference_tags or [],
    )


def _apply_filters(
    available: list[str], filters: RecommendationFilters | None, course_data: dict,
) -> list[str]:
    """Apply user-specified filters to the candidate course list."""
    if not filters:
        return available

    filtered = available
    
    # Department filter
    if filters.departments:
        depts = {d.upper() for d in filters.departments}
        filtered = [c for c in filtered if (course_data.get(c, {}).get("department") or "").upper() in depts]
    
    # Level filter (e.g., 100, 200)
    if filters.levels:
        lvls = {str(lvl)[0] for lvl in filters.levels}
        filtered = [
            c for c in filtered
            if any(char.isdigit() and char in lvls for char in c)
        ]
        
    # GenEd filter
    if filters.gen_eds:
        gen_set = {g.upper() for g in filters.gen_eds}
        filtered = [
            c for c in filtered
            if gen_set & set(course_data.get(c, {}).get("gen_eds") or [])
        ]
        
    if filters.min_credits is not None:
        filtered = [c for c in filtered if course_data.get(c, {}).get("credits", 3) >= filters.min_credits]
        
    if filters.max_credits is not None:
        filtered = [c for c in filtered if course_data.get(c, {}).get("credits", 3) <= filters.max_credits]
        
    # GPA filter - Strict exclusion
    if filters.min_gpa is not None:
        filtered = [
            c for c in filtered
            if (course_data.get(c, {}).get("avg_gpa") or 0) >= filters.min_gpa
        ]
        
    # Exclusion list
    if filters.exclude_courses:
        excluded = {e.upper() for e in filters.exclude_courses}
        filtered = [c for c in filtered if c.upper() not in excluded]
        
    return filtered


@router.post("/recommendations", response_model=RecommendationListResponse)
async def get_recommendations(body: RecommendationRequest, db: AsyncSession = Depends(get_db)):
    """Get personalized course recommendations."""
    completed_credits = await _get_completed_credits(body.completed_courses, db)
    completed = set(completed_credits.keys())
    major = body.major or "Computer Science"

    graph = _build_graph_for_major(major)
    requirements = build_requirements_for_major(major)
    auditor = DegreeAuditor(requirements)

    available = graph.get_available_courses(completed)

    # Load course metadata for filtering
    if available:
        filter_result = await db.execute(select(Course).where(Course.course_id.in_(available)))
        course_meta = {
            c.course_id: {
                "department": c.department, "credits": c.credits,
                "avg_gpa": c.avg_gpa, "gen_eds": c.gen_eds or [],
            }
            for c in filter_result.scalars().all()
        }
    else:
        course_meta = {}

    available = _apply_filters(available, body.filters, course_meta)

    impact_courses = auditor.get_highest_impact_courses(completed_credits, available)
    requirement_impact = dict(impact_courses)

    context = await _build_scoring_context(
        db, available, completed, major, requirement_impact, body.weight_overrides,
        preference_tags=body.preference_tags,
    )

    result = await _engine.recommend(available, context, body.top_n)

    return RecommendationListResponse(
        recommendations=[
            RecommendationResponse(
                course_id=r.course_id, final_score=r.final_score, rank=r.rank,
                top_reason=r.top_reason, confidence=r.confidence,
                explanations=[
                    {"factor": e.factor, "score": e.score, "weight": e.weight,
                     "contribution": e.contribution, "text": e.text}
                    for e in r.explanations
                ],
            )
            for r in result.recommendations
        ],
        total_candidates=result.total_candidates,
        weights_used=result.weights_used,
    )


@router.post("/audit", response_model=AuditResponse)
async def get_degree_audit(body: AuditRequest, db: AsyncSession = Depends(get_db)):
    """Get degree audit showing progress toward graduation."""
    completed = await _get_completed_credits(
        body.completed_courses, db,
        credit_overrides=body.completed_course_credits or None,
    )
    major = body.major or "Computer Science"

    # Fetch gen_ed tags for completed courses that exist in the DB
    rows = await db.execute(
        select(Course.course_id, Course.gen_eds)
        .where(Course.course_id.in_(list(completed.keys())))
    )
    course_gen_eds = {row.course_id: (row.gen_eds or []) for row in rows.all()}

    # Merge transcript-parsed gen_eds with the DB. The transcript is highly accurate for the specific student.
    for cid, tags in body.course_gen_eds_override.items():
        if not tags:
            continue
        if cid not in course_gen_eds:
            course_gen_eds[cid] = tags
        else:
            course_gen_eds[cid] = list(set(course_gen_eds[cid] + tags))

    requirements = build_requirements_for_major(major, body.track)

    # If the student declared a minor, inject its department prefixes into the ULC requirement
    if body.minor_prefix:
        ulc_group = next((g for g in requirements.groups if g.id == "ulc"), None)
        if ulc_group:
            ulc_req = ulc_group.requirements[0]
            dept = body.minor_prefix.upper()
            for level in ["3", "4"]:
                pat = dept + level
                if pat not in ulc_req.prefix_patterns:
                    ulc_req.prefix_patterns.append(pat)

    auditor = DegreeAuditor(requirements)
    result = auditor.audit(
        completed,
        in_progress=set(body.in_progress_courses),
        course_gen_eds=course_gen_eds,
    )

    return AuditResponse(
        major=result.major,
        overall_progress_pct=result.overall_progress_pct,
        total_credits_completed=result.total_credits_completed,
        total_credits_required=result.total_credits_required,
        groups=[
            GroupResultResponse(
                name=g.group.name, progress_pct=g.progress_pct,
                completed_count=g.completed_count, total_count=g.total_count,
                min_required=g.group.min_requirements_satisfied,
                requirements=[
                    RequirementResultResponse(
                        name=r.requirement.name, status=r.status.value,
                        completed_courses=r.completed_courses,
                        remaining_options=r.remaining_options,
                        credits_completed=r.credits_completed,
                        credits_remaining=r.credits_remaining,
                        courses_completed=len(r.completed_courses),
                        courses_needed=r.requirement.courses_needed,
                    )
                    for r in g.results
                ],
            )
            for g in result.group_results
        ],
        courses_remaining=result.courses_remaining,
        total_courses_remaining=result.total_courses_remaining,
    )


@router.post("/plan", response_model=MultiSemesterPlanResponse)
async def generate_plan(body: PlanRequest, db: AsyncSession = Depends(get_db)):
    """Generate a multi-semester graduation plan."""
    completed = await _get_completed_credits(body.completed_courses, db)
    major = body.major or "Computer Science"

    graph = _build_graph_for_major(major)
    requirements = build_requirements_for_major(major, body.track)
    auditor = DegreeAuditor(requirements)
    # Include graph courses and any requirement courses not in the graph (default 3 credits)
    credit_map: dict[str, int] = {
        node.course_id: node.credits
        for node in [graph.get_course(c) for c in graph.courses] if node
    }
    for group in requirements.groups:
        for req in group.requirements:
            for course_id in req.course_options:
                if course_id not in credit_map:
                    credit_map[course_id] = req.credits_needed if req.courses_needed == 1 else 3

    planner = PlanGenerator(graph, auditor, credit_map)
    result = planner.generate_plan(
        completed,
        max_credits_per_semester=body.max_credits_per_semester,
        max_courses_per_semester=body.max_courses_per_semester,
        start_semester=body.start_semester,
        prioritize=body.prioritize,
    )

    return MultiSemesterPlanResponse(
        semesters=[
            SemesterPlanResponse(
                semester_number=s.semester_number, semester_label=s.semester_label,
                courses=s.courses, total_credits=s.total_credits,
            )
            for s in result.semesters
        ],
        total_semesters=result.total_semesters,
        total_credits=result.total_credits,
        warnings=result.warnings,
    )
