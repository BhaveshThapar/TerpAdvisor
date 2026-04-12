"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { planApi } from "@/lib/api";
import { getCompletedCourseIds, getState, useUserStore } from "@/lib/userStore";
import type { MultiSemesterPlan, SemesterPlan } from "@/types";

function SemesterCard({ semester }: { semester: SemesterPlan }) {
  return (
    <div className="bg-[var(--bg-secondary)] rounded-2xl border border-[var(--border-dark)] shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-[var(--text-primary)]">{semester.semester_label}</h3>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">Semester {semester.semester_number}</p>
        </div>
        <span className="text-xs font-semibold bg-[var(--umd-red)]/10 text-[var(--umd-red)] px-2.5 py-1 rounded-full">
          {semester.total_credits} cr
        </span>
      </div>
      <div className="space-y-2">
        {semester.courses.map((courseId) => (
          <Link
            key={courseId}
            href={`/course/${courseId}`}
            className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[var(--umd-light)] hover:bg-[var(--bg-elevated)] transition-colors group"
          >
            <span className="w-2 h-2 rounded-full bg-[var(--umd-red)] shrink-0" />
            <span className="text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--umd-red)] transition-colors">
              {courseId}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function PlanPage() {
  const [plan, setPlan] = useState<MultiSemesterPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [maxCredits, setMaxCredits] = useState(16);
  const [startSemester, setStartSemester] = useState("Fall 2026");
  // Subscribe to completed courses so the plan regenerates when the user
  // adds courses (e.g. transcript parsing) without a manual page refresh.
  const completedCourses = useUserStore((s) => s.completedCourses);

  async function generatePlan() {
    setLoading(true);
    setError(null);
    try {
      const completedIds = getCompletedCourseIds();
      const state = getState();
      const major = state.major || "Computer Science";
      const track = state.track || "General";
      const data = await planApi.generate(completedIds, major, track, {
        max_credits_per_semester: maxCredits,
        start_semester: startSemester,
      });
      setPlan(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate plan");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    generatePlan();
  // Re-generate whenever completed courses change in the store.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [completedCourses]);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Graduation Plan</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          A semester-by-semester roadmap to graduation, respecting prerequisite ordering.
        </p>
      </div>

      {/* Controls */}
      <div className="bg-[var(--bg-secondary)] rounded-2xl border border-[var(--border-dark)] shadow-sm p-5 mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1.5">Max Credits / Semester</label>
          <select
            value={maxCredits}
            onChange={(e) => setMaxCredits(Number(e.target.value))}
            className="text-sm border border-[var(--border-dark)] rounded-lg px-3 py-2 bg-[var(--bg-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/30"
          >
            {[6, 9, 12, 13, 14, 15, 16, 17, 18].map((n) => (
              <option key={n} value={n}>{n} credits</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1.5">Start Semester</label>
          <select
            value={startSemester}
            onChange={(e) => setStartSemester(e.target.value)}
            className="text-sm border border-[var(--border-dark)] rounded-lg px-3 py-2 bg-[var(--bg-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/30"
          >
            {["Fall 2025", "Spring 2026", "Fall 2026", "Spring 2027", "Fall 2027"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <button
          onClick={generatePlan}
          disabled={loading}
          className="py-2 px-5 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors disabled:opacity-50"
        >
          {loading ? "Generating…" : "Regenerate"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 px-4 py-3 bg-red-500/10 border border-red-200 rounded-xl text-sm text-red-300">{error}</div>
      )}

      {/* Loading skeleton */}
      {loading && !plan && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-[var(--bg-secondary)] rounded-2xl border border-[var(--border-dark)] shadow-sm p-5 animate-pulse">
              <div className="h-4 bg-[var(--bg-elevated)] rounded w-1/2 mb-2" />
              <div className="h-3 bg-[var(--bg-elevated)] rounded w-1/4 mb-4" />
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, j) => (
                  <div key={j} className="h-8 bg-[var(--bg-elevated)] rounded-lg" />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Plan */}
      {plan && !loading && (
        <>
          {/* Summary bar */}
          <div className="flex flex-wrap gap-4 mb-6">
            <div className="bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-dark)] shadow-sm px-4 py-3 text-center min-w-[100px]">
              <p className="text-2xl font-bold text-[var(--umd-red)]">{plan.total_semesters}</p>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">Semesters</p>
            </div>
            <div className="bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-dark)] shadow-sm px-4 py-3 text-center min-w-[100px]">
              <p className="text-2xl font-bold text-[var(--text-primary)]">{plan.total_credits}</p>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">Credits</p>
            </div>
            <div className="bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-dark)] shadow-sm px-4 py-3 text-center min-w-[100px]">
              <p className="text-2xl font-bold text-[var(--text-primary)]">
                {plan.semesters.reduce((s, sem) => s + sem.courses.length, 0)}
              </p>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">Courses</p>
            </div>
          </div>

          {/* Warnings */}
          {plan.warnings.length > 0 && (
            <div className="mb-6 px-4 py-3 bg-amber-500/10 border border-amber-200 rounded-xl">
              <p className="text-xs font-bold text-amber-300 mb-1">Scheduling Notes</p>
              <ul className="space-y-1">
                {plan.warnings.map((w, i) => (
                  <li key={i} className="text-xs text-amber-300">• {w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Semester grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {plan.semesters.map((sem) => (
              <SemesterCard key={sem.semester_number} semester={sem} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
