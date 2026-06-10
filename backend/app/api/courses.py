"""Course and search API endpoints."""

import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.cache.service import cached
from app.db.session import get_db
from app.engine.requirements_loader import load_requirements_for_major
from app.models import Course, Professor, Review
from app.schemas.schemas import CourseResponse

router = APIRouter(prefix="/api/courses", tags=["courses"])

_UMD_COURSE_ID_RE = re.compile(r'\b([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\b')


async def _fetch_umdio_course(course_id: str) -> dict | None:
    """Fetch course data from umd.io API (prerequisites, description)."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"https://api.umd.io/v1/courses/{course_id}")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0]
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return None


async def _fetch_planetterp_grades(course_id: str) -> dict[str, int]:
    """Grade distribution for a course, served through the multi-layer cache.

    Grade data changes once a semester at most, so a 24h TTL avoids hitting
    PlanetTerp on every course-detail view. Falls back to a live fetch when
    the cache layers are unavailable.
    """
    return await cached(
        f"grades:{course_id}",
        lambda: _fetch_planetterp_grades_live(course_id),
        ttl=86400,
        delta=0.5,
    )


async def _fetch_planetterp_grades_live(course_id: str) -> dict[str, int]:
    """Fetch and aggregate grade distribution from PlanetTerp across all semesters."""
    grade_keys = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-",
                  "D+", "D", "D-", "F", "W", "Other"]
    api_keys = ["A_plus", "A", "A_minus", "B_plus", "B", "B_minus", "C_plus", "C", "C_minus",
                "D_plus", "D", "D_minus", "F", "W", "other"]
    totals: dict[str, int] = dict.fromkeys(grade_keys, 0)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://planetterp.com/api/v1/grades",
                params={"course": course_id},
            )
            if resp.status_code == 200:
                for row in resp.json():
                    for display_key, api_key in zip(grade_keys, api_keys):
                        totals[display_key] += row.get(api_key, 0)
    except Exception:
        pass
    return {k: v for k, v in totals.items() if v > 0}


async def _fetch_planetterp_course(course_id: str) -> dict | None:
    """Fetch course data from PlanetTerp API (professors list)."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://planetterp.com/api/v1/course",
                params={"name": course_id, "reviews": "false"},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None


