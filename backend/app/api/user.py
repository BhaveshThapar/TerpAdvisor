"""User profile and course history API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verify_jwt
from app.config import settings
from app.db.session import get_db
from app.models import CompletedCourse, User
from app.schemas.schemas import (
    CompletedCourseAdd,
    CompletedCourseResponse,
    UserCreate,
    UserPreferencesSchema,
    UserResponse,
    UserUpdate,
)


class TranscriptParseRequest(BaseModel):
    raw_text: str


class TranscriptParseResult(BaseModel):
    matched: list[str]
    suggested: list[dict]
    unrecognized: list[str]

router = APIRouter(prefix="/api/user", tags=["user"])

DEMO_EMAIL = "demo@terpmail.umd.edu"


async def _get_or_create_demo_user(db: AsyncSession) -> User:
    """Get or create the demo user for local development."""
    result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            display_name="Demo Student",
            major="Computer Science",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def _current_user(request: Request, db: AsyncSession) -> User:
    """Get current user from JWT token, or demo user in demo mode."""
    if settings.demo_mode:
        return await _get_or_create_demo_user(db)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")
    token = auth_header[7:]
    payload = verify_jwt(token)
    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    new_user = User(
        email=user.email,
        display_name=user.display_name,
        major=user.major,
        minor=user.minor,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse(
        id=str(new_user.id), email=new_user.email,
        display_name=new_user.display_name, major=new_user.major, minor=new_user.minor,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    return UserResponse(
        id=str(user.id), email=user.email,
        display_name=user.display_name, major=user.major, minor=user.minor,
    )


@router.patch("/me", response_model=UserResponse)
async def update_user(request: Request, update: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    if update.display_name is not None:
        user.display_name = update.display_name
    if update.major is not None:
        user.major = update.major
    if update.minor is not None:
        user.minor = update.minor
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id), email=user.email,
        display_name=user.display_name, major=user.major, minor=user.minor,
    )


@router.get("/courses", response_model=list[CompletedCourseResponse])
async def get_completed_courses(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    result = await db.execute(
        select(CompletedCourse).where(CompletedCourse.user_id == user.id)
    )
    rows = result.scalars().all()
    return [
        CompletedCourseResponse(
            course_id=r.course_id, semester=r.semester, grade=r.grade
        )
        for r in rows
    ]


@router.post("/courses", response_model=CompletedCourseResponse)
async def add_completed_course(request: Request, course: CompletedCourseAdd, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    row = CompletedCourse(
        user_id=user.id,
        course_id=course.course_id.upper(),
        semester=course.semester,
        grade=course.grade,
    )
    db.add(row)
    await db.commit()
    return CompletedCourseResponse(
        course_id=row.course_id, semester=row.semester, grade=row.grade,
    )


@router.delete("/courses/{course_id}")
async def remove_completed_course(request: Request, course_id: str, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    await db.execute(
        delete(CompletedCourse).where(
            CompletedCourse.user_id == user.id,
            CompletedCourse.course_id == course_id.upper(),
        )
    )
    await db.commit()
    return {"message": f"Removed {course_id} from completed courses"}


@router.post("/courses/bulk", response_model=list[CompletedCourseResponse])
async def bulk_add_courses(request: Request, courses: list[CompletedCourseAdd], db: AsyncSession = Depends(get_db)):
    """Bulk import completed courses. Accepts a JSON array of course objects."""
    user = await _current_user(request, db)
    added = []
    for course in courses:
        # Skip duplicates
        existing = await db.execute(
            select(CompletedCourse).where(
                CompletedCourse.user_id == user.id,
                CompletedCourse.course_id == course.course_id.upper(),
            )
        )
        if existing.scalar_one_or_none():
            continue

        row = CompletedCourse(
            user_id=user.id,
            course_id=course.course_id.upper(),
            semester=course.semester,
            grade=course.grade,
        )
        db.add(row)
        added.append(CompletedCourseResponse(
            course_id=row.course_id, semester=row.semester, grade=row.grade,
        ))
    await db.commit()
    return added


@router.get("/me/preferences", response_model=UserPreferencesSchema)
async def get_preferences(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    prefs = user.preferences or {}
    return UserPreferencesSchema(
        weight_overrides=prefs.get("weight_overrides"),
        preference_tags=prefs.get("preference_tags"),
        filters=prefs.get("filters"),
        schedule_preferences=prefs.get("schedule_preferences"),
    )


@router.patch("/me/preferences", response_model=UserPreferencesSchema)
async def update_preferences(
    update: UserPreferencesSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await _current_user(request, db)
    current = dict(user.preferences or {})
    if update.weight_overrides is not None:
        current["weight_overrides"] = update.weight_overrides
    if update.preference_tags is not None:
        current["preference_tags"] = update.preference_tags
    if update.filters is not None:
        current["filters"] = update.filters
    if update.schedule_preferences is not None:
        current["schedule_preferences"] = update.schedule_preferences
    user.preferences = current
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "preferences")
    await db.commit()
    await db.refresh(user)
    return UserPreferencesSchema(**user.preferences)


@router.post("/courses/parse-transcript", response_model=TranscriptParseResult)
async def parse_transcript(
    body: TranscriptParseRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Parse raw transcript text and extract UMD course IDs.
    Returns matched courses (confirmed in DB), suggested (fuzzy matches), unrecognized.
    Does NOT add courses — just parses.
    """
    import re
    from difflib import get_close_matches
    from app.models import Course

    raw = body.raw_text.upper()
    candidates = re.findall(r'[A-Z]{3,4}\s?\d{3}[A-Z]?', raw)
    candidates = list(set(c.replace(" ", "") for c in candidates))

    if not candidates:
        return TranscriptParseResult(matched=[], suggested=[], unrecognized=[])

    result = await db.execute(select(Course.course_id))
    known_ids = [row[0] for row in result.all()]
    known_set = set(known_ids)

    matched = []
    suggested = []
    unrecognized = []

    for candidate in candidates:
        if candidate in known_set:
            matched.append(candidate)
        else:
            close = get_close_matches(candidate, known_ids, n=1, cutoff=0.8)
            if close:
                suggested.append({"input": candidate, "closest": close[0]})
            else:
                unrecognized.append(candidate)

    return TranscriptParseResult(
        matched=sorted(matched),
        suggested=suggested,
        unrecognized=sorted(unrecognized),
    )
