"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import type { ScheduleResult, ScheduleSection, ScheduleMeeting } from "@/types";
import { scheduleApi, auditApi } from "@/lib/api";
import { getCompletedCourseIds, getState } from "@/lib/userStore";

/* ── Helpers ─────────────────────────────────────── */

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const DAY_CODE_MAP: Record<string, string> = {
  Mon: "M", Tue: "T", Wed: "W", Thu: "Th", Fri: "F",
};
const HOURS = Array.from({ length: 10 }, (_, i) => i + 8); // 8 AM to 5 PM

const COURSE_COLORS: Record<string, string> = {
  CMSC420: "bg-[var(--umd-red)]/90 text-white",
  CMSC411: "bg-indigo-500 text-white",
  STAT400: "bg-emerald-500 text-white",
  ENGL393: "bg-amber-500 text-white",
  CMSC435: "bg-purple-500 text-white",
  CMSC451: "bg-cyan-600 text-white",
  CMSC417: "bg-rose-500 text-white",
};

const FALLBACK_COLORS = [
  "bg-[var(--umd-red)]/90 text-white",
  "bg-indigo-500 text-white",
  "bg-emerald-500 text-white",
  "bg-amber-500 text-white",
  "bg-purple-500 text-white",
  "bg-cyan-600 text-white",
  "bg-rose-500 text-white",
  "bg-teal-500 text-white",
];

