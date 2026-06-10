"""Recommendation and degree audit API endpoints."""

import re

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.service import cached, make_key
from app.db.session import get_db
from app.engine.course_graph import CourseGraph, CourseNode, PrereqNode, PrereqType
from app.engine.degree_audit import DegreeAuditor, build_cs_requirements
from app.engine.requirements_loader import load_requirements_for_major
from app.engine.planner import PlanGenerator
from app.engine.recommender import RecommendationEngine
from app.engine.scorers.base import ScoringContext
from app.models import Course, Professor, Review, Section
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
    needs_db_lookup: list[str] = []
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

        needs_db_lookup.append(course_id)

    # Single batched query instead of one round-trip per course (N+1).
    db_credits: dict[str, int] = {}
    if needs_db_lookup:
        rows = await db.execute(
            select(Course.course_id, Course.credits).where(
                Course.course_id.in_(needs_db_lookup)
            )
        )
        db_credits = {row.course_id: row.credits for row in rows.all()}

    for course_id in needs_db_lookup:
        credits = db_credits.get(course_id)
        # Use 0 rather than a 3-credit guess for courses absent from the DB.
        # The frontend should supply credit_overrides for such courses.
        completed[course_id] = credits if credits is not None else 0
    return completed


async def _build_scoring_context(
    db: AsyncSession, available: list[str], completed: set[str], major: str,
    requirement_impact: dict[str, int], weight_overrides: dict | None,
    preference_tags: list[str] | None = None,
) -> ScoringContext:
    """Build scoring context with real data from DB."""
    # Map professors to courses via sections so the professor scorer sees
    # real instructor data (previously hardcoded to [] — the scorer was a
    # no-op and the professor weight slider did nothing).
    course_profs: dict[str, set[str]] = {}
    prof_names: set[str] = set()
    if available:
        section_rows = await db.execute(
            select(Section.course_id, Professor.name)
            .join(Professor, Section.professor_id == Professor.id)
            .where(Section.course_id.in_(available))
        )
        for sec_course_id, prof_name in section_rows.all():
            course_profs.setdefault(sec_course_id, set()).add(prof_name)
            prof_names.add(prof_name)

    # Fetch course data
    course_data = {}
    if available:
        result = await db.execute(select(Course).where(Course.course_id.in_(available)))
        for c in result.scalars().all():
            course_data[c.course_id] = {
                "avg_gpa": c.avg_gpa,
                "department": c.department,
                "credits": c.credits,
                "gen_eds": c.gen_eds or [],
                "sections": [],
                "professors": sorted(course_profs.get(c.course_id, set())),
            }

    # Fetch only professors who actually teach the candidate courses
    # (previously loaded the entire professors table on every request).
    professor_data = {}
    if prof_names:
        prof_result = await db.execute(
            select(Professor).where(Professor.name.in_(prof_names))
        )
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
    available: list[str],
    filters: RecommendationFilters | None,
    course_data: dict,
    allowed_by_prof: set[str] | None = None,
    excluded_by_prof: set[str] | None = None,
) -> list[str]:
    """Apply user-specified filters to the candidate course list."""
    if not filters and not allowed_by_prof and not excluded_by_prof:
        return available

    filtered = available
    if filters is None:
        filters = RecommendationFilters()
    
    # Department filter
    if filters.departments:
        depts = {d.upper() for d in filters.departments}
        filtered = [c for c in filtered if (course_data.get(c, {}).get("department") or "").upper() in depts]
    
    # Level filter (e.g., 100, 200) — match the FIRST digit of the course
    # number. The old `any(char in lvls for char in c)` matched a level digit
    # anywhere in the ID, so a 100-level filter wrongly kept CMSC216/351/416.
    if filters.levels:
        lvls = {str(lvl)[0] for lvl in filters.levels}

        def _level_digit(cid: str) -> str | None:
            m = re.search(r"\d", cid)
            return m.group() if m else None

        filtered = [c for c in filtered if _level_digit(c) in lvls]
        
    # GenEd filter
    if filters.gen_eds:
        gen_set = {g.upper() for g in filters.gen_eds}
        filtered = [
            c for c in filtered
            if gen_set & set(course_data.get(c, {}).get("gen_eds") or [])
        ]
        
    if filters.min_credits is not None:
        filtered = [c for c in filtered if (course_data.get(c, {}).get("credits") or 3) >= filters.min_credits]
        
    if filters.max_credits is not None:
        filtered = [c for c in filtered if (course_data.get(c, {}).get("credits") or 3) <= filters.max_credits]
        
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

    # Professor filters (resolved to course-id sets by caller)
    if allowed_by_prof is not None:
        filtered = [c for c in filtered if c in allowed_by_prof]
    if excluded_by_prof:
        filtered = [c for c in filtered if c not in excluded_by_prof]

    return filtered


