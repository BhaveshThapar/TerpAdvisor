/**
 * API client for TerpAdvisor backend.
 * After the localStorage migration, only catalog/stateless endpoints remain.
 * User-specific state (cart, wishlist, completed courses, preferences) is
 * managed client-side via userStore.ts.
 */

import type {
  AuditResult,
  CourseDetail,
  MultiSemesterPlan,
  ProfessorDetail,
  RecommendationList,
  ScheduleResult,
  TranscriptParseResult,
  UserPreferences,
  WeightConfig,
} from "@/types";

const BASE_URL = "/api";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Courses ───────────────────────────────────
export const courseApi = {
  search: (query: string) => fetchApi<CourseDetail[]>(`/courses/search?q=${encodeURIComponent(query)}`),
  getDetail: (courseId: string, completedCourses?: string[]) => {
    const params = completedCourses?.length
      ? `?completed=${encodeURIComponent(completedCourses.join(","))}`
      : "";
    return fetchApi<CourseDetail>(`/courses/${courseId}${params}`);
  },
  getGrades: (courseId: string) => fetchApi<Record<string, number>>(`/courses/${courseId}/grades`),
  parseTranscript: (raw_text: string) =>
    fetchApi<TranscriptParseResult>("/courses/parse-transcript", {
      method: "POST",
      body: JSON.stringify({ raw_text }),
    }),
  parseTranscriptPdf: async (file: File): Promise<TranscriptParseResult> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/courses/parse-transcript-pdf`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => null);
      throw new Error(errBody?.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  },
};

// ── Recommendations ───────────────────────────
export const recommendationApi = {
  get: (
    completedCourses: string[],
    major: string,
    track: string = "General",
    weights?: Partial<WeightConfig>,
    topN = 20,
    preferenceTags?: string[],
    filters?: UserPreferences["filters"],
  ) =>
    fetchApi<RecommendationList>("/recommendations", {
      method: "POST",
      body: JSON.stringify({
        completed_courses: completedCourses,
        major,
        track,
        weight_overrides: weights,
        top_n: topN,
        preference_tags: preferenceTags,
        filters: filters,
      }),
    }),
};

// ── Degree Audit ──────────────────────────────
export const auditApi = {
  get: (completedCourses: string[], major: string, track: string = "General", inProgressCourses?: string[], creditOverrides?: Record<string, number>, courseGenEdsOverride?: Record<string, string[]>, minorPrefix?: string | null) =>
    fetchApi<AuditResult>("/audit", {
      method: "POST",
      body: JSON.stringify({
        completed_courses: completedCourses,
        in_progress_courses: inProgressCourses || [],
        major,
        track,
        minor_prefix: minorPrefix || null,
        completed_course_credits: creditOverrides || {},
        course_gen_eds_override: courseGenEdsOverride || {},
      }),
    }),
};

// ── Schedule ──────────────────────────────────
export const scheduleApi = {
  generate: (courseIds: string[], preferences?: Record<string, unknown>) =>
    fetchApi<{ schedules: ScheduleResult[]; total_generated: number; message?: string }>("/schedule/generate", {
      method: "POST",
      body: JSON.stringify({ course_ids: courseIds, preferences }),
    }),
  exportIcal: async (courseIds: string[]) => {
    const res = await fetch(`${BASE_URL}/schedule/export/ical`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ course_ids: courseIds }),
    });
    if (!res.ok) throw new Error("Failed to export schedule");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "schedule.ics";
    a.click();
    URL.revokeObjectURL(url);
  },
};

// ── Professors ────────────────────────────────
export const professorApi = {
  search: (q: string) =>
    fetchApi<Array<{ name: string; slug: string; avg_rating: number | null; review_count: number; courses_taught: string[] }>>(
      `/professors/search?q=${encodeURIComponent(q)}`
    ),
  getDetail: (slug: string) => fetchApi<ProfessorDetail>(`/professors/${slug}`),
};

// ── Plan ──────────────────────────────────────
export const planApi = {
  generate: (
    completedCourses: string[],
    major: string,
    track: string = "General",
    options?: {
      max_credits_per_semester?: number;
      start_semester?: string;
      prioritize?: string[];
    },
  ) =>
    fetchApi<MultiSemesterPlan>("/plan", {
      method: "POST",
      body: JSON.stringify({
        completed_courses: completedCourses,
        major,
        track,
        ...(options || {}),
      }),
    }),
};