function getCourseColor(courseId: string, index: number): string {
  return COURSE_COLORS[courseId] || FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

function timeToRow(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return (h - 8) * 4 + Math.floor(m / 15);
}

function formatTime(time: string): string {
  const [h, m] = time.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `${h12}:${m.toString().padStart(2, "0")} ${ampm}`;
}

/* ── Components ─────────────────────────────────── */

function CalendarGrid({ schedule }: { schedule: ScheduleResult }) {
  return (
    <div className="bg-white rounded-2xl border border-black/5 shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
      <div className="grid grid-cols-6 border-b border-black/5 min-w-[480px]">
        <div className="p-3 text-xs font-medium text-[var(--umd-gray)]">Time</div>
        {DAYS.map((day) => (
          <div key={day} className="p-3 text-xs font-bold text-[var(--umd-black)] text-center border-l border-black/5">
            {day}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-6 relative min-w-[480px]" style={{ minHeight: 600 }}>
        {/* Time labels */}
        <div className="border-r border-black/5">
          {HOURS.map((hour) => (
            <div key={hour} className="h-[60px] px-3 flex items-start pt-1 border-b border-black/5">
              <span className="text-xs text-[var(--umd-gray)]">{hour > 12 ? hour - 12 : hour}:00 {hour >= 12 ? "PM" : "AM"}</span>
            </div>
          ))}
        </div>

        {/* Day columns */}
        {DAYS.map((day) => (
          <div key={day} className="relative border-l border-black/5">
            {/* Hour grid lines */}
            {HOURS.map((hour) => (
              <div key={hour} className="h-[60px] border-b border-black/5" />
            ))}

            {/* Course blocks */}
            {schedule.sections.map((section, sectionIdx) =>
              section.meetings
                .filter((m) => m.day === DAY_CODE_MAP[day])
                .map((meeting, i) => {
                  const top = (timeToRow(meeting.start_time) / 4) * 60;
                  const height = ((timeToRow(meeting.end_time) - timeToRow(meeting.start_time)) / 4) * 60;
                  return (
                    <div
                      key={`${section.section_id}-${i}`}
                      className={`absolute left-1 right-1 rounded-lg px-2 py-1.5 ${getCourseColor(section.course_id, sectionIdx)} shadow-sm overflow-hidden`}
                      style={{ top, height: Math.max(height, 30) }}
                    >
                      <p className="text-xs font-bold leading-tight truncate">{section.course_id}</p>
                      {height > 40 && (
                        <p className="text-[10px] opacity-80 leading-tight truncate">{section.professor}</p>
                      )}
                      {height > 55 && (
                        <p className="text-[10px] opacity-70 leading-tight">{formatTime(meeting.start_time)}</p>
                      )}
                    </div>
                  );
                })
            )}
          </div>
        ))}
      </div>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="flex gap-3">
        {[1, 2].map((i) => (
          <div key={i} className="h-10 bg-gray-200 rounded-xl w-32" />
        ))}
      </div>
      <div className="h-[600px] bg-white rounded-2xl border border-black/5" />
    </div>
  );
}

/* ── Page ────────────────────────────────────────── */

function SchedulePageInner() {
  const searchParams = useSearchParams();
  const [selectedCourses, setSelectedCourses] = useState<string[]>([]);
  const [availableCourses, setAvailableCourses] = useState<{ id: string; name: string; credits: number }[]>([]);
  const [noBefore, setNoBefore] = useState<string>("");
  const [noAfter, setNoAfter] = useState<string>("");
  const [dayPref, setDayPref] = useState<string>("balanced");
  const [gapPref, setGapPref] = useState<string>("minimal");
  const [activeSchedule, setActiveSchedule] = useState(0);
  const [schedules, setSchedules] = useState<ScheduleResult[]>([]);
  const [scheduleMessage, setScheduleMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generated, setGenerated] = useState(false);
  const cartCoursesApplied = useRef(false);

  // Fetch available courses from audit (remaining courses)
  useEffect(() => {
    async function loadCourses() {
      try {
        const completedIds = getCompletedCourseIds();
        const major = getState().major;
        const track = getState().track || "General";
        const audit = await auditApi.get(completedIds, major, track);
        const courses = audit.courses_remaining.map((courseId) => ({
          id: courseId,
          name: courseId,
          credits: 3,
        }));
        setAvailableCourses(courses);

        // Pre-select courses from the ?courses query param (CartDrawer navigation)
        // OR fall back to the current cart contents when navigating directly.
        const cartParam = searchParams.get("courses");
        const cartIds: string[] = cartParam
          ? cartParam.split(",").map((id) => id.trim()).filter(Boolean)
          : (getState().cart ?? []);

        if (cartIds.length > 0 && !cartCoursesApplied.current) {
          cartCoursesApplied.current = true;
          // Merge cart courses with audit courses so they appear in the selector
          const auditIds = new Set(courses.map((c) => c.id));
          const extraCourses = cartIds
            .filter((id) => !auditIds.has(id))
            .map((id) => ({ id, name: id, credits: 3 }));
          setAvailableCourses([...courses, ...extraCourses]);
          setSelectedCourses(cartIds);
        }
      } catch {
        // If audit fails, fall back to cart contents
        const cartParam = searchParams.get("courses");
        const fallbackIds: string[] = cartParam
          ? cartParam.split(",").map((id) => id.trim()).filter(Boolean)
          : (getState().cart ?? []);
        if (fallbackIds.length > 0) {
          const fallbackCourses = fallbackIds.map((id) => ({ id, name: id, credits: 3 }));
          setAvailableCourses(fallbackCourses);
          setSelectedCourses(fallbackIds);
        }
      } finally {
        setLoadingCourses(false);
      }
    }
    loadCourses();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load schedule preferences from local store
  useEffect(() => {
    const prefs = getState().preferences;
    if (prefs?.schedule_preferences) {
      if (prefs.schedule_preferences.no_before != null) setNoBefore(prefs.schedule_preferences.no_before);
      if (prefs.schedule_preferences.no_after != null) setNoAfter(prefs.schedule_preferences.no_after);
      if (prefs.schedule_preferences.day_preference) setDayPref(prefs.schedule_preferences.day_preference);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleCourse = (id: string) => {
    setSelectedCourses((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const handleGenerate = async () => {
    if (selectedCourses.length === 0) return;
    setLoading(true);
    setError(null);
    setGenerated(true);
    try {
      const preferences: Record<string, unknown> = {
        day_preference: dayPref,
        gap_preference: gapPref,
        ...(noBefore ? { no_before: noBefore } : {}),
        ...(noAfter ? { no_after: noAfter } : {}),
      };
      const data = await scheduleApi.generate(selectedCourses, preferences);
      setSchedules(data.schedules);
      setScheduleMessage(data.message ?? null);
      setActiveSchedule(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate schedules");
      setSchedules([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[var(--umd-black)]">Schedule Builder</h1>
        <p className="text-sm text-[var(--umd-gray)] mt-1">
          Select courses and preferences to generate optimized schedules.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Controls */}
        <div className="lg:col-span-1 space-y-6">
          {/* Course selector */}
          <div className="bg-white rounded-2xl p-5 border border-black/5 shadow-sm">
            <h3 className="text-sm font-bold text-[var(--umd-black)] mb-4">Select Courses</h3>
            {loadingCourses ? (
              <div className="animate-pulse space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-14 bg-gray-100 rounded-xl" />
                ))}
              </div>
            ) : availableCourses.length === 0 ? (
              <p className="text-sm text-[var(--umd-gray)] py-4 text-center">
                No remaining courses found. Complete your degree audit first.
              </p>
            ) : (
              <div className="space-y-2">
                {availableCourses.map((course) => (
                  <label
                    key={course.id}
                    className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                      selectedCourses.includes(course.id)
                        ? "border-[var(--umd-red)]/30 bg-[var(--umd-red)]/5"
                        : "border-black/5 hover:border-black/10"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedCourses.includes(course.id)}
                      onChange={() => toggleCourse(course.id)}
                      className="w-4 h-4 rounded accent-[var(--umd-red)]"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[var(--umd-black)] truncate">{course.id}</p>
                    </div>
                  </label>
                ))}
              </div>
            )}
            <p className="text-xs text-[var(--umd-gray)] mt-3">
              {selectedCourses.length} selected
            </p>
          </div>

          {/* Preferences */}
          <div className="bg-white rounded-2xl p-5 border border-black/5 shadow-sm">
            <h3 className="text-sm font-bold text-[var(--umd-black)] mb-4">Preferences</h3>
            <div className="space-y-5">
              {/* No classes before */}
              <div>
                <label className="text-xs font-medium text-[var(--umd-gray)] block mb-2">No classes before</label>
                <select
                  value={noBefore}
                  onChange={(e) => setNoBefore(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)]"
                >
                  <option value="">No restriction</option>
                  <option value="08:00">8:00 AM</option>
                  <option value="09:00">9:00 AM</option>
                  <option value="10:00">10:00 AM</option>
                  <option value="11:00">11:00 AM</option>
                  <option value="12:00">12:00 PM</option>
                </select>
              </div>

              {/* No classes after */}
              <div>
                <label className="text-xs font-medium text-[var(--umd-gray)] block mb-2">No classes after</label>
                <select
                  value={noAfter}
                  onChange={(e) => setNoAfter(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)]"
                >
                  <option value="">No restriction</option>
                  <option value="15:00">3:00 PM</option>
                  <option value="16:00">4:00 PM</option>
                  <option value="17:00">5:00 PM</option>
                  <option value="18:00">6:00 PM</option>
                  <option value="19:00">7:00 PM</option>
                </select>
              </div>

              {/* Day preference */}
              <div>
                <label className="text-xs font-medium text-[var(--umd-gray)] block mb-2">Day Preference</label>
                <div className="space-y-1.5">
                  {[
                    { value: "mwf", label: "MWF preferred" },
                    { value: "tuth", label: "TuTh preferred" },
                    { value: "balanced", label: "Balanced" },
                  ].map((opt) => (
                    <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="dayPref"
                        value={opt.value}
                        checked={dayPref === opt.value}
                        onChange={(e) => setDayPref(e.target.value)}
                        className="w-3.5 h-3.5 accent-[var(--umd-red)]"
                      />
                      <span className="text-sm text-[var(--umd-black)]">{opt.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Gap preference */}
              <div>
                <label className="text-xs font-medium text-[var(--umd-gray)] block mb-2">Gap Preference</label>
                <div className="space-y-1.5">
                  {[
                    { value: "minimal", label: "Minimize gaps" },
                    { value: "some", label: "Some breaks" },
                    { value: "spread", label: "Spread out" },
                  ].map((opt) => (
                    <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="gapPref"
                        value={opt.value}
                        checked={gapPref === opt.value}
                        onChange={(e) => setGapPref(e.target.value)}
                        className="w-3.5 h-3.5 accent-[var(--umd-red)]"
                      />
                      <span className="text-sm text-[var(--umd-black)]">{opt.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={loading || selectedCourses.length === 0}
              className="mt-5 w-full py-2.5 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors shadow-sm disabled:opacity-50"
            >
              {loading ? "Generating..." : "Generate Schedules"}
            </button>
          </div>
        </div>

        {/* Main calendar area */}
        <div className="lg:col-span-3">
          {/* Error state */}
          {error && (
            <div className="text-center py-8 bg-white rounded-2xl border border-black/5 shadow-sm mb-4">
              <p className="text-sm text-red-600">{error}</p>
              <button onClick={handleGenerate} className="mt-2 text-xs text-[var(--umd-red)] underline">Retry</button>
            </div>
          )}

          {/* Loading state */}
          {loading && <LoadingSkeleton />}

          {/* Empty state - before generation */}
          {!loading && !generated && !error && (
            <div className="text-center py-20 bg-white rounded-2xl border border-black/5 shadow-sm">
              <svg className="w-12 h-12 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
              </svg>
              <p className="text-lg font-medium text-[var(--umd-gray)]">No schedules generated yet</p>
              <p className="text-sm text-[var(--umd-gray)] mt-1">Select courses and click &ldquo;Generate Schedules&rdquo; to get started.</p>
            </div>
          )}

          {/* No results after generation */}
          {!loading && generated && schedules.length === 0 && !error && (
            <div className="text-center py-16 bg-white rounded-2xl border border-black/5 shadow-sm">
              <p className="text-lg font-medium text-[var(--umd-gray)]">No valid schedules found</p>
              <p className="text-sm text-[var(--umd-gray)] mt-1">
                {scheduleMessage ?? "Try selecting different courses or adjusting your preferences."}
              </p>
            </div>
          )}

          {/* Schedule results */}
          {!loading && schedules.length > 0 && (
            <>
              {/* Schedule tabs */}
              <div className="flex items-center gap-3 mb-4">
                {schedules.map((sched, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveSchedule(i)}
                    className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                      activeSchedule === i
                        ? "bg-[var(--umd-red)] text-white shadow-sm"
                        : "bg-white text-[var(--umd-gray)] border border-black/5 hover:border-[var(--umd-red)]/20"
                    }`}
                  >
                    Schedule {i + 1}
                    <span className={`ml-2 text-xs ${activeSchedule === i ? "text-white/80" : "text-[var(--umd-gray)]"}`}>
                      {Math.round(sched.score)}pts
                    </span>
                  </button>
                ))}
              </div>

              {/* Calendar */}
              <CalendarGrid schedule={schedules[activeSchedule]} />

              {/* Score breakdown */}
              <div className="mt-4 bg-white rounded-2xl p-5 border border-black/5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-[var(--umd-black)]">Score Breakdown</h3>
                  <span className="text-sm font-bold text-[var(--umd-red)]">
                    Overall: {Math.round(schedules[activeSchedule].score)} / 100
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(schedules[activeSchedule].breakdown).map(([key, val]) => (
                    <div key={key} className="text-center">
                      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden mb-2">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${(val as number) * 100}%`,
                            backgroundColor: (val as number) > 0.8 ? "#10b981" : (val as number) > 0.6 ? "#f59e0b" : "#ef4444",
                          }}
                        />
                      </div>
                      <p className="text-xs font-medium text-[var(--umd-black)] capitalize">{key.replace(/_/g, " ")}</p>
                      <p className="text-xs text-[var(--umd-gray)]">{Math.round((val as number) * 100)}%</p>
                    </div>
                  ))}
                </div>

                {/* Sections list */}
                <div className="mt-5 pt-5 border-t border-black/5">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {schedules[activeSchedule].sections.map((sec, idx) => (
                      <div key={sec.section_id} className="flex items-center gap-3 p-3 rounded-xl bg-[var(--umd-light)]">
                        <div className={`w-2 h-10 rounded-full ${getCourseColor(sec.course_id, idx).split(" ")[0] || "bg-gray-400"}`} />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-bold text-[var(--umd-black)]">{sec.course_id}</p>
                          <p className="text-xs text-[var(--umd-gray)]">
                            {sec.professor} &middot; {sec.section_id} &middot; {sec.open_seats} seats
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Export button */}
              <div className="mt-4 flex gap-3">
                <button
                  onClick={() => scheduleApi.exportIcal(selectedCourses)}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--umd-black)] text-white text-sm font-semibold hover:bg-[var(--umd-black)]/80 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  Export to Calendar (.ics)
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SchedulePage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-400">Loading...</div>}>
      <SchedulePageInner />
    </Suspense>
  );
}