async def _compute_recommendations(body: RecommendationRequest, db: AsyncSession) -> dict:
    """Run the full recommendation pipeline.

    Returns a JSON-serialisable dict in the RecommendationListResponse shape
    so the result can be stored in the multi-layer cache and shared with the
    Celery cache-warming task.
    """
    completed_credits = await _get_completed_credits(body.completed_courses, db)
    completed = set(completed_credits.keys())
    major = body.major or "Computer Science"

    requirements = await load_requirements_for_major(db, major, body.track or "General")
    graph = await CourseGraph.build_from_umd_catalog(db, major, requirements=requirements)
    auditor = DegreeAuditor(requirements)

    if body.goal == "easiest" and not body.show_prerequisites_only:
        catalog_result = await db.execute(select(Course.course_id))
        available = [cid for cid in catalog_result.scalars().all() if cid not in completed]
    else:
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

    unmet_gened_codes: set[str] = set()
    if body.goal == "easiest":
        audit_result = auditor.audit(
            completed_credits,
            course_gen_eds={cid: meta.get("gen_eds") or [] for cid, meta in course_meta.items()},
        )
        for group in audit_result.group_results:
            for req_result in group.results:
                req = req_result.requirement
                if req.type.value != "gened":
                    continue
                if req_result.status.value == "complete":
                    continue
                for code in req.id.split("_")[1:]:
                    unmet_gened_codes.add(code.upper())

        if unmet_gened_codes:
            narrowed = [
                cid for cid in available
                if unmet_gened_codes & {g.upper() for g in (course_meta.get(cid, {}).get("gen_eds") or [])}
            ]
            if narrowed:
                available = narrowed
            else:
                # No seeded courses carry gen_eds tags — fall back to full catalog
                # so users still see results, and clear unmet codes so the weight
                # tuning below doesn't over-boost the requirement scorer.
                unmet_gened_codes = set()

    allowed_by_prof: set[str] | None = None
    excluded_by_prof: set[str] = set()
    if body.filters and (body.filters.include_professors or body.filters.exclude_professors):
        slugs = list({*(body.filters.include_professors or []), *(body.filters.exclude_professors or [])})
        prof_rows = await db.execute(select(Professor).where(Professor.slug.in_(slugs)))
        prof_courses = {p.slug: (p.courses_taught or []) for p in prof_rows.scalars().all()}
        if body.filters.include_professors:
            allowed_by_prof = set()
            for s in body.filters.include_professors:
                allowed_by_prof.update(prof_courses.get(s, []))
        for s in (body.filters.exclude_professors or []):
            excluded_by_prof.update(prof_courses.get(s, []))

    available = _apply_filters(available, body.filters, course_meta, allowed_by_prof, excluded_by_prof)

    impact_courses = auditor.get_highest_impact_courses(completed_credits, available)
    requirement_impact = dict(impact_courses)

    weight_overrides = dict(body.weight_overrides or {})
    preference_tags = body.preference_tags
    if body.goal == "easiest":
        easiest_defaults: dict[str, float] = {
            "gpa": 0.50,
            "preference_tags": 0.30,
            "sentiment": 0.10,
            "requirement": 0.05,
            "professor": 0.05,
            "collaborative": 0.0,
            "schedule_fit": 0.0,
        }
        if unmet_gened_codes:
            # Shift weight back toward requirement fit so GenEd-fulfilling picks win.
            easiest_defaults["requirement"] = 0.20
            easiest_defaults["gpa"] = 0.40
        for k, v in easiest_defaults.items():
            weight_overrides.setdefault(k, v)

    context = await _build_scoring_context(
        db, available, completed, major, requirement_impact, weight_overrides,
        preference_tags=preference_tags,
    )

    result = await _engine.recommend(available, context, body.top_n)

    if body.goal != "easiest" and requirement_impact and body.top_n >= 4:
        elective_ids = [cid for cid in available if cid not in requirement_impact]
        if elective_ids:
            elective_weights = dict(weight_overrides)
            elective_weights["requirement"] = 0.0
            elective_context = await _build_scoring_context(
                db, elective_ids, completed, major, requirement_impact,
                elective_weights, preference_tags=preference_tags,
            )
            elective_result = await _engine.recommend(
                elective_ids, elective_context, body.top_n,
            )
            k = max(3, body.top_n // 4)
            keep_requirement = body.top_n - k
            existing_ids = {r.course_id for r in result.recommendations[:keep_requirement]}
            elective_picks = [
                r for r in elective_result.recommendations
                if r.course_id not in existing_ids
            ][:k]
            merged = result.recommendations[:keep_requirement] + elective_picks
            merged.sort(key=lambda r: r.final_score, reverse=True)
            for idx, rec in enumerate(merged, start=1):
                rec.rank = idx
            result.recommendations = merged

    recommended_ids = [r.course_id for r in result.recommendations]
    classification = auditor.classify_courses(
        recommended_ids,
        completed,
        course_gen_eds={cid: course_meta.get(cid, {}).get("gen_eds") or [] for cid in recommended_ids},
    )

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
                fulfills_requirements=classification.get(r.course_id, []),
                section="major_requirement" if classification.get(r.course_id) else "other_course",
            )
            for r in result.recommendations
        ],
        total_candidates=result.total_candidates,
        weights_used=result.weights_used,
    ).model_dump()


@router.post("/recommendations", response_model=RecommendationListResponse)
async def get_recommendations(body: RecommendationRequest, db: AsyncSession = Depends(get_db)):
    """Get personalized course recommendations.

    Responses are served through the multi-layer cache (LRU -> Redis ->
    Postgres) with XFetch stampede protection, keyed on the full request
    payload. TTL is 15 minutes; cache-layer failures fall back to direct
    computation so the endpoint works even without Redis.
    """
    key = make_key("rec", body.model_dump())
    return await cached(
        key,
        lambda: _compute_recommendations(body, db),
        ttl=900,
        delta=1.5,
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

    requirements = await load_requirements_for_major(db, major, body.track or "General")

    # If the student declared a minor, inject its department prefixes into the
    # ULC requirement. Mutating in place is safe: load_requirements_for_major
    # returns a fresh object per call (the cache stores dicts, not objects).
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

    requirements = await load_requirements_for_major(db, major, body.track or "General")
    graph = await CourseGraph.build_from_umd_catalog(db, major, requirements=requirements)
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