@router.get("/search", response_model=list[CourseResponse])
async def search_courses(
    q: str = Query(..., min_length=2),
    department: str | None = None,
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search courses by name or ID."""
    stmt = select(Course).where(
        or_(
            Course.course_id.ilike(f"%{q}%"),
            Course.name.ilike(f"%{q}%"),
        )
    )
    if department:
        stmt = stmt.where(Course.department == department.upper())
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        CourseResponse(
            course_id=c.course_id, name=c.name, department=c.department,
            credits=c.credits, description=c.description or "",
            avg_gpa=c.avg_gpa, gen_eds=c.gen_eds or [],
        )
        for c in rows
    ]


@router.get("/{course_id}")
async def get_course_detail(
    course_id: str,
    completed: str | None = Query(None, description="Comma-separated list of completed course IDs"),
    db: AsyncSession = Depends(get_db),
):
    """Get full course detail with reviews and professors."""
    result = await db.execute(
        select(Course)
        .options(selectinload(Course.reviews), selectinload(Course.sections))
        .where(Course.course_id == course_id.upper())
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail=f"Course {course_id} not found")

    # Get professors from sections
    prof_ids = {s.professor_id for s in course.sections if s.professor_id}
    prof_map: dict = {}
    professors = []
    if prof_ids:
        prof_result = await db.execute(select(Professor).where(Professor.id.in_(prof_ids)))
        prof_rows = prof_result.scalars().all()
        prof_map = {p.id: p for p in prof_rows}
        # Count actual reviews per professor; fall back to PlanetTerp stored count
        count_result = await db.execute(
            select(Review.professor_id, func.count().label("cnt"))
            .where(Review.professor_id.in_(prof_ids))
            .group_by(Review.professor_id)
        )
        db_review_counts = {row.professor_id: row.cnt for row in count_result}
        seen: set[str] = set()
        for p in prof_rows:
            if p.name in seen:
                continue
            seen.add(p.name)
            professors.append({
                "name": p.name,
                "avg_rating": p.avg_rating,
                "review_count": db_review_counts.get(p.id) or p.review_count,
            })

    reviews = [
        {"rating": r.rating, "text": r.text, "professor": None, "created_at": str(r.created_at)}
        for r in (course.reviews or [])
    ]

    grade_dist = await _fetch_planetterp_grades(course.course_id)

    # Parse prerequisites — try DB first, fall back to umd.io
    prereqs: list[str] = []
    prereq_text: str = ""
    if course.prerequisites_raw:
        raw = course.prerequisites_raw
        if isinstance(raw, list):
            prereqs = raw
        elif isinstance(raw, dict) and "courses" in raw:
            prereqs = raw["courses"]
            prereq_text = raw.get("text", "")
        elif isinstance(raw, dict) and "all" in raw:
            prereqs = raw["all"]
        elif isinstance(raw, dict) and "text" in raw:
            prereq_text = raw["text"]
            prereqs = _UMD_COURSE_ID_RE.findall(prereq_text)

    if not prereqs and not prereq_text:
        umdio = await _fetch_umdio_course(course.course_id)
        if umdio:
            rels = umdio.get("relationships") or {}
            raw_text = rels.get("prereqs", "") or ""
            prereq_text = raw_text.strip()
            if prereq_text:
                prereqs = _UMD_COURSE_ID_RE.findall(prereq_text)
                # Persist so we don't fetch again next time
                course.prerequisites_raw = {"text": prereq_text, "courses": prereqs}
                await db.commit()
            # Also backfill description if missing
            if not course.description and umdio.get("description"):
                course.description = umdio["description"]
                await db.commit()

    # Fall back to PlanetTerp for professor list if sections gave us nothing
    if not professors:
        pt = await _fetch_planetterp_course(course.course_id)
        if pt:
            seen_names: set[str] = set()
            pt_profs = pt.get("professors") or []
            for prof_name in pt_profs:
                if prof_name in seen_names:
                    continue
                seen_names.add(prof_name)
                # Try slug lookup first, then fall back to exact name match
                slug = re.sub(r'[^a-z0-9_]', '', prof_name.lower().replace(" ", "_"))
                existing = await db.execute(select(Professor).where(Professor.slug == slug))
                db_prof = existing.scalar_one_or_none()
                if db_prof is None:
                    # Slug mismatch — try by exact name
                    name_result = await db.execute(
                        select(Professor).where(Professor.name == prof_name)
                    )
                    db_prof = name_result.scalar_one_or_none()
                if db_prof:
                    rc_result = await db.execute(
                        select(func.count()).where(Review.professor_id == db_prof.id)
                    )
                    db_rc = rc_result.scalar() or 0
                    professors.append({
                        "name": db_prof.name,
                        "avg_rating": db_prof.avg_rating,
                        "review_count": db_rc if db_rc > 0 else db_prof.review_count,
                    })
                else:
                    professors.append({"name": prof_name, "avg_rating": None, "review_count": 0})

    # Determine which prereqs have been completed (from query param)
    user_courses: set[str] = set()
    if completed:
        user_courses = {c.strip().upper() for c in completed.split(",") if c.strip()}
    prereqs_completed = [p for p in prereqs if p in user_courses]
    prereqs_remaining = [p for p in prereqs if p not in user_courses]

    # Determine which requirements this course fulfills
    fulfills = []
    for major_name in ["Computer Science", "Mathematics", "Information Science",
                       "Economics", "Biological Sciences", "Mechanical Engineering"]:
        reqs = await load_requirements_for_major(db, major_name)
        for group in reqs.groups:
            for req in group.requirements:
                if course.course_id in req.course_options:
                    fulfills.append(f"{major_name}: {req.name}")

    # Build section meeting times for display
    sections = []
    for s in (course.sections or []):
        if not s.start_time or not s.end_time or not s.days:
            continue
        prof = prof_map.get(s.professor_id)
        sections.append({
            "section_id": s.section_id,
            "days": s.days,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "open_seats": s.open_seats,
            "total_seats": s.total_seats,
            "semester": s.semester,
            "professor": prof.name if prof else "Staff",
        })

    return {
        "course_id": course.course_id,
        "name": course.name,
        "department": course.department,
        "credits": course.credits,
        "description": course.description or "",
        "avg_gpa": course.avg_gpa,
        "gen_eds": course.gen_eds or [],
        "grade_distribution": grade_dist,
        "reviews": reviews,
        "professors": professors,
        "prerequisites": prereqs,
        "prerequisites_text": prereq_text,
        "prereqs_completed": prereqs_completed,
        "prereqs_remaining": prereqs_remaining,
        "fulfills_requirements": fulfills,
        "sections": sections,
    }


@router.post("/{course_id}/sync")
async def sync_course_professors(course_id: str, db: AsyncSession = Depends(get_db)):
    """Re-sync professor data for a course from PlanetTerp (fixes stale review_count/avg_rating)."""
    from app.workers.etl.planetterp_etl import PlanetTerpETL
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        etl = PlanetTerpETL()
        result = await loop.run_in_executor(None, etl.sync_course, course_id.upper())
        return {"success": True, "course_id": course_id.upper(), "detail": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{course_id}/grades")
async def get_grade_distribution(course_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Course).where(Course.course_id == course_id.upper()))
    course = result.scalar_one_or_none()
    grades = await _fetch_planetterp_grades(course_id.upper())
    return {
        "course_id": course_id.upper(),
        "avg_gpa": course.avg_gpa if course else None,
        "grades": grades,
    }


@router.get("/{course_id}/reviews")
async def get_reviews(
    course_id: str,
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(Review.course_id == course_id.upper()).limit(limit)
    )
    rows = result.scalars().all()
    return {
        "course_id": course_id,
        "reviews": [
            {"rating": r.rating, "text": r.text, "created_at": str(r.created_at)}
            for r in rows
        ],
    }


# ── Transcript Parsing ────────────────────────

from pydantic import BaseModel
from fastapi import File, UploadFile


class TranscriptParseRequest(BaseModel):
    raw_text: str


class ParsedCourse(BaseModel):
    course_id: str
    name: str | None = None
    credits: float | None = None
    grade: str | None = None
    gen_eds: list[str] = []
    in_catalog: bool = False
    in_progress: bool = False


class TranscriptParseResult(BaseModel):
    courses: list[ParsedCourse]
    total_credits: float = 0
    major: str | None = None


# Known UMD department prefixes — comprehensive list covering all colleges
_UMD_DEPT_PREFIXES = {
    "AASP", "AAST", "AGNR", "AMSC", "AMST", "ANSC", "ANTH", "AOSC", "ARAB",
    "ARCH", "AREC", "ARHU", "ARMY", "ARSC", "ARTH", "ARTT", "ASTR", "BCHM",
    "BIOE", "BIOL", "BIOM", "BIPH", "BMGT", "BSCI", "BSCV", "BSOS", "BSST",
    "BUAC", "BUDT", "BUFN", "BULM", "BUMK", "BUMO", "BUSI", "BUSM", "CCJS",
    "CHBE", "CHEM", "CHIN", "CHPH", "CINE", "CLAS", "CLFS", "CMLT", "CMSC",
    "COMM", "CPMS", "CPSD", "CPSP", "DANC", "ECON", "EDCI", "EDCP", "EDHD",
    "EDHI", "EDMS", "EDPS", "EDSP", "EDUC", "ENAE", "ENCE", "ENCH", "ENCO",
    "ENEE", "ENES", "ENFP", "ENGL", "ENMA", "ENME", "ENPM", "ENPP", "ENRE",
    "ENSE", "ENSP", "ENST", "ENTM", "EPIB", "FGSM", "FILM", "FIRE", "FMSC",
    "FOLA", "FREN", "GEMS", "GEOG", "GEOL", "GERM", "GREK", "GVPT", "HACS",
    "HDCC", "HEBR", "HEIP", "HESP", "HHUM", "HISP", "HIST", "HLSA", "HLSC",
    "HLTH", "HONR", "IDEA", "IMDM", "IMMR", "INAG", "INFM", "INST", "ISRL",
    "ITAL", "JAPN", "JOUR", "JWST", "KINE", "KNES", "KORA", "LACS", "LARC",
    "LATN", "LBSC", "LING", "MATH", "MEES", "MIEH", "MITH", "MLSC", "MSML",
    "MUSC", "NACS", "NAVY", "NFSC", "PERS", "PHIL", "PHPE", "PHSC", "PHYS",
    "PLCY", "PLSC", "PORT", "PSYC", "PUAF", "RDEV", "RELS", "RUSS", "SLAA",
    "SLLC", "SOCY", "SPAN", "SPHL", "STAT", "SURV", "TDPS", "THET", "TLPL",
    "TLTC", "UMEI", "UNIV", "URSP", "USLT", "VMSC", "WMST",
}

# Known UMD gen-ed codes
_GENED_CODES = {
    "FSAW", "FSAR", "FSMA", "FSOC", "FSPW",  # Fundamental Studies
    "DSHS", "DSHU", "DSNL", "DSNS", "DSSP",   # Distributive Studies
    "DVCC", "DVUP",                             # Diversity
    "SCIS",                                     # Scholarship in Practice
}

# Valid letter grades
_VALID_GRADES = {"A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F", "W", "S", "P", "NC", "XF", "I"}

# Grades that mean the student did not complete the course — exclude from completed set
# W = Withdrawal, AW = Administrative Withdrawal, F = Failing
# Note: XF (Academic Dishonesty) is NOT excluded here so it appears in the parsed
# transcript result, but it must be filtered out downstream when building the
# prerequisite-satisfied / completed-course lists.
_EXCLUDED_GRADES = {"AU"} # Only exclude 'Audit' by default; let W/F show up in results

# Action codes in the Current Course Information table that mean the student dropped/withdrew
_DROPPED_ACTIONS = {"AW", "D", "W"}

# Numeric quality score for each grade — used to keep the BEST grade when a course
# appears multiple times (e.g. repeated course). Higher = better.
_GRADE_QUALITY: dict[str, int] = {
    "A+": 14, "A": 13, "A-": 12,
    "B+": 11, "B": 10, "B-": 9,
    "C+": 8,  "C": 7,  "C-": 6,
    "D+": 5,  "D": 4,  "D-": 3,
    "P": 2, "S": 2, "TR": 2,
    "NC": 1, "I": 0, "XF": 0,
}


async def _match_courses(raw_text: str, db: AsyncSession) -> TranscriptParseResult:
    """Parse transcript text and extract course data with credits and gen-eds."""
    import re

    # Get known course IDs from DB for catalog matching
    result = await db.execute(select(Course.course_id))
    known_set = set(row[0] for row in result.all())

    # Extract major from Testudo header (e.g. "Major: Computer Science")
    major_match = re.search(r'^Major:\s*(.+)$', raw_text, re.MULTILINE | re.IGNORECASE)
    major = major_match.group(1).strip() if major_match else None

    lines = raw_text.split("\n")
    seen: dict[str, ParsedCourse] = {}  # dedup by course_id
    next_is_repeat = False  # set True when *Repeated Course* marker is seen
    in_progress_section = False  # set True after "Current Course Information" header
    # Regex for current-course rows: course_id  section  credits  [remainder]
    # Remainder may contain an action code (AW, D, W) indicating a drop/withdrawal
    _current_course_re = re.compile(r'^([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\s+(\S+)\s+(\d+\.\d{1,2})(.*)?$')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect Testudo's "*Repeated Course*" marker line BEFORE any regex matching.
        # This line does not start with a course code so it never matches the main regex.
        # Setting the flag here ensures the very next course line is treated as a repeat
        # replacement regardless of where the marker appears in the transcript.
        if re.search(r'\*repeated', line, re.IGNORECASE):
            next_is_repeat = True
            continue

        # Detect the "Current Course Information" section header
        if re.search(r'Current Course Information', line, re.IGNORECASE):
            in_progress_section = True
            continue

        if in_progress_section:
            cm = _current_course_re.match(line)
            if cm:
                course_id = cm.group(1)
                prefix_match = re.match(r'^[A-Z]+', course_id)
                prefix = prefix_match.group() if prefix_match else ""
                if prefix not in _UMD_DEPT_PREFIXES:
                    continue
                # Check remainder for a drop/withdrawal action code (AW, D, W)
                remainder_tokens = set((cm.group(4) or "").split())
                if remainder_tokens & _DROPPED_ACTIONS:
                    continue
                credits = float(cm.group(3))
                # Don't overwrite a graded entry already in seen
                if course_id not in seen:
                    seen[course_id] = ParsedCourse(
                        course_id=course_id,
                        name=None,
                        credits=credits,
                        grade=None,
                        gen_eds=[],
                        in_catalog=course_id in known_set,
                        in_progress=True,
                    )
            continue  # skip graded-course regex for lines in this section

        # Try to match Testudo transcript line format:
        #   CMSC131 OBJECT-ORIENTED PROG I  A+  4.00  4.00  16.00  FSAR, FSMA
        #   FMSC190 MAN UP! FATHERS         A-  3.00  3.00  11.10  DSHS, SCIS
        # Pattern: DEPT+NUM  TITLE  GRADE  CREDITS  EARNED  QPOINTS  [GENEDS]
        m = re.match(
            r'^([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\s+'   # course_id
            r'(.+?)\s+'                        # course name (non-greedy)
            r'([A-Z][+-]?|NC|XF|W|S|P|I|TR)\s+' # grade (added TR)
            r'(\d+\.\d{2})\s+'                 # credits attempted
            r'(\d+\.\d{2})\s+'                 # credits earned
            r'(\d+\.\d{2})'                     # quality points
            r'(.*)?$',                          # optional gen-ed codes
            line
        )

        if m:
            course_id = m.group(1)
            prefix_match = re.match(r'^[A-Z]+', course_id)
            prefix = prefix_match.group() if prefix_match else ""

            # Skip if the prefix isn't a real UMD department
            if prefix not in _UMD_DEPT_PREFIXES:
                next_is_repeat = False
                continue

            name = m.group(2).strip()

            # When a *Repeated Course* marker line is matched, set the flag and skip
            # inserting — the NEXT course line is the replacement and should overwrite.
            if name.startswith("*Repeated"):
                next_is_repeat = True
                continue

            grade = m.group(3)

            # Skip withdrawals and academic-dishonesty grades — course not completed.
            # Note: AW lines are parsed with grade W (the A is absorbed into the name)
            # so checking W covers both W and AW cases.
            if grade in _EXCLUDED_GRADES:
                next_is_repeat = False
                continue

            credits = float(m.group(4))
            remainder = (m.group(7) or "").strip()

            # Extract gen-ed codes from the remainder
            gen_eds = [code for code in re.findall(r'[A-Z]{3,4}', remainder) if code in _GENED_CODES]

            # Always prefer the LATEST attempt in the transcript (found later in the text)
            # or the one marked as a repeat replacement.
            if next_is_repeat or course_id not in seen:
                seen[course_id] = ParsedCourse(
                    course_id=course_id,
                    name=name,
                    credits=credits,
                    grade=grade,
                    gen_eds=gen_eds,
                    in_catalog=course_id in known_set,
                )
            elif grade not in _EXCLUDED_GRADES:
                # Second (or later) attempt without an explicit repeat marker.
                # Keep the attempt with the HIGHER quality grade so that a retaken
                # course always shows the student's best outcome regardless of the
                # order entries appear in the transcript.
                existing_quality = _GRADE_QUALITY.get(seen[course_id].grade or "", 0)
                new_quality = _GRADE_QUALITY.get(grade, 0)
                if new_quality >= existing_quality:
                    seen[course_id] = ParsedCourse(
                        course_id=course_id,
                        name=name,
                        credits=max(credits, seen[course_id].credits or 0),
                        grade=grade,
                        gen_eds=gen_eds or seen[course_id].gen_eds,
                        in_catalog=course_id in known_set,
                    )
            next_is_repeat = False
        else:
            # Try compact formats that omit course name and numeric credit columns:
            #   "CMSC131 (A)"        — grade in parentheses, no credits
            #   "CMSC131 (A) 4.00"   — grade in parentheses with optional credits
            #   "CMSC131 A"          — bare grade, no credits
            #   "CMSC131 A 4.00"     — bare grade with credits
            _grade_token = r'(?:A[+-]?|B[+-]?|C[+-]?|D[+-]?|F|NC|XF|W|S|P|I|TR|NG)'
            compact_paren = re.match(
                r'^([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\s+\((' + _grade_token + r')\)\s*(\d+\.\d{2})?$',
                line,
            )
            compact_bare = re.match(
                r'^([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\s+(' + _grade_token + r')\s*(\d+\.\d{2})?$',
                line,
            )
            cm2 = compact_paren or compact_bare
            if cm2:
                course_id = cm2.group(1)
                prefix_match = re.match(r'^[A-Z]+', course_id)
                prefix = prefix_match.group() if prefix_match else ""
                if prefix in _UMD_DEPT_PREFIXES:
                    grade = cm2.group(2)
                    if grade not in _EXCLUDED_GRADES:
                        credits = float(cm2.group(3)) if cm2.group(3) else 0.0
                        if next_is_repeat or course_id not in seen:
                            seen[course_id] = ParsedCourse(
                                course_id=course_id,
                                name=None,
                                credits=credits,
                                grade=grade,
                                gen_eds=[],
                                in_catalog=course_id in known_set,
                            )
                        else:
                            # Second (or later) compact entry — keep the higher-quality grade,
                            # mirroring the logic in the full-format path above.
                            existing_quality = _GRADE_QUALITY.get(seen[course_id].grade or "", 0)
                            new_quality = _GRADE_QUALITY.get(grade, 0)
                            if new_quality >= existing_quality:
                                seen[course_id] = seen[course_id].model_copy(update={
                                    "credits": max(credits, seen[course_id].credits or 0),
                                    "grade": grade,
                                })
                        next_is_repeat = False
                        continue
            # Non-blank line that didn't match — reset repeat flag to avoid
            # a malformed transcript infecting an unrelated subsequent course
            if line:
                next_is_repeat = False

    # Also do a simple regex pass for AP/transfer credits that don't follow the tabular format
    # Match lines like "ENG LANG/COMP/SCR 3 P 3.00 L1" or "2405 HUMAN EVOLUTION & ARCH A 3.00 DSNS, DVUP"
    for line in lines:
        line = line.strip()

        # Skip lines that match the main 3-column tabular format — already parsed in pass 1.
        # Real course lines have: COURSE_ID  TITLE  GRADE  CREDITS  EARNED  QPOINTS (3 decimal fields).
        # Transfer/AP lines have only 1 decimal field, so this guard doesn't affect them.
        if re.match(
            r'^[A-Z]{3,4}\d{3}[A-Z0-9X]{0,2}\s+.+?\s+'
            r'(?:A[+-]?|B[+-]?|C[+-]?|D[+-]?|F|NC|XF|W|S|P|I|TR)\s+'
            r'\d+\.\d{2}\s+\d+\.\d{2}\s+\d+\.\d{2}',
            line,
        ):
            continue

        # Skip semester/year header lines like "Fall 2023", "Summer I 2024"
        if re.match(r'^(Fall|Spring|Summer|Winter)\s+', line, re.IGNORECASE):
            continue

        # Look for typical equivalency patterns
        ap_match = re.match(r'^([\w\s&/-]+?/SCR)\s+(\d+)\s+(P|NC|A[+-]?|B[+-]?|C[+-]?|TR)\s+(\d+(?:\.\d{1,2})?)(.*)$', line)
        tr_match = re.match(r'^([\w\s&/-]+?)\s+(A[+-]?|B[+-]?|C[+-]?|D[+-]?|F|S|P|TR|XF|I|NG|W|AU)\s+(\d+(?:\.\d{1,2})?)(.*)$', line)
        
        m_course = None
        m_grade = None
        m_credits = None
        m_remainder = ""

        if ap_match:
            m_course = ap_match.group(1).strip()
            m_grade = ap_match.group(3).strip()
            m_credits = float(ap_match.group(4))
            m_remainder = (ap_match.group(5) or "").strip()
        elif tr_match:
            m_course = tr_match.group(1).strip()
            # If the course ID looks like a standard UMD course, accept it directly
            # Otherwise, it might be a transfer title (e.g. "Linear Algebra")
            m_grade = tr_match.group(2).strip()
            m_credits = float(tr_match.group(3))
            m_remainder = (tr_match.group(4) or "").strip()

        # Extract gen-ed codes from the remainder of the transfer line
        tr_gen_eds = [code for code in re.findall(r'[A-Z]{3,4}', m_remainder) if code in _GENED_CODES]

        # When found, assign the AP/transfer credits directly to the equivalency course and
        # skip creating a separate TR_ entry — prevents double-counting.
        equiv_matches = re.findall(r'\b([A-Z]{3,4}\d{3}[A-Z0-9X]{0,2})\b', line)
        found_equivs: list[str] = []
        is_transfer_line = "/SCR" in line.upper() or "Transfer" in line or "Advanced Placement" in line
        for cid in equiv_matches:
            prefix_match = re.match(r'^[A-Z]+', cid)
            prefix = prefix_match.group() if prefix_match else ""
            if prefix in _UMD_DEPT_PREFIXES and is_transfer_line:
                found_equivs.append(cid)
                if cid not in seen:
                    seen[cid] = ParsedCourse(
                        course_id=cid,
                        name=None,
                        credits=m_credits,
                        grade="TR",
                        gen_eds=tr_gen_eds,
                        in_catalog=cid in known_set,
                    )

        # Only create a TR_ entry when there is no UMD equivalency on this line.
        # If there IS an equivalency, the credits are already attributed to that course above.
        if m_course and m_credits is not None and not found_equivs:
            if m_credits == 0.0:
                continue
            if m_credits > 20:  # sanity check — no real course exceeds 20 credits
                continue
            
            # Additional check: If m_course is a standard UMD ID already in seen, don't duplicate it
            if m_course.upper() in seen:
                continue
                
            clean_name = re.sub(r'[^A-Z0-9_]', '', m_course.upper().replace(' ', '_'))
            if not clean_name:
                continue
            cid = f"TR_{m_credits}_{clean_name}"
            if cid not in seen:
                seen[cid] = ParsedCourse(
                    course_id=cid,
                    name=m_course,
                    credits=m_credits,
                    grade="TR" if m_grade in ("P", "TR", "NC") else m_grade,
                    gen_eds=tr_gen_eds,
                    in_catalog=False,
                )

    # Back-fill credits for in-catalog courses that were parsed without a credit column
    # (compact format omits the numeric columns, so credits default to 0.0).
    zero_ids = [cid for cid, c in seen.items() if not c.credits and c.in_catalog and not c.in_progress]
    if zero_ids:
        db_rows = await db.execute(
            select(Course.course_id, Course.credits).where(Course.course_id.in_(zero_ids))
        )
        for db_cid, db_cr in db_rows.all():
            if db_cr:
                seen[db_cid] = seen[db_cid].model_copy(update={"credits": float(db_cr)})

    courses = sorted(seen.values(), key=lambda c: c.course_id)
    total_credits = sum(c.credits for c in courses if c.credits and not c.in_progress)

    return TranscriptParseResult(
        courses=courses,
        total_credits=total_credits,
        major=major,
    )


@router.post("/parse-transcript", response_model=TranscriptParseResult)
async def parse_transcript(
    body: TranscriptParseRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Parse raw transcript text and extract UMD course IDs.
    Returns matched courses (confirmed in DB), suggested (fuzzy matches), unrecognized.
    """
    return await _match_courses(body.raw_text, db)


@router.post("/parse-transcript-pdf", response_model=TranscriptParseResult)
async def parse_transcript_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a PDF transcript file, extract text, and match UMD course IDs.
    Supports Testudo unofficial transcripts and similar formats.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()

    try:
        import fitz  # pymupdf

        doc = fitz.open(stream=contents, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        raw_text = "\n".join(text_parts)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {str(e)}")

    if not raw_text.strip():
        return TranscriptParseResult(matched=[], suggested=[], unrecognized=[])

    return await _match_courses(raw_text, db)
