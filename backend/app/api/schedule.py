"""Schedule builder API endpoints."""

import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.engine.interval_tree import TimeInterval
from app.engine.schedule_solver import (
    DayPreference,
    SchedulePreferences,
    ScheduleSolver,
    Section as EngineSection,
)
from app.models import Section
from app.schemas.schemas import (
    ScheduleListResponse,
    ScheduleMeetingResponse,
    ScheduleRequest,
    ScheduleResultResponse,
    ScheduleSectionResponse,
)

router = APIRouter(prefix="/api/schedule", tags=["schedule"])

# Day character mapping: DB stores "MWF" or "TuTh", engine needs individual day strings
DAY_CHARS = {"M": "M", "T": "T", "W": "W", "R": "Th", "F": "F"}

_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _parse_hhmm(value: str, field_name: str) -> int:
    """Parse a 'HH:MM' 24-hour string into minutes from midnight, or 400 on bad input."""
    m = _HHMM_RE.match(value.strip())
    if not m:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} time '{value}'; expected HH:MM (24-hour).",
        )
    return int(m.group(1)) * 60 + int(m.group(2))


def _ical_escape(value: str) -> str:
    """Escape a text value for an iCal property per RFC 5545 (backslash, comma,
    semicolon, and newlines) so DB-sourced names can't inject calendar syntax."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _parse_days(days_str: str | None) -> list[str]:
    """Parse a days string like 'MWF' or 'TuTh' into individual day codes."""
    if not days_str:
        return []
    result = []
    i = 0
    while i < len(days_str):
        if i + 1 < len(days_str) and days_str[i:i+2] == "Tu":
            result.append("T")
            i += 2
        elif i + 1 < len(days_str) and days_str[i:i+2] == "Th":
            result.append("Th")
            i += 2
        elif days_str[i] in DAY_CHARS:
            result.append(DAY_CHARS[days_str[i]])
            i += 1
        else:
            i += 1
    return result


def _db_section_to_engine(db_section: Section, professor_name: str) -> EngineSection | None:
    """Convert a DB Section row to the engine Section dataclass."""
    if not db_section.start_time or not db_section.end_time or not db_section.days:
        return None

    days = _parse_days(db_section.days)
    if not days:
        return None

    start_str = db_section.start_time.strftime("%H:%M")
    end_str = db_section.end_time.strftime("%H:%M")

    meetings = [
        TimeInterval.from_time_str(start_str, end_str, day, f"{db_section.course_id} Lec")
        for day in days
    ]

    return EngineSection(
        section_id=db_section.section_id,
        course_id=db_section.course_id,
        professor=professor_name,
        meetings=meetings,
        open_seats=db_section.open_seats,
    )


@router.post("/generate", response_model=ScheduleListResponse)
async def generate_schedules(request: ScheduleRequest, db: AsyncSession = Depends(get_db)):
    """Generate optimal schedules using CSP solver."""
    if not request.course_ids:
        raise HTTPException(status_code=400, detail="No courses provided")

    # Parse preferences
    prefs = SchedulePreferences()
    if request.preferences:
        p = request.preferences
        if p.no_before:
            prefs.no_before = _parse_hhmm(p.no_before, "no_before")
        if p.no_after:
            prefs.no_after = _parse_hhmm(p.no_after, "no_after")
        try:
            prefs.day_preference = DayPreference(p.day_preference)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid day_preference '{p.day_preference}'."
            )
        prefs.max_classes_per_day = p.max_classes_per_day
        prefs.minimize_gaps = p.minimize_gaps
        prefs.avoid_days = p.avoid_days or []

    # Fetch real sections from database
    result = await db.execute(
        select(Section)
        .options(selectinload(Section.professor))
        .where(Section.course_id.in_([c.upper() for c in request.course_ids]))
    )
    db_sections = result.scalars().all()

    # Group by course and convert to engine sections
    course_sections: dict[str, list[EngineSection]] = {}
    for db_sec in db_sections:
        prof_name = db_sec.professor.name if db_sec.professor else "Staff"
        engine_sec = _db_section_to_engine(db_sec, prof_name)
        if engine_sec:
            course_sections.setdefault(db_sec.course_id, []).append(engine_sec)

    # Check we have sections for all requested courses
    missing = [c.upper() for c in request.course_ids if c.upper() not in course_sections]
    if missing:
        return ScheduleListResponse(
            schedules=[],
            total_generated=0,
            message=f"No timetable sections found for: {', '.join(missing)}. "
                    "Run the seed script to populate section data.",
        )

    solver = ScheduleSolver(prefs)
    results = solver.solve(course_sections, max_results=request.max_results)

    if not results:
        return ScheduleListResponse(
            schedules=[],
            total_generated=0,
            message="No conflict-free schedule exists for these courses and constraints. "
                    "Try removing a course or relaxing time preferences.",
        )

    return ScheduleListResponse(
        schedules=[
            ScheduleResultResponse(
                sections=[
                    ScheduleSectionResponse(
                        section_id=s.section_id,
                        course_id=s.course_id,
                        professor=s.professor,
                        meetings=[
                            ScheduleMeetingResponse(
                                day=m.day,
                                start_time=f"{m.start // 60:02d}:{m.start % 60:02d}",
                                end_time=f"{m.end // 60:02d}:{m.end % 60:02d}",
                            )
                            for m in s.meetings
                        ],
                        open_seats=s.open_seats,
                    )
                    for s in r.sections
                ],
                score=r.score,
                total_credits=r.total_credits,
                breakdown=r.breakdown,
            )
            for r in results
        ],
        total_generated=len(results),
    )


DAY_TO_ICAL = {"M": "MO", "T": "TU", "W": "WE", "Th": "TH", "F": "FR"}
DAY_TO_WEEKDAY = {"M": 0, "T": 1, "W": 2, "Th": 3, "F": 4}


@router.post("/export/ical")
async def export_schedule_ical(request: ScheduleRequest, db: AsyncSession = Depends(get_db)):
    """Export a generated schedule as an iCal (.ics) file."""
    if not request.course_ids:
        raise HTTPException(status_code=400, detail="No courses provided")

    prefs = SchedulePreferences()
    result_db = await db.execute(
        select(Section)
        .options(selectinload(Section.professor))
        .where(Section.course_id.in_([c.upper() for c in request.course_ids]))
    )
    db_sections = result_db.scalars().all()

    course_sections: dict[str, list[EngineSection]] = {}
    for db_sec in db_sections:
        prof_name = db_sec.professor.name if db_sec.professor else "Staff"
        engine_sec = _db_section_to_engine(db_sec, prof_name)
        if engine_sec:
            course_sections.setdefault(db_sec.course_id, []).append(engine_sec)

    missing = [c.upper() for c in request.course_ids if c.upper() not in course_sections]
    if missing:
        raise HTTPException(status_code=404, detail=f"No sections found for: {', '.join(missing)}")

    solver = ScheduleSolver(prefs)
    results = solver.solve(course_sections, max_results=1)
    if not results:
        raise HTTPException(status_code=404, detail="No valid schedule found")

    best = results[0]

    # Find the next Monday as the semester start reference
    today = date.today()
    start_monday = today + timedelta(days=(7 - today.weekday()) % 7)
    semester_end = start_monday + timedelta(weeks=16)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TerpAdvisor//Schedule Export//EN",
        "CALSCALE:GREGORIAN",
    ]

    for section in best.sections:
        for meeting in section.meetings:
            day_offset = DAY_TO_WEEKDAY.get(meeting.day, 0)
            event_date = start_monday + timedelta(days=day_offset)
            start_h, start_m = divmod(meeting.start, 60)
            end_h, end_m = divmod(meeting.end, 60)
            dtstart = event_date.strftime("%Y%m%d") + f"T{start_h:02d}{start_m:02d}00"
            dtend = event_date.strftime("%Y%m%d") + f"T{end_h:02d}{end_m:02d}00"
            ical_day = DAY_TO_ICAL.get(meeting.day, "MO")
            until = semester_end.strftime("%Y%m%d") + "T235959"

            lines.extend([
                "BEGIN:VEVENT",
                f"DTSTART:{dtstart}",
                f"DTEND:{dtend}",
                f"RRULE:FREQ=WEEKLY;BYDAY={ical_day};UNTIL={until}",
                f"SUMMARY:{_ical_escape(section.course_id)} - {_ical_escape(section.professor)}",
                f"DESCRIPTION:Section {_ical_escape(section.section_id)}",
                "LOCATION:UMD Campus",
                "END:VEVENT",
            ])

    lines.append("END:VCALENDAR")
    ical_content = "\r\n".join(lines)

    return PlainTextResponse(
        content=ical_content,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=schedule.ics"},
    )
