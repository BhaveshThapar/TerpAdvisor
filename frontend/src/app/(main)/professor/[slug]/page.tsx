"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { professorApi } from "@/lib/api";
import type { ProfessorDetail } from "@/types";

function StarRating({ rating }: { rating: number | null }) {
  if (!rating) return <span className="text-gray-400 text-sm">No rating</span>;
  return (
    <span className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= Math.round(rating) ? "text-yellow-400" : "text-gray-200"}>
          ★
        </span>
      ))}
      <span className="text-sm text-gray-500 ml-1">{rating.toFixed(1)}</span>
    </span>
  );
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
        <div className="bg-white rounded-2xl p-6 border border-black/5">
          <div className="h-8 bg-gray-200 rounded w-64 mb-4" />
          <div className="h-5 bg-gray-100 rounded w-40" />
        </div>
        <div className="bg-white rounded-2xl p-6 border border-black/5 h-32" />
        <div className="bg-white rounded-2xl p-6 border border-black/5 h-48" />
      </div>
    );
  }

  if (error || !prof) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Professor not found.</p>
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
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <button onClick={() => router.back()} className="hover:text-[#e21833] transition-colors">
          ← Back
        </button>
      </div>

      {/* Header */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-black/5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{prof.name}</h1>
            <div className="mt-2 flex items-center gap-3 flex-wrap">
              <StarRating rating={prof.avg_rating} />
              <span className="text-sm text-gray-400">{prof.review_count} reviews</span>
              <span className="text-sm text-gray-400">{prof.courses_taught.length} courses</span>
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
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-black/5">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Courses Taught</h2>
        {prof.courses_taught.length === 0 ? (
          <p className="text-gray-400 text-sm">No course data available.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {prof.courses_taught.map((cid) => (
              <Link
                key={cid}
                href={`/course/${cid}`}
                className="px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-[#e21833]/10 text-sm font-mono font-medium text-gray-700 hover:text-[#e21833] transition-colors"
              >
                {cid}
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Reviews */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-black/5">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Student Reviews</h2>
        {prof.reviews.length === 0 ? (
          <p className="text-gray-400 text-sm">No reviews yet.</p>
        ) : (
          <div className="space-y-4">
            {prof.reviews.map((r, i) => (
              <div key={i} className="border-b border-gray-100 pb-4 last:border-0">
                <div className="flex items-center gap-2 mb-1">
                  {r.rating !== null && <StarRating rating={r.rating} />}
                  {r.created_at && (
                    <span className="text-xs text-gray-400">
                      {new Date(r.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600">{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
