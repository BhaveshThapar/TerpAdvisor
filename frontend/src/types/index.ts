// ── User ──────────────────────────────────────
export interface User {
  id: string;
  email: string;
  display_name: string;
  major: string;
  minor: string | null;
}

export interface CompletedCourse {
  course_id: string;
  semester: string | null;
  grade: string | null;
  credits?: number | null;
  gen_eds?: string[];
  in_progress?: boolean;
}

// ── Course ────────────────────────────────────
export interface Course {
  course_id: string;
  name: string;
  department: string;
  credits: number;
  description: string;
  avg_gpa: number | null;
  gen_eds: string[];
}

export interface CourseSectionBrief {
  section_id: string;
  days: string;
  start_time: string;
  end_time: string;
  open_seats: number;
  total_seats: number;
  semester: string;
  professor: string;
}

export interface CourseDetail extends Course {
  grade_distribution: Record<string, number>;
  reviews: Review[];
  professors: ProfessorBrief[];
  prerequisites: string[];
  prerequisites_text: string;
  prereqs_completed: string[];
  prereqs_remaining: string[];
  fulfills_requirements: string[];
  sections: CourseSectionBrief[];
}

export interface GradeDistribution {
  [grade: string]: number;
}

// ── Professor ─────────────────────────────────
export interface ProfessorBrief {
  name: string;
  avg_rating: number | null;
  review_count: number;
}

export interface ProfessorDetail {
  name: string;
  slug: string;
  avg_rating: number | null;
  review_count: number;
  courses_taught: string[];
  reviews: Review[];
}

// ── Review ────────────────────────────────────
export interface Review {
  rating: number | null;
  text: string;
  professor: string | null;
  created_at: string | null;
}

// ── Recommendations ───────────────────────────
export interface Explanation {
  factor: string;
  score: number;
  weight: number;
  contribution: number;
  text: string;
}

export interface Recommendation {
  course_id: string;
  final_score: number;
  rank: number;
  top_reason: string;
  confidence: number;
  explanations: Explanation[];
}

export interface RecommendationList {
  recommendations: Recommendation[];
  total_candidates: number;
  weights_used: Record<string, number>;
}

// ── Degree Audit ──────────────────────────────
export interface RequirementResult {
  name: string;
  status: "complete" | "in_progress" | "incomplete";
  completed_courses: string[];
  remaining_options: string[];
  credits_completed: number;
  credits_remaining: number;
  courses_completed: number;
  courses_needed: number;
}

export interface GroupResult {
  name: string;
  progress_pct: number;
  completed_count: number;
  total_count: number;
  min_required?: number;
  requirements: RequirementResult[];
}

export interface AuditResult {
  major: string;
  overall_progress_pct: number;
  total_credits_completed: number;
  total_credits_required: number;
  groups: GroupResult[];
  courses_remaining: string[];
  total_courses_remaining: number;
}

// ── Schedule ──────────────────────────────────
export interface ScheduleMeeting {
  day: string;
  start_time: string;
  end_time: string;
}

export interface ScheduleSection {
  section_id: string;
  course_id: string;
  professor: string;
  meetings: ScheduleMeeting[];
  open_seats: number;
}

export interface ScheduleResult {
  sections: ScheduleSection[];
  score: number;
  total_credits: number;
  breakdown: Record<string, number>;
}

// ── Semester Plan ─────────────────────────────
export interface SemesterPlan {
  semester_number: number;
  semester_label: string;
  courses: string[];
  total_credits: number;
}

export interface MultiSemesterPlan {
  semesters: SemesterPlan[];
  total_semesters: number;
  total_credits: number;
  warnings: string[];
}

// ── Cart ──────────────────────────────────────
export interface CartItem {
  course_id: string;
  added_at: string;
}

// ── Transcript ────────────────────────────────
export interface ParsedCourse {
  course_id: string;
  name: string | null;
  credits: number | null;
  grade: string | null;
  gen_eds: string[];
  in_catalog: boolean;
  in_progress?: boolean;
}

export interface TranscriptParseResult {
  courses: ParsedCourse[];
  total_credits: number;
  major: string | null;
}

// ── Wishlist ─────────────────────────────────
export interface WishlistItem {
  course_id: string;
  added_at: string;
}

// ── Weight Sliders ────────────────────────────
export interface WeightConfig {
  requirement: number;
  gpa: number;
  professor: number;
  sentiment: number;
  collaborative: number;
  schedule_fit: number;
}

export const DEFAULT_WEIGHTS: WeightConfig = {
  requirement: 0.35,
  gpa: 0.25,
  professor: 0.15,
  sentiment: 0.10,
  collaborative: 0.05,
  schedule_fit: 0.10,
};

// ── Preferences ───────────────────────────────
export interface UserPreferences {
  weight_overrides: Partial<WeightConfig> | null;
  preference_tags: string[] | null;
  filters: {
    departments?: string[];
    levels?: number[];
    min_gpa?: number;
    exclude_courses?: string[];
    exclude_professors?: string[];
    include_professors?: string[];
  } | null;
  schedule_preferences: {
    no_before?: string;
    no_after?: string;
    day_preference?: string;
    minimize_gaps?: boolean;
  } | null;
}
