"use client";

import Link from "next/link";
import { useState, useEffect, useMemo } from "react";
import { recommendationApi, auditApi } from "@/lib/api";
import { getCompletedCourseIds, getState } from "@/lib/userStore";
import type { Recommendation, AuditResult, UserPreferences } from "@/types";
import { DEFAULT_WEIGHTS } from "@/types";
import CircularProgress from "@/components/ui/CircularProgress";

function DifficultyBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    Easy: "bg-emerald-100 text-emerald-700",
    Medium: "bg-amber-100 text-amber-700",
    Hard: "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${colors[level] || "bg-gray-100 text-gray-600"}`}>
      {level}
    </span>
  );
}


function ArrowIcon() {
  return (
    <div className="w-9 h-9 rounded-full bg-white/80 flex items-center justify-center shadow-sm group-hover:bg-white group-hover:shadow-md transition-all">
      <svg className="w-4 h-4 text-[var(--umd-black)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
      </svg>
    </div>
  );
}

export default function HomePage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [cartCount, setCartCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const completedIds = getCompletedCourseIds();
        const state = getState();
        const major = state.major;
        const track = state.track || "General";
        
        setCartCount(state.cart.length);

        const prefs: UserPreferences = state.preferences || { filters: null, weight_overrides: null, preference_tags: null, schedule_preferences: null };
        const weights = { ...DEFAULT_WEIGHTS, ...(prefs.weight_overrides || {}) };
        
        const [recData, auditData] = await Promise.all([
          recommendationApi.get(completedIds, major, track, weights, 20, prefs.preference_tags || undefined, prefs.filters || undefined),
          auditApi.get(completedIds, major, track)
        ]);
        
        setRecommendations(recData.recommendations || []);
        setAudit(auditData);
      } catch (err) {
        console.error("Failed to load dashboard data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const topDepartments = useMemo(() => {
    if (recommendations.length === 0) return [];
    const counts: Record<string, number> = {};
    recommendations.forEach(r => {
      const dept = r.course_id.replace(/[0-9].*/, "");
      counts[dept] = (counts[dept] || 0) + 1;
    });
    const colors = ["#2563eb", "#e21833", "#16a34a", "#f59e0b", "#6366f1"];
    
    return Object.entries(counts)
      .sort((a,b) => b[1] - a[1])
      .slice(0, 3)
      .map(([dept, count], idx) => ({
        name: dept,
        code: dept,
        color: colors[idx % colors.length],
        pct: Math.round((count / recommendations.length) * 100)
      }));
  }, [recommendations]);

  const displayedRecs = recommendations.slice(0, 5);

  return (
    <div className="max-w-6xl mx-auto">
      {/* Greeting + Stat Badges */}
      <section className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-[var(--umd-black)] tracking-tight">
            Hello, Terp!
          </h1>
          <p className="text-base text-[var(--text-muted)] mt-1">
            Plan smarter semesters with AI-driven insights.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="bg-[var(--accent-blue)] text-white rounded-2xl px-5 py-3 flex items-center gap-3 shadow-md">
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
              </svg>
            </div>
            <div>
              <p className="text-lg font-bold leading-tight">4,200+</p>
              <p className="text-xs text-white/80">courses indexed</p>
            </div>
          </div>
          <div className="bg-[var(--accent-blue)] text-white rounded-2xl px-5 py-3 flex items-center gap-3 shadow-md">
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-lg font-bold leading-tight">16 hours</p>
              <p className="text-xs text-white/80">saved planning</p>
            </div>
          </div>
        </div>
      </section>

      {/* Bento Feature Grid */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <Link href="/recommendations" className="group">
          <div className="bg-[var(--card-beige)] rounded-2xl p-6 h-full flex flex-col justify-between min-h-[200px] transition-all hover:shadow-lg hover:-translate-y-0.5">
            <div>
              <h3 className="text-base font-semibold text-[var(--umd-black)] mb-1">
                Recommendations
              </h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                AI-powered course suggestions based on your goals, GPA, and reviews.
              </p>
            </div>
            <div className="flex items-end justify-between mt-6">
              <p className="text-5xl font-bold text-[var(--umd-black)] tracking-tight leading-none">
                {loading ? "..." : recommendations.length}
              </p>
              <ArrowIcon />
            </div>
          </div>
        </Link>

        <Link href="/dashboard" className="group">
          <div className="bg-[var(--card-blue)] rounded-2xl p-6 h-full flex flex-col justify-between min-h-[200px] transition-all hover:shadow-lg hover:-translate-y-0.5">
            <div>
              <h3 className="text-base font-semibold text-[var(--umd-black)] mb-1">
                Degree Tracking
              </h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                Real-time progress toward your degree requirements.
              </p>
            </div>
            <div className="flex items-end justify-between mt-6">
              <p className="text-5xl font-bold text-[var(--umd-black)] tracking-tight leading-none">
                {loading ? "..." : (audit?.courses_remaining?.length ?? 0)}
              </p>
              <ArrowIcon />
            </div>
          </div>
        </Link>

        <Link href="/schedule" className="group">
          <div className="bg-[var(--card-gray)] rounded-2xl p-6 h-full flex flex-col justify-between min-h-[200px] transition-all hover:shadow-lg hover:-translate-y-0.5">
            <div>
              <h3 className="text-base font-semibold text-[var(--umd-black)] mb-1">
                Schedule Builder
              </h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                Conflict-free schedules optimized for your preferences.
              </p>
            </div>
            <div className="flex items-end justify-between mt-6">
              <div className="flex items-baseline gap-2">
                <p className="text-5xl font-bold text-[var(--umd-black)] tracking-tight leading-none">
                  {cartCount}
                </p>
                <span className="text-sm font-medium text-[var(--text-muted)] mb-1">in cart</span>
              </div>
              <ArrowIcon />
            </div>
          </div>
        </Link>
      </section>

      {/* Main Content: Recommendations Table + Sidebar Widgets */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-8">
        {/* Recommendations Table — 2/3 width */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-[var(--border-subtle)] shadow-sm">
          <div className="px-6 pt-5 pb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-[var(--umd-black)]">
                Latest recommendations
              </h2>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                {displayedRecs.length} courses displayed
              </p>
            </div>
          </div>

          {/* Table header */}
          <div className="px-6 py-2.5 border-t border-b border-[var(--border-subtle)] grid grid-cols-12 gap-3 text-xs font-medium text-[var(--text-muted)]">
            <span className="col-span-5">Course</span>
            <span className="col-span-2 text-center">Match</span>
            <span className="col-span-3 text-center">Difficulty</span>
            <span className="col-span-2 text-center">Rating</span>
          </div>

          {/* Table rows */}
          <div className="divide-y divide-[var(--border-subtle)]">
            {displayedRecs.map((rec) => {
              const dept = rec.course_id.replace(/[0-9].*/, "");
              const matchPct = Math.round(rec.final_score);
              const difficulty = rec.confidence > 0.8 ? "Easy" : rec.confidence > 0.6 ? "Medium" : "Hard"; // mock since Recommendation doesn't have it explicitly mapped like this natively easily
              
              return (
                <Link
                  key={rec.course_id}
                  href={`/course/${rec.course_id}`}
                  className="px-6 py-3.5 grid grid-cols-12 gap-3 items-center hover:bg-[var(--card-gray)]/50 transition-colors"
                >
                  <div className="col-span-5 flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-[var(--card-blue)] flex items-center justify-center text-xs font-bold text-[var(--accent-blue)]">
                      {dept.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[var(--umd-black)] truncate">
                        {rec.course_id}
                      </p>
                      <p className="text-xs text-[var(--text-muted)] truncate" title={rec.top_reason}>
                        {rec.top_reason.length > 35 ? rec.top_reason.slice(0, 35) + "..." : rec.top_reason}
                      </p>
                    </div>
                  </div>
                  <div className="col-span-2 text-center">
                    <span className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--accent-blue)]">
                      {matchPct}%
                    </span>
                  </div>
                  <div className="col-span-3 text-center">
                    <DifficultyBadge level={difficulty} />
                  </div>
                  <div className="col-span-2 text-center">
                    <span className="text-sm text-[var(--umd-black)] font-medium">
                      {(rec.confidence * 5).toFixed(1)}
                    </span>
                    <span className="text-xs text-[var(--text-muted)]"> / 5</span>
                  </div>
                </Link>
              );
            })}
          </div>

          {!loading && displayedRecs.length === 0 && (
            <div className="px-6 py-10 text-center text-sm text-[var(--text-muted)]">
              No recommendations found yet.
            </div>
          )}
        </div>

        {/* Sidebar Widgets — 1/3 width */}
        <div className="flex flex-col gap-5">
          {/* Progress Gauge */}
          <div className="bg-white rounded-2xl border border-[var(--border-subtle)] shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-[var(--umd-black)]">
                Your progress
              </h3>
              <button className="text-[var(--text-muted)] hover:text-[var(--umd-black)] transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM12.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM18.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
                </svg>
              </button>
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-4">Degree: {audit ? audit.major : "Loading..."}</p>
            <div className="flex justify-center mb-4">
              <CircularProgress value={loading ? 0 : Math.round(audit?.overall_progress_pct ?? 0)} color="var(--accent-blue)" />
            </div>
            <p className="text-center text-sm text-[var(--text-muted)]">
              {loading ? "..." : `${audit?.total_credits_completed ?? 0} of ${audit?.total_credits_required ?? 0} credits completed`}
            </p>
            <div className="mt-5 flex gap-2">
              <Link
                href="/dashboard"
                className="flex-1 text-center text-sm font-medium py-2.5 rounded-xl border border-[var(--border-subtle)] text-[var(--umd-black)] hover:bg-[var(--card-gray)] transition-colors"
              >
                View audit
              </Link>
              <Link
                href="/onboarding"
                className="flex-1 text-center text-sm font-medium py-2.5 rounded-xl bg-[var(--accent-blue)] text-white hover:bg-[var(--accent-blue-light)] transition-colors"
              >
                Update profile
              </Link>
            </div>
          </div>

          {/* Top Departments */}
          <div className="bg-white rounded-2xl border border-[var(--border-subtle)] shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-[var(--umd-black)]">
                Top departments
              </h3>
              <button className="text-[var(--text-muted)] hover:text-[var(--umd-black)] transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM12.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM18.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
                </svg>
              </button>
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-4">Based on your recommendations</p>

            {/* Stacked bar */}
            <div className="flex h-2.5 rounded-full overflow-hidden mb-5">
              {topDepartments.map((dept) => (
                <div
                  key={dept.code}
                  style={{ width: `${dept.pct}%`, backgroundColor: dept.color }}
                  className="first:rounded-l-full last:rounded-r-full"
                />
              ))}
            </div>

            <div className="space-y-3.5">
              {topDepartments.map((dept) => (
                <div key={dept.code} className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: dept.color }}
                    />
                    <span className="text-sm text-[var(--umd-black)]">{dept.name}</span>
                  </div>
                  <span className="text-sm font-medium text-[var(--umd-black)]">{dept.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CTA Banner */}
      <section className="relative overflow-hidden bg-[var(--accent-blue)] rounded-2xl p-8 mb-8 flex flex-col sm:flex-row items-center justify-between gap-6">
        {/* Background decorative circles */}
        <div className="absolute -right-10 -top-10 w-40 h-40 rounded-full bg-white/10" />
        <div className="absolute -right-5 -bottom-12 w-28 h-28 rounded-full bg-white/5" />

        <div className="relative z-10">
          <div className="inline-flex items-center gap-1.5 bg-white/20 text-white text-xs font-semibold px-3 py-1 rounded-full mb-3">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
            AI-POWERED
          </div>
          <h2 className="text-xl font-bold text-white mb-1">
            Start planning your next semester
          </h2>
          <p className="text-sm text-white/80">
            Get personalized course recommendations and build your perfect schedule.
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-3 flex-shrink-0">
          <Link
            href="/onboarding"
            className="bg-white text-[var(--accent-blue)] font-semibold text-sm px-6 py-2.5 rounded-xl hover:bg-white/90 transition-colors shadow-md"
          >
            Get started
          </Link>
          <Link
            href="/schedule"
            className="bg-white/15 text-white font-semibold text-sm px-6 py-2.5 rounded-xl hover:bg-white/25 transition-colors border border-white/20"
          >
            Build schedule
          </Link>
        </div>
      </section>
    </div>
  );
}
