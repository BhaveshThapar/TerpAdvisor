"""Pydantic request/response schemas for all API endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── Course ────────────────────────────────────

class CourseResponse(BaseModel):
    course_id: str
    name: str
    department: str
    credits: int
    description: str
    avg_gpa: float | None
    gen_eds: list[str]
    model_config = {"from_attributes": True}


class CourseDetailResponse(CourseResponse):
    grade_distribution: dict[str, int] = {}
    reviews: list[ReviewResponse] = []
    professors: list[ProfessorBrief] = []
    prerequisites: list[str] = []
    prereqs_completed: list[str] = []
    prereqs_remaining: list[str] = []
    fulfills_requirements: list[str] = []


class GradeDistribution(BaseModel):
    A_plus: int = Field(0, alias="A+")
    A: int = 0
    A_minus: int = Field(0, alias="A-")
    B_plus: int = Field(0, alias="B+")
    B: int = 0
    B_minus: int = Field(0, alias="B-")
    C_plus: int = Field(0, alias="C+")
    C: int = 0
    C_minus: int = Field(0, alias="C-")
    D_plus: int = Field(0, alias="D+")
    D: int = 0
    D_minus: int = Field(0, alias="D-")
    F: int = 0
    W: int = 0
    other: int = 0


# ── Professor ─────────────────────────────────

class ProfessorBrief(BaseModel):
    name: str
    avg_rating: float | None
    review_count: int = 0


class ProfessorResponse(ProfessorBrief):
    slug: str
    courses_taught: list[str] = []
    model_config = {"from_attributes": True}


class ProfessorDetailResponse(ProfessorResponse):
    reviews: list[ReviewResponse] = []


# ── Review ────────────────────────────────────

class ReviewResponse(BaseModel):
    rating: int | None
    text: str
    professor: str | None
    created_at: str | None
    model_config = {"from_attributes": True}


# ── Recommendations ───────────────────────────

class RecommendationRequest(BaseModel):
    completed_courses: list[str] = Field(default_factory=list, max_length=300)  # course IDs completed
    major: str = "Computer Science"
    track: str = "General"
    weight_overrides: dict[str, float] | None = None
    filters: RecommendationFilters | None = None
    preference_tags: list[str] | None = None  # e.g., ["project-based", "no-final-exam"]
    goal: Literal["balanced", "easiest"] = "balanced"
    show_prerequisites_only: bool = False
    top_n: int = Field(20, ge=1, le=100)


class RecommendationFilters(BaseModel):
    departments: list[str] | None = None
    levels: list[int] | None = None  # 100, 200, 300, 400
    gen_eds: list[str] | None = None
    min_credits: int | None = None
    max_credits: int | None = None
    min_gpa: float | None = None
    exclude_courses: list[str] | None = None
    exclude_professors: list[str] | None = None
    include_professors: list[str] | None = None


class ExplanationResponse(BaseModel):
    factor: str
    score: float
    weight: float
    contribution: float
    text: str


class RecommendationResponse(BaseModel):
    course_id: str
    final_score: float
    rank: int
    top_reason: str
    confidence: float
    explanations: list[ExplanationResponse]
    section: Literal["major_requirement", "other_course"] = "other_course"
    fulfills_requirements: list[str] = []


class RecommendationListResponse(BaseModel):
    recommendations: list[RecommendationResponse]
    total_candidates: int
    weights_used: dict[str, float]


# ── Degree Audit ──────────────────────────────

class RequirementResultResponse(BaseModel):
    name: str
    status: str
    completed_courses: list[str]
    remaining_options: list[str]
    credits_completed: int
    credits_remaining: int
    courses_completed: int = 0
    courses_needed: int = 1


class GroupResultResponse(BaseModel):
    name: str
    progress_pct: float
    completed_count: int
    total_count: int
    min_required: int | None = None
    requirements: list[RequirementResultResponse]


class AuditRequest(BaseModel):
    completed_courses: list[str] = Field(default_factory=list, max_length=300)   # completed course IDs
    in_progress_courses: list[str] = Field(default_factory=list, max_length=50)  # currently being taken
    major: str = "Computer Science"
    track: str = "General"                  # major specialization track
    minor_prefix: str | None = None         # department prefix for minor (e.g. "ENTR" for Entrepreneurship)
    # Overrides from transcript parser — avoids wrong DB fallback for courses not in catalog
    completed_course_credits: dict[str, int] = {}       # course_id → actual credits from transcript
    course_gen_eds_override: dict[str, list[str]] = {}  # course_id → gen_ed codes from transcript


class AuditResponse(BaseModel):
    major: str
    overall_progress_pct: float
    total_credits_completed: int
    total_credits_required: int
    groups: list[GroupResultResponse]
    courses_remaining: list[str]
    total_courses_remaining: int


# ── Schedule ──────────────────────────────────

class ScheduleRequest(BaseModel):
    course_ids: list[str] = Field(default_factory=list, max_length=50)
    preferences: SchedulePreferencesSchema | None = None
    max_results: int = Field(5, ge=1, le=25)


class SchedulePreferencesSchema(BaseModel):
    no_before: str | None = None  # Time string like "09:00"
    no_after: str | None = None
    day_preference: str = "balanced"  # mwf, tuth, no_friday, balanced, any
    max_classes_per_day: int = 5
    minimize_gaps: bool = True
    avoid_days: list[str] | None = None


class ScheduleMeetingResponse(BaseModel):
    day: str
    start_time: str
    end_time: str


class ScheduleSectionResponse(BaseModel):
    section_id: str
    course_id: str
    professor: str
    meetings: list[ScheduleMeetingResponse]
    open_seats: int


class ScheduleResultResponse(BaseModel):
    sections: list[ScheduleSectionResponse]
    score: float
    total_credits: int
    breakdown: dict[str, float]


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleResultResponse]
    total_generated: int
    message: str = ""


# ── Semester Plan ─────────────────────────────

class PlanRequest(BaseModel):
    completed_courses: list[str] = Field(default_factory=list, max_length=300)  # course IDs completed
    major: str = "Computer Science"
    track: str = "General"
    max_credits_per_semester: int = Field(16, ge=1, le=30)
    max_courses_per_semester: int = Field(5, ge=1, le=10)
    start_semester: str = "Fall 2026"
    prioritize: list[str] | None = None


class SemesterPlanResponse(BaseModel):
    semester_number: int
    semester_label: str
    courses: list[str]
    total_credits: int


class MultiSemesterPlanResponse(BaseModel):
    semesters: list[SemesterPlanResponse]
    total_semesters: int
    total_credits: int
    warnings: list[str]


# ── Majors ────────────────────────────────────

class MajorSummary(BaseModel):
    name: str
    code: str | None
    tracks: list[str]


# Forward references
CourseDetailResponse.model_rebuild()
ProfessorDetailResponse.model_rebuild()
RecommendationRequest.model_rebuild()
ScheduleRequest.model_rebuild()
