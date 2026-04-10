"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import type { AuditResult, Recommendation } from "@/types";
import { auditApi, recommendationApi } from "@/lib/api";
import { getState, updateProfile, useUserStore } from "@/lib/userStore";
import CircularProgress from "@/components/ui/CircularProgress";

function GpaBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 85 ? "bg-emerald-100 text-emerald-700" :
    pct >= 70 ? "bg-amber-100 text-amber-700" :
    "bg-red-100 text-red-700";
  return (
    <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${color}`}>{pct}</span>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-xl p-5 border border-black/5 shadow-sm">
            <div className="h-3 bg-gray-200 rounded w-24 mb-2" />
            <div className="h-8 bg-gray-200 rounded w-16" />
          </div>
        ))}
      </div>
      <div className="h-64 bg-white rounded-2xl border border-black/5" />
    </div>
  );
}

const ULC_DISCIPLINES: { label: string; prefix: string }[] = [
  { label: "Mathematics", prefix: "MATH" },
  { label: "Statistics", prefix: "STAT" },
  { label: "Economics", prefix: "ECON" },
  { label: "Physics", prefix: "PHYS" },
  { label: "Chemistry", prefix: "CHEM" },
  { label: "Biology", prefix: "BIOL" },
  { label: "Psychology", prefix: "PSYC" },
  { label: "Linguistics", prefix: "LING" },
  { label: "Philosophy", prefix: "PHIL" },
  { label: "Business (BMGT)", prefix: "BMGT" },
  { label: "Entrepreneurship", prefix: "ENTR" },
];

export default function DashboardPage() {
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ulcPrefix, setUlcPrefix] = useState<string | null>(getState().ulcPrefix ?? null);
  const [ulcEditing, setUlcEditing] = useState(false);
  // Subscribe to completed courses so the dashboard re-fetches whenever
  // the user adds/removes courses (e.g. after transcript parsing in onboarding).
  const completedCourses = useUserStore((s) => s.completedCourses);

  function handleUlcChange(prefix: string | null) {
    setUlcPrefix(prefix);
    updateProfile({ ulcPrefix: prefix });
    setUlcEditing(false);
  }

  useEffect(() => {
    async function load() {
      try {
        const completedCourses = getState().completedCourses;
        const major = getState().major;
        const track = getState().track || "General";
        const ulc = getState().ulcPrefix ?? null;

        const completedIds: string[] = [];
        const inProgressIds: string[] = [];
        const creditOverrides: Record<string, number> = {};
        const genEdsOverrides: Record<string, string[]> = {};

        for (const c of completedCourses) {
          if (c.in_progress) {
            inProgressIds.push(c.course_id);
          } else {
            completedIds.push(c.course_id);
          }
          if (c.credits != null) creditOverrides[c.course_id] = c.credits;
          if (c.gen_eds && c.gen_eds.length > 0) genEdsOverrides[c.course_id] = c.gen_eds;
        }

        const [auditData, recData] = await Promise.all([
          auditApi.get(completedIds, major, track, inProgressIds, creditOverrides, genEdsOverrides, ulc),
          recommendationApi.get(completedIds, major, track, undefined, 5),
        ]);
        setAudit(auditData);
        setRecs(recData.recommendations);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    load();
  // Re-run when ulcPrefix changes OR when completedCourses changes in the store
  // (which happens after transcript parsing, AP credit import, etc.)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ulcPrefix, completedCourses]);

  if (loading) return <LoadingSkeleton />;
  if (error || !audit) {
    return (
      <div className="text-center py-16">
        <p className="text-lg font-medium text-[var(--umd-gray)]">Failed to load dashboard</p>
        <p className="text-sm text-[var(--umd-gray)] mt-1">{error || "Unknown error"}</p>
        <button onClick={() => window.location.reload()} className="mt-4 px-4 py-2 bg-[var(--umd-red)] text-white rounded-lg text-sm">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[var(--umd-black)]">Dashboard</h1>
        <p className="text-sm text-[var(--umd-gray)] mt-1">Welcome back. Here is your academic overview.</p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Credits Completed", value: audit.total_credits_completed, accent: false },
          { label: "Credits Remaining", value: audit.total_credits_required - audit.total_credits_completed, accent: false },
          { label: "Courses Remaining", value: audit.total_courses_remaining, accent: true },
          { label: "Est. Semesters Left", value: Math.ceil(Math.max(audit.total_credits_required - audit.total_credits_completed, 0) / 15), accent: false },
        ].map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl p-5 border border-black/5 shadow-sm">
            <p className="text-xs font-medium text-[var(--umd-gray)] uppercase tracking-wider">{stat.label}</p>
            <p className={`text-3xl font-extrabold mt-1 ${stat.accent ? "text-[var(--umd-red)]" : "text-[var(--umd-black)]"}`}>
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Degree Progress */}
        <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm lg:col-span-1">
          <h2 className="text-base font-bold text-[var(--umd-black)] mb-1">Degree Progress</h2>
          <p className="text-xs text-[var(--umd-gray)] mb-6">{audit.major}</p>

          <div className="flex justify-center mb-8">
            <CircularProgress value={audit.overall_progress_pct} label="Complete" />
          </div>

          <div className="space-y-3">
            {audit.groups.map((group) => {
              const isComplete = group.progress_pct === 100;
              // For groups with a single requirement that tracks multiple courses (e.g. 400-level, ULC),
              // show courses_completed/courses_needed instead of requirements satisfied count.
              const singleReq = group.total_count === 1 ? group.requirements[0] : null;
              const displayNum = singleReq ? singleReq.courses_completed : group.completed_count;
              const displayDen = singleReq ? singleReq.courses_needed : (group.min_required ?? group.total_count);
              const barPct = singleReq
                ? Math.min(100, (singleReq.courses_completed / singleReq.courses_needed) * 100)
                : group.progress_pct;
              const isUlc = group.name.startsWith("Upper-Level Concentration");
              return (
                <div key={group.name}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-medium text-[var(--umd-black)]">{group.name}</span>
                    <span className="text-xs text-[var(--umd-gray)]">
                      {displayNum}/{displayDen}
                    </span>
                  </div>
                  {isUlc && (
                    <div className="mb-1.5">
                      {ulcEditing ? (
                        <div className="flex flex-wrap gap-1">
                          <button
                            onClick={() => handleUlcChange(null)}
                            className="text-xs px-2 py-0.5 rounded border border-gray-200 text-gray-400 hover:border-red-300"
                          >
                            Clear
                          </button>
                          {ULC_DISCIPLINES.map((d) => (
                            <button
                              key={d.prefix}
                              onClick={() => handleUlcChange(d.prefix)}
                              className={`text-xs px-2 py-0.5 rounded border transition-colors ${ulcPrefix === d.prefix ? "border-[var(--umd-red)] text-[var(--umd-red)] bg-red-50" : "border-gray-200 text-gray-500 hover:border-[var(--umd-red)]/40"}`}
                            >
                              {d.label}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <button
                          onClick={() => setUlcEditing(true)}
                          className="text-xs text-[var(--umd-gray)] hover:text-[var(--umd-red)] transition-colors"
                        >
                          {ulcPrefix
                            ? `Discipline: ${ULC_DISCIPLINES.find((d) => d.prefix === ulcPrefix)?.label ?? ulcPrefix} · change`
                            : "Set ULC discipline →"}
                        </button>
                      )}
                    </div>
                  )}
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${barPct}%`,
                        backgroundColor: isComplete ? "#10b981" : "var(--umd-red)",
                      }}
                    />
                  </div>
                  {!isComplete && (
                    <ul className="mt-1.5 space-y-0.5 pl-1">
                      {(group.min_required != null
                        ? group.requirements.filter((r) => r.status === "complete")
                        : group.requirements.filter((r) => r.status !== "complete")
                      ).map((r) => (
                        <li key={r.name} className="flex items-center gap-1.5 text-xs text-[var(--umd-gray)]">
                          <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${r.status === "complete" ? "bg-green-500" : r.status === "in_progress" ? "bg-yellow-400" : "bg-gray-300"}`} />
                          {r.name}
                          {r.credits_remaining > 0 && (
                            <span className="text-gray-400">({r.credits_remaining} cr)</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Recommended Courses */}
        <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-base font-bold text-[var(--umd-black)]">Recommended Courses</h2>
              <p className="text-xs text-[var(--umd-gray)] mt-0.5">Top picks for your next semester</p>
            </div>
            <Link
              href="/recommendations"
              className="text-xs font-semibold text-[var(--umd-red)] hover:text-[var(--umd-red)]/80 transition-colors"
            >
              View All &rarr;
            </Link>
          </div>

          {recs.length === 0 ? (
            <p className="text-sm text-[var(--umd-gray)] py-8 text-center">
              Add completed courses to get personalized recommendations.
            </p>
          ) : (
            <div className="space-y-3">
              {recs.map((rec) => (
                <Link
                  key={rec.course_id}
                  href={`/course/${rec.course_id}`}
                  className="flex items-center gap-4 p-4 rounded-xl border border-black/5 hover:border-[var(--umd-red)]/20 hover:shadow-md transition-all group"
                >
                  <div className="w-8 h-8 rounded-lg bg-[var(--umd-red)]/10 text-[var(--umd-red)] flex items-center justify-center text-sm font-bold shrink-0">
                    {rec.rank}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-[var(--umd-black)] group-hover:text-[var(--umd-red)] transition-colors">
                        {rec.course_id}
                      </span>
                      <GpaBadge score={rec.final_score} />
                    </div>
                    <p className="text-xs text-[var(--umd-gray)] mt-0.5 truncate">{rec.top_reason}</p>
                  </div>
                  <div className="hidden sm:flex flex-col items-end shrink-0">
                    <span className="text-xs text-[var(--umd-gray)]">Confidence</span>
                    <div className="w-20 h-1.5 bg-gray-100 rounded-full mt-1 overflow-hidden">
                      <div
                        className="h-full bg-[var(--umd-gold)] rounded-full"
                        style={{ width: `${rec.confidence * 100}%` }}
                      />
                    </div>
                  </div>
                  <svg className="w-4 h-4 text-gray-300 group-hover:text-[var(--umd-red)] transition-colors shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Remaining Courses */}
      {audit.courses_remaining.length > 0 && (
        <div className="mt-6 bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
          <h2 className="text-base font-bold text-[var(--umd-black)] mb-4">Courses Remaining</h2>
          <div className="flex flex-wrap gap-2">
            {audit.courses_remaining.map((courseId) => (
              <Link
                key={courseId}
                href={`/course/${courseId}`}
                className="px-3 py-1.5 bg-[var(--umd-light)] border border-black/5 rounded-lg text-sm font-medium text-[var(--umd-gray)] hover:text-[var(--umd-red)] hover:border-[var(--umd-red)]/20 transition-colors"
              >
                {courseId}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
