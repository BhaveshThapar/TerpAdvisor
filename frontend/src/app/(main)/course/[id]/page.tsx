"use client";

import { useState, useEffect, use } from "react";
import Link from "next/link";
import type { CourseDetail, CourseSectionBrief, Review } from "@/types";
import { courseApi } from "@/lib/api";
import { addToCart, addToWishlist, isInWishlist, getCompletedCourseIds, useUserStore } from "@/lib/userStore";

/* ── Helpers ─────────────────────────────────────── */

function formatTime(time: string): string {
  const [h, m] = time.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `${h12}:${m.toString().padStart(2, "0")} ${ampm}`;
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
}

function gpaBadgeColor(gpa: number | null): string {
  if (!gpa) return "bg-gray-100 text-gray-600";
  if (gpa >= 3.5) return "bg-emerald-100 text-emerald-700";
  if (gpa >= 3.0) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

function sentimentFromRating(rating: number | null): { label: string; color: string } {
  if (!rating) return { label: "N/A", color: "bg-gray-100 text-gray-600" };
  if (rating >= 4) return { label: "Positive", color: "bg-emerald-100 text-emerald-700" };
  if (rating >= 3) return { label: "Mixed", color: "bg-amber-100 text-amber-700" };
  return { label: "Negative", color: "bg-red-100 text-red-700" };
}

function StarRating({ rating }: { rating: number | null }) {
  if (!rating) return null;
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <svg
          key={star}
          className={`w-4 h-4 ${star <= rating ? "text-[var(--umd-gold)]" : "text-gray-200"}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="max-w-4xl mx-auto animate-pulse space-y-6">
      <div className="h-4 bg-gray-200 rounded w-48" />
      <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
        <div className="h-8 bg-gray-200 rounded w-40 mb-2" />
        <div className="h-5 bg-gray-200 rounded w-64 mb-4" />
        <div className="h-16 bg-gray-100 rounded" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl p-6 border border-black/5 h-64" />
        <div className="space-y-6">
          <div className="bg-white rounded-2xl p-6 border border-black/5 h-28" />
          <div className="bg-white rounded-2xl p-6 border border-black/5 h-28" />
        </div>
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────── */

export default function CourseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wishlisted, setWishlisted] = useState(false);
  // Derive cart state reactively from the store so it stays in sync with the
  // CartDrawer and any other component that mutates the cart.
  const cartSet = useUserStore((s) => new Set(s.cart));
  const cartAdded = course ? cartSet.has(course.course_id) : false;

  function handleAddToWishlist() {
    if (!course) return;
    addToWishlist(course.course_id);
    setWishlisted(true);
  }

  function handleAddToCart() {
    if (!course) return;
    addToCart(course.course_id);
  }

  useEffect(() => {
    async function loadCourse() {
      try {
        const completedIds = getCompletedCourseIds();
        const data = await courseApi.getDetail(id, completedIds);
        setCourse(data);
        setWishlisted(isInWishlist(data.course_id));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load course");
      } finally {
        setLoading(false);
      }
    }
    loadCourse();
  }, [id]);

  if (loading) return <LoadingSkeleton />;

  if (error || !course) {
    return (
      <div className="max-w-4xl mx-auto text-center py-16">
        <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
        <p className="text-lg font-medium text-[var(--umd-gray)]">
          {error?.includes("404") ? "Course not found" : "Could not load course data"}
        </p>
        <p className="text-sm text-[var(--umd-gray)] mt-1">{error || "Unknown error"}</p>
        <div className="mt-4 flex items-center justify-center gap-3">
          <button onClick={() => window.location.reload()} className="px-4 py-2 bg-[var(--umd-red)] text-white rounded-lg text-sm">
            Retry
          </button>
          <Link href="/recommendations" className="px-4 py-2 border border-black/10 rounded-lg text-sm text-[var(--umd-gray)] hover:text-[var(--umd-black)]">
            Browse Courses
          </Link>
        </div>
      </div>
    );
  }

  const totalStudents = Object.values(course.grade_distribution).reduce((a, b) => a + b, 0);
  const maxGradeCount = totalStudents > 0 ? Math.max(...Object.values(course.grade_distribution)) : 1;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-[var(--umd-gray)] mb-6">
        <Link href="/recommendations" className="hover:text-[var(--umd-red)] transition-colors">
          Courses
        </Link>
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        <span className="text-[var(--umd-black)] font-medium">{course.course_id}</span>
      </div>

      {/* Course header */}
      <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm mb-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold text-[var(--umd-black)]">{course.course_id}</h1>
              <span className={`text-xs font-bold px-3 py-1 rounded-full ${gpaBadgeColor(course.avg_gpa)}`}>
                Avg GPA: {course.avg_gpa?.toFixed(2) || "N/A"}
              </span>
            </div>
            <h2 className="text-lg text-[var(--umd-gray)] mt-1">{course.name}</h2>
            <div className="flex items-center gap-4 mt-3 flex-wrap">
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--umd-gray)]">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21" />
                </svg>
                {course.department}
              </span>
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--umd-gray)]">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {course.credits} credits
              </span>
              {course.gen_eds.length > 0 && (
                <span className="text-xs text-[var(--umd-gray)]">
                  Gen-Eds: {course.gen_eds.join(", ")}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleAddToWishlist}
              disabled={wishlisted}
              title={wishlisted ? "Already wishlisted" : "Add to Wishlist"}
              className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl border transition-colors shadow-sm ${
                wishlisted
                  ? "border-[var(--umd-gold)]/50 bg-[var(--umd-gold)]/10 text-[var(--umd-black)] cursor-default"
                  : "border-black/10 bg-white text-[var(--umd-black)] hover:border-[var(--umd-gold)]/50 hover:bg-[var(--umd-gold)]/5"
              }`}
            >
              <svg className="w-4 h-4" fill={wishlisted ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
              </svg>
              {wishlisted ? "Wishlisted ✓" : "Add to Wishlist"}
            </button>
            <button
              onClick={handleAddToCart}
              disabled={cartAdded}
              className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl border transition-colors shadow-sm ${
                cartAdded
                  ? "border-emerald-300 bg-emerald-50 text-emerald-700 cursor-default"
                  : "border-black/10 bg-white text-[var(--umd-black)] hover:border-[var(--umd-red)]/30 hover:bg-[var(--umd-red)]/5"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 00-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.962-7.138a60.114 60.114 0 00-16.536-1.84M7.5 14.25L5.106 5.272M6 20.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm12.75 0a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
              </svg>
              {cartAdded ? "Added ✓" : "Add to Cart"}
            </button>
            <Link
              href={`/schedule?courses=${course.course_id}`}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--umd-red)] text-white text-sm font-semibold rounded-xl hover:bg-[var(--umd-red)]/90 transition-colors shadow-sm"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Add to Schedule
            </Link>
          </div>
        </div>
        <p className="text-sm text-[var(--umd-gray)] mt-4 leading-relaxed">{course.description}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Grade Distribution */}
        <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
          <h3 className="text-base font-bold text-[var(--umd-black)] mb-1">Grade Distribution</h3>
          <p className="text-xs text-[var(--umd-gray)] mb-5">
            {totalStudents > 0 ? `${totalStudents} students total` : "Grade breakdown unavailable — avg GPA shown above"}
          </p>
          {totalStudents === 0 ? null : (
          <div className="space-y-2.5">
            {Object.entries(course.grade_distribution).map(([grade, count]) => {
              const pct = (count / maxGradeCount) * 100;
              const isARange = grade.startsWith("A");
              const isBRange = grade.startsWith("B");
              const barColor = isARange
                ? "bg-emerald-500"
                : isBRange
                ? "bg-[var(--umd-gold)]"
                : "bg-[var(--umd-red)]";

              return (
                <div key={grade} className="flex items-center gap-3">
                  <span className="text-xs font-mono font-bold text-[var(--umd-black)] w-6 text-right">{grade}</span>
                  <div className="flex-1 h-5 bg-gray-100 rounded-md overflow-hidden">
                    <div
                      className={`h-full ${barColor} rounded-md transition-all duration-500 flex items-center justify-end pr-2`}
                      style={{ width: `${Math.max(pct, 4)}%` }}
                    >
                      {pct > 15 && (
                        <span className="text-[10px] font-bold text-white">{count}</span>
                      )}
                    </div>
                  </div>
                  {pct <= 15 && (
                    <span className="text-xs text-[var(--umd-gray)] w-6">{count}</span>
                  )}
                </div>
              );
            })}
          </div>
          )}
        </div>

        {/* Prerequisites and Requirements */}
        <div className="space-y-6">
          {/* Prerequisites */}
          <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
            <h3 className="text-base font-bold text-[var(--umd-black)] mb-4">Prerequisites</h3>
            {course.prerequisites.length === 0 && !course.prerequisites_text ? (
              <p className="text-sm text-[var(--umd-gray)]">No prerequisites required.</p>
            ) : (
              <div className="space-y-3">
                {course.prerequisites_text && (
                  <p className="text-xs text-[var(--umd-gray)] leading-relaxed bg-gray-50 rounded-lg px-3 py-2">
                    {course.prerequisites_text}
                  </p>
                )}
                {course.prerequisites.length > 0 && (
                  <div className="space-y-2">
                    {course.prerequisites.map((prereq) => {
                      const completed = course.prereqs_completed.includes(prereq);
                      return (
                        <div
                          key={prereq}
                          className={`flex items-center gap-3 p-3 rounded-xl ${
                            completed ? "bg-emerald-50" : "bg-red-50"
                          }`}
                        >
                          {completed ? (
                            <div className="w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center shrink-0">
                              <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                              </svg>
                            </div>
                          ) : (
                            <div className="w-6 h-6 rounded-full bg-red-500 flex items-center justify-center shrink-0">
                              <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </div>
                          )}
                          <div>
                            <span className="text-sm font-medium text-[var(--umd-black)]">{prereq}</span>
                            <span className={`ml-2 text-xs ${completed ? "text-emerald-600" : "text-red-600"}`}>
                              {completed ? "Completed" : "Remaining"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Fulfills Requirements */}
          <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
            <h3 className="text-base font-bold text-[var(--umd-black)] mb-4">Fulfills Requirements</h3>
            <div className="space-y-2">
              {course.fulfills_requirements.map((req) => (
                <div key={req} className="flex items-center gap-3 p-3 rounded-xl bg-[var(--umd-gold)]/10">
                  <div className="w-6 h-6 rounded-full bg-[var(--umd-gold)] flex items-center justify-center shrink-0">
                    <svg className="w-3.5 h-3.5 text-[var(--umd-black)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342" />
                    </svg>
                  </div>
                  <span className="text-sm font-medium text-[var(--umd-black)]">{req}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Professors */}
          <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
            <h3 className="text-base font-bold text-[var(--umd-black)] mb-4">Professors</h3>
            <div className="space-y-3">
              {course.professors.map((prof) => (
                <div key={prof.name} className="flex items-center justify-between p-3 rounded-xl bg-[var(--umd-light)]">
                  <div>
                    <Link
                      href={`/professor/${slugify(prof.name)}`}
                      className="text-sm font-medium text-[var(--umd-black)] hover:text-[var(--umd-red)] transition-colors"
                    >
                      {prof.name}
                    </Link>
                    <p className="text-xs text-[var(--umd-gray)]">{prof.review_count} reviews</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StarRating rating={Math.round(prof.avg_rating || 0)} />
                    <span className="text-sm font-bold text-[var(--umd-black)]">{prof.avg_rating?.toFixed(1)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Sections / Meeting Times */}
          {course.sections && course.sections.length > 0 && (
            <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
              <h3 className="text-base font-bold text-[var(--umd-black)] mb-4">Class Times</h3>
              <div className="space-y-2">
                {course.sections.map((sec: CourseSectionBrief) => (
                  <div key={sec.section_id} className="flex items-center justify-between p-3 rounded-xl bg-[var(--umd-light)]">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[var(--umd-black)]">{sec.section_id}</p>
                      <p className="text-xs text-[var(--umd-gray)]">{sec.professor} &middot; {sec.semester}</p>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <p className="text-sm font-semibold text-[var(--umd-black)]">{sec.days}</p>
                      <p className="text-xs text-[var(--umd-gray)]">{formatTime(sec.start_time)} &ndash; {formatTime(sec.end_time)}</p>
                      <p className="text-xs text-[var(--umd-gray)]">{sec.open_seats}/{sec.total_seats} seats</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Reviews */}
      {course.reviews.length > 0 && (
        <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm mb-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-base font-bold text-[var(--umd-black)]">Student Reviews</h3>
              <p className="text-xs text-[var(--umd-gray)] mt-0.5">{course.reviews.length} reviews</p>
            </div>
            {(() => {
              const avgRating = course.reviews.reduce((a, r) => a + (r.rating || 0), 0) / course.reviews.length;
              const sentiment = sentimentFromRating(avgRating);
              return (
                <span className={`text-xs font-bold px-3 py-1.5 rounded-full ${sentiment.color}`}>
                  {sentiment.label}
                </span>
              );
            })()}
          </div>
          <div className="space-y-4">
            {course.reviews.map((review: Review, i: number) => (
              <div key={i} className="p-4 rounded-xl bg-[var(--umd-light)] border border-black/5">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <StarRating rating={review.rating} />
                    {review.professor && (
                      <span className="text-xs text-[var(--umd-gray)]">Prof. {review.professor}</span>
                    )}
                  </div>
                  {review.created_at && (
                    <span className="text-xs text-[var(--umd-gray)]">
                      {new Date(review.created_at).toLocaleDateString("en-US", { month: "short", year: "numeric" })}
                    </span>
                  )}
                </div>
                <p className="text-sm text-[var(--umd-black)] leading-relaxed">{review.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
