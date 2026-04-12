"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { professorApi } from "@/lib/api";
import type { ProfessorDetail } from "@/types";
import StarRating from "@/components/ui/StarRating";

function RatingDisplay({ rating }: { rating: number | null }) {
  if (!rating) return <span className="text-white/40 text-sm">No rating</span>;
  return <StarRating rating={rating} showValue />;
}

export default function ProfessorPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const [prof, setProf] = useState<ProfessorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    professorApi
      .getDetail(slug)
      .then(setProf)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto animate-pulse space-y-6 p-8">
        <div className="bg-[var(--bg-secondary)] rounded-2xl p-6 border border-[var(--border-dark)]">
          <div className="h-8 bg-white/10 rounded w-64 mb-4" />
          <div className="h-5 bg-[var(--bg-elevated)] rounded w-40" />
        </div>
        <div className="bg-[var(--bg-secondary)] rounded-2xl p-6 border border-[var(--border-dark)] h-32" />
        <div className="bg-[var(--bg-secondary)] rounded-2xl p-6 border border-[var(--border-dark)] h-48" />
      </div>
    );
  }

  if (error || !prof) {
    return (
      <div className="p-8">
        <p className="text-[var(--text-muted)]">Professor not found.</p>
        <button
          onClick={() => router.back()}
          className="mt-4 text-sm text-[#e21833]"
        >
          ← Go back
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        <button onClick={() => router.back()} className="hover:text-[#e21833] transition-colors">
          ← Back
        </button>
      </div>

      {/* Header */}
      <div className="bg-[var(--bg-secondary)] rounded-2xl p-6 shadow-sm border border-[var(--border-dark)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{prof.name}</h1>
            <div className="mt-2 flex items-center gap-3 flex-wrap">
              <RatingDisplay rating={prof.avg_rating} />
              <span className="text-sm text-white/40">{prof.review_count} reviews</span>
              <span className="text-sm text-white/40">{prof.courses_taught.length} courses</span>
            </div>
          </div>
          <button
            onClick={() => router.push(`/recommendations?professor=${slug}`)}
            className="px-4 py-2 rounded-xl text-sm font-semibold text-white shrink-0"
            style={{ backgroundColor: "#e21833" }}
          >
            Filter Recommendations
          </button>
        </div>
      </div>

      {/* Courses taught */}
      <div className="bg-[var(--bg-secondary)] rounded-2xl p-6 shadow-sm border border-[var(--border-dark)]">
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">Courses Taught</h2>
        {prof.courses_taught.length === 0 ? (
          <p className="text-white/40 text-sm">No course data available.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {prof.courses_taught.map((cid) => (
              <Link
                key={cid}
                href={`/course/${cid}`}
                className="px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] hover:bg-[#e21833]/10 text-sm font-mono font-medium text-white/80 hover:text-[#e21833] transition-colors"
              >
                {cid}
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Reviews */}
      <div className="bg-[var(--bg-secondary)] rounded-2xl p-6 shadow-sm border border-[var(--border-dark)]">
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">Student Reviews</h2>
        {prof.reviews.length === 0 ? (
          <p className="text-white/40 text-sm">No reviews yet.</p>
        ) : (
          <div className="space-y-4">
            {prof.reviews.map((r, i) => (
              <div key={i} className="border-b border-[var(--border-dark)] pb-4 last:border-0">
                <div className="flex items-center gap-2 mb-1">
                  {r.rating !== null && <StarRating rating={r.rating} />}
                  {r.created_at && (
                    <span className="text-xs text-white/40">
                      {new Date(r.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <p className="text-sm text-[var(--text-muted)]">{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
