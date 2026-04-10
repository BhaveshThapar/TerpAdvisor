"use client";

import { useState, useEffect, useRef } from "react";
import { courseApi } from "@/lib/api";
import type { CourseDetail } from "@/types";

interface CourseSearchProps {
  onSelect: (course: CourseDetail) => void;
  placeholder?: string;
}

export default function CourseSearch({ onSelect, placeholder = "Search courses (e.g., CMSC131, Calculus)..." }: CourseSearchProps) {
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

  return (
    <div ref={ref} className="relative">
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--umd-gray)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-black/10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)]"
        />
        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-[var(--umd-red)]/30 border-t-[var(--umd-red)] rounded-full animate-spin" />
          </div>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full bg-white rounded-lg border border-black/10 shadow-lg max-h-64 overflow-y-auto">
          {results.map((course) => (
            <button
              key={course.course_id}
              onClick={() => {
                onSelect(course);
                setQuery("");
                setOpen(false);
              }}
              className="w-full px-4 py-2.5 text-left hover:bg-[var(--umd-light)] transition-colors border-b border-black/5 last:border-b-0"
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-semibold text-[var(--umd-black)]">{course.course_id}</span>
                  <span className="text-sm text-[var(--umd-gray)] ml-2">{course.name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-[var(--umd-gray)]">{course.credits} cr</span>
                  {course.avg_gpa && (
                    <span className="text-xs font-medium bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded">
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
        <div className="absolute z-50 mt-1 w-full bg-white rounded-lg border border-black/10 shadow-lg p-4 text-center text-sm text-[var(--umd-gray)]">
          No courses found for &ldquo;{query}&rdquo;
        </div>
      )}
    </div>
  );
}
