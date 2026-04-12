"use client";

import { useState, useEffect, useRef } from "react";
import { courseApi } from "@/lib/api";
import type { CourseDetail } from "@/types";

interface CourseSearchProps {
  onSelect: (course: CourseDetail) => void;
  placeholder?: string;
  variant?: "default" | "compact";
}

export default function CourseSearch({
  onSelect,
  placeholder = "Search courses (e.g., CMSC131, Calculus)...",
  variant = "default",
}: CourseSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CourseDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }

    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await courseApi.search(query);
        setResults(data.slice(0, 10));
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(debounceRef.current);
  }, [query]);

  const compact = variant === "compact";
  const inputClass = compact
    ? "w-full pl-9 pr-3 py-1.5 rounded-md border border-[var(--border-dark)] text-sm bg-[var(--bg-elevated)] text-[var(--text-primary)] placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/30 focus:border-[var(--umd-red)]"
    : "w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border-dark)] text-sm bg-[var(--bg-secondary)] text-[var(--text-primary)] placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/30 focus:border-[var(--umd-red)]";

  const iconClass = compact
    ? "absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/50"
    : "absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/50";

  return (
    <div ref={ref} className="relative">
      <div className="relative">
        <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className={inputClass}
        />
        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-[var(--umd-red)]/30 border-t-[var(--umd-red)] rounded-full animate-spin" />
          </div>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-dark)] shadow-xl max-h-64 overflow-y-auto">
          {results.map((course) => (
            <button
              key={course.course_id}
              onClick={() => {
                onSelect(course);
                setQuery("");
                setOpen(false);
              }}
              className="w-full px-4 py-2.5 text-left hover:bg-[var(--bg-elevated)] transition-colors border-b border-[var(--border-dark)] last:border-b-0"
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{course.course_id}</span>
                  <span className="text-sm text-[var(--text-muted)] ml-2">{course.name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-[var(--text-muted)]">{course.credits} cr</span>
                  {course.avg_gpa && (
                    <span className="text-xs font-medium bg-emerald-500/15 text-emerald-300 px-1.5 py-0.5 rounded">
                      {course.avg_gpa.toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {open && query.length >= 2 && results.length === 0 && !loading && (
        <div className="absolute z-50 mt-1 w-full bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-dark)] shadow-xl p-4 text-center text-sm text-[var(--text-muted)]">
          No courses found for &ldquo;{query}&rdquo;
        </div>
      )}
    </div>
  );
}
