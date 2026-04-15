"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { Recommendation, Explanation, WeightConfig, UserPreferences } from "@/types";
import { DEFAULT_WEIGHTS } from "@/types";
import { recommendationApi, professorApi } from "@/lib/api";
import {
  useUserStore, getCompletedCourseIds, getState,
  addToCart, isInCart, addToWishlist, removeFromWishlist, isInWishlist,
  updatePreferences,
} from "@/lib/userStore";

const FACTOR_LABELS: Record<string, string> = {
  requirement: "Requirement Fit",
  gpa: "GPA Potential",
  professor: "Professor Rating",
  sentiment: "Student Sentiment",
  collaborative: "Peer Similarity",
  schedule_fit: "Schedule Fit",
};

const FACTOR_COLORS: Record<string, string> = {
  requirement: "#e21833",
  gpa: "#10b981",
  professor: "#f59e0b",
  sentiment: "#6366f1",
  collaborative: "#ec4899",
  schedule_fit: "#06b6d4",
};

const UMD_DEPARTMENTS = ["CMSC", "MATH", "STAT", "ENGL", "BMGT", "INST", "PHYS", "CHEM", "BIOL", "PSYC"];

const ALL_PREFERENCE_TAGS = [
  "project-based",
  "no-final-exam",
  "discussion-heavy",
  "writing-intensive",
  "lab-required",
  "online",
  "no-attendance",
  "easy-a",
  "light-workload",
];

const COURSE_LEVELS = [100, 200, 300, 400];

/* ── Components ─────────────────────────────────── */

function WeightSlider({
  label,
  factor,
  value,
  onChange,
}: {
  label: string;
  factor: string;
  value: number;
  onChange: (factor: string, value: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-[var(--text-primary)]">{label}</span>
        <span className="text-xs font-bold text-[var(--text-muted)]">{Math.round(value * 100)}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={Math.round(value * 100)}
        onChange={(e) => onChange(factor, Number(e.target.value) / 100)}
        className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-[var(--umd-red)]"
      />
    </div>
  );
}

function RecommendationCard({
  rec,
  expanded,
  onToggle,
  inCart,
  onAddToCart,
  wishlisted,
  onToggleWishlist,
}: {
  rec: Recommendation;
  expanded: boolean;
  onToggle: () => void;
  inCart: boolean;
  onAddToCart: (course_id: string) => void;
  wishlisted: boolean;
  onToggleWishlist: (course_id: string) => void;
}) {
  const pct = Math.round(rec.final_score);
  return (
    <div className="bg-[var(--bg-secondary)] rounded-2xl border border-[var(--border-dark)] shadow-sm overflow-hidden hover:shadow-md transition-shadow">
      <div className="p-5">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-[var(--umd-red)] text-white flex items-center justify-center text-sm font-bold shrink-0">
            #{rec.rank}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <Link href={`/course/${rec.course_id}`} className="text-lg font-bold text-[var(--text-primary)] hover:text-[var(--umd-red)] transition-colors">
                {rec.course_id}
              </Link>
              <span className="text-xs font-bold bg-[var(--umd-gold)]/20 text-[var(--text-primary)] px-2.5 py-0.5 rounded-full">
                Score: {pct}
              </span>
            </div>
            <p className="text-sm text-[var(--text-muted)] mt-1">{rec.top_reason}</p>
            {rec.fulfills_requirements.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {rec.fulfills_requirements.map((groupId) => (
                  <span
                    key={groupId}
                    className="inline-flex items-center px-2 py-0.5 rounded-full bg-[var(--umd-red)]/10 text-[var(--umd-red)] text-[10px] font-semibold uppercase tracking-wide"
                  >
                    {groupId.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-3 flex items-center gap-3">
              <span className="text-xs text-[var(--text-muted)]">Confidence</span>
              <div className="flex-1 max-w-48 h-2 bg-[var(--bg-elevated)] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${rec.confidence * 100}%`,
                    backgroundColor: rec.confidence > 0.8 ? "#10b981" : rec.confidence > 0.6 ? "#f59e0b" : "#ef4444",
                  }}
                />
              </div>
              <span className="text-xs font-medium text-[var(--text-muted)]">{Math.round(rec.confidence * 100)}%</span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => onToggleWishlist(rec.course_id)}
              title={wishlisted ? "Remove from wishlist" : "Add to wishlist"}
              className={`w-8 h-8 rounded-lg border flex items-center justify-center transition-colors ${
                wishlisted
                  ? "border-[var(--umd-gold)]/50 bg-[var(--umd-gold)]/10 text-[var(--text-primary)]"
                  : "border-[var(--border-dark)] text-[var(--text-muted)] hover:border-[var(--umd-gold)]/50 hover:text-[var(--text-primary)]"
              }`}
            >
              <svg className="w-4 h-4" fill={wishlisted ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
              </svg>
            </button>
            <button
              onClick={() => onAddToCart(rec.course_id)}
              disabled={inCart}
              title={inCart ? "Already in cart" : "Add to cart"}
              className={`w-8 h-8 rounded-lg border flex items-center justify-center transition-colors ${
                inCart
                  ? "border-emerald-200 bg-emerald-500/10 text-emerald-500 cursor-default"
                  : "border-[var(--border-dark)] text-[var(--text-muted)] hover:border-[var(--umd-red)]/30 hover:text-[var(--umd-red)]"
              }`}
            >
              {inCart ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 00-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.962-7.138a60.114 60.114 0 00-16.536-1.84M7.5 14.25L5.106 5.272M6 20.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm12.75 0a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
                </svg>
              )}
            </button>
            <button
              onClick={onToggle}
              className="w-8 h-8 rounded-lg border border-[var(--border-dark)] flex items-center justify-center text-[var(--text-muted)] hover:bg-[var(--umd-light)] transition-colors"
            >
              <svg className={`w-4 h-4 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-[var(--border-dark)] bg-[var(--umd-light)]/50 p-5">
          <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-4">Score Breakdown</h4>
          <div className="space-y-3">
            {rec.explanations.map((exp) => (
              <div key={exp.factor}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-[var(--text-primary)]">{FACTOR_LABELS[exp.factor] || exp.factor}</span>
                  <span className="text-xs text-[var(--text-muted)]">{Math.round(exp.score * 100)} / 100</span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${exp.score * 100}%`, backgroundColor: FACTOR_COLORS[exp.factor] || "#888" }}
                  />
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-1">{exp.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Page ────────────────────────────────────────── */

function RecommendationsPageInner() {
  const searchParams = useSearchParams();
  const initialProfessor = searchParams.get("professor");

  const [weights, setWeights] = useState<WeightConfig>({ ...DEFAULT_WEIGHTS });
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [cartIds, setCartIds] = useState<Set<string>>(new Set());
  const [wishlistIds, setWishlistIds] = useState<Set<string>>(new Set());

  // Professor filter
  const [profSearchQuery, setProfSearchQuery] = useState("");
  const [profSearchResults, setProfSearchResults] = useState<Array<{ name: string; slug: string }>>([]);
  const [selectedProfessors, setSelectedProfessors] = useState<Array<{ name: string; slug: string }>>(
    initialProfessor ? [{ name: initialProfessor, slug: initialProfessor }] : []
  );
  const [profSearchOpen, setProfSearchOpen] = useState(false);
  const profDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Advanced filters state
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [minGpa, setMinGpa] = useState<number>(0);
  const [selectedLevels, setSelectedLevels] = useState<number[]>([]);
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [excludeInput, setExcludeInput] = useState("");
  const [excludedCourses, setExcludedCourses] = useState<string[]>([]);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [savedNotice, setSavedNotice] = useState(false);
  const [goal, setGoal] = useState<"balanced" | "easiest">("balanced");
  const [showPrereqOnly, setShowPrereqOnly] = useState(false);

  // Load preferences from local store on mount
  useEffect(() => {
    const prefs = getState().preferences;
    if (prefs) {
      if (prefs.weight_overrides) {
        setWeights((prev) => ({ ...prev, ...prefs.weight_overrides }));
      }
      if (prefs.preference_tags) {
        setSelectedTags(prefs.preference_tags);
      }
      if (prefs.filters) {
        if (prefs.filters.min_gpa != null) setMinGpa(prefs.filters.min_gpa);
        if (prefs.filters.levels) setSelectedLevels(prefs.filters.levels);
        if (prefs.filters.departments) setSelectedDepartments(prefs.filters.departments);
        if (prefs.filters.exclude_courses) setExcludedCourses(prefs.filters.exclude_courses);
      }
    }
    // Initialize cart/wishlist IDs from local store
    const state = getState();
    setCartIds(new Set(state.cart));
    setWishlistIds(new Set(state.wishlist));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleToggleWishlist(course_id: string) {
    if (wishlistIds.has(course_id)) {
      removeFromWishlist(course_id);
      setWishlistIds((prev) => {
        const next = new Set(prev);
        next.delete(course_id);
        return next;
      });
    } else {
      addToWishlist(course_id);
      setWishlistIds((prev) => new Set([...prev, course_id]));
    }
  }

  function handleAddToCart(course_id: string) {
    addToCart(course_id);
    setCartIds((prev) => new Set([...prev, course_id]));
  }

  const handleProfSearchChange = (q: string) => {
    setProfSearchQuery(q);
    if (profDebounceRef.current) clearTimeout(profDebounceRef.current);
    if (!q.trim()) {
      setProfSearchResults([]);
      setProfSearchOpen(false);
      return;
    }
    profDebounceRef.current = setTimeout(async () => {
      try {
        const results = await professorApi.search(q);
        setProfSearchResults(results);
        setProfSearchOpen(true);
      } catch {
        setProfSearchResults([]);
      }
    }, 300);
  };

  const handleSelectProfessor = (prof: { name: string; slug: string }) => {
    if (!selectedProfessors.find((p) => p.slug === prof.slug)) {
      setSelectedProfessors((prev) => [...prev, prof]);
    }
    setProfSearchQuery("");
    setProfSearchResults([]);
    setProfSearchOpen(false);
  };

  const handleRemoveProfessor = (slug: string) => {
    setSelectedProfessors((prev) => prev.filter((p) => p.slug !== slug));
  };

  function buildApiFilters(): UserPreferences["filters"] {
    const filters: NonNullable<UserPreferences["filters"]> = {};
    if (selectedDepartments.length > 0) filters.departments = selectedDepartments;
    if (selectedLevels.length > 0) filters.levels = selectedLevels;
    if (minGpa > 0) filters.min_gpa = minGpa;
    if (excludedCourses.length > 0) filters.exclude_courses = excludedCourses;
    if (selectedProfessors.length > 0) {
      filters.include_professors = selectedProfessors.map((p) => p.slug);
    }
    return Object.keys(filters).length > 0 ? filters : null;
  }

  const fetchRecs = useCallback(async (w: WeightConfig) => {
    setLoading(true);
    setError(null);
    try {
      const completedIds = getCompletedCourseIds();
      const major = getState().major;
      const track = getState().track || "General";
      const filters = buildApiFilters();
      const data = await recommendationApi.get(completedIds, major, track, w, 20, selectedTags.length > 0 ? selectedTags : undefined, filters ?? undefined, goal, showPrereqOnly);
      setRecommendations(data.recommendations);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch recommendations");
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTags, selectedDepartments, selectedLevels, minGpa, excludedCourses, selectedProfessors, goal, showPrereqOnly]);

  useEffect(() => {
    fetchRecs(weights);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const weightDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const filterDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(false);

  // Auto-refetch when advanced filter values change (debounced)
  useEffect(() => {
    if (!mountedRef.current) { mountedRef.current = true; return; }
    if (filterDebounceRef.current) clearTimeout(filterDebounceRef.current);
    filterDebounceRef.current = setTimeout(() => fetchRecs(weights), 400);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minGpa, selectedDepartments, selectedLevels, selectedTags, excludedCourses, selectedProfessors, goal, showPrereqOnly]);

  const handleWeightChange = (factor: string, value: number) => {
    const next = { ...weights, [factor]: value };
    setWeights(next);
    if (weightDebounceRef.current) clearTimeout(weightDebounceRef.current);
    weightDebounceRef.current = setTimeout(() => fetchRecs(next), 500);
  };

  const handleApplyWeights = () => {
    if (weightDebounceRef.current) clearTimeout(weightDebounceRef.current);
    fetchRecs(weights);
  };

  const handleToggleLevel = (level: number) => {
    setSelectedLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level]
    );
  };

  const handleToggleDepartment = (dept: string) => {
    setSelectedDepartments((prev) =>
      prev.includes(dept) ? prev.filter((d) => d !== dept) : [...prev, dept]
    );
  };

  const handleToggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const handleExcludeKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && excludeInput.trim()) {
      const course = excludeInput.trim().toUpperCase();
      if (!excludedCourses.includes(course)) {
        setExcludedCourses((prev) => [...prev, course]);
      }
      setExcludeInput("");
    }
  };

  const handleRemoveExcluded = (course: string) => {
    setExcludedCourses((prev) => prev.filter((c) => c !== course));
  };

  const handleSavePreferences = () => {
    updatePreferences({
      weight_overrides: weights,
      preference_tags: selectedTags,
      filters: buildApiFilters(),
    });
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 2500);
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Course Recommendations</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Personalized picks based on your degree progress, preferences, and peer data.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-6">
          {/* Goal selector */}
          <div className="bg-[var(--bg-secondary)] rounded-2xl p-5 border border-[var(--border-dark)] shadow-sm">
            <h3 className="text-sm font-bold text-[var(--text-primary)] mb-3">Goal</h3>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setGoal("balanced")}
                className={`py-2 rounded-lg text-xs font-semibold transition-colors ${goal === "balanced" ? "bg-[var(--umd-red)] text-white" : "bg-white/5 text-[var(--text-primary)] hover:bg-white/10"}`}
              >
                Balanced
              </button>
              <button
                type="button"
                onClick={() => setGoal("easiest")}
                className={`py-2 rounded-lg text-xs font-semibold transition-colors ${goal === "easiest" ? "bg-[var(--umd-red)] text-white" : "bg-white/5 text-[var(--text-primary)] hover:bg-white/10"}`}
              >
                Easiest Classes
              </button>
            </div>
            {goal === "easiest" && (
              <p className="text-[11px] text-[var(--text-muted)] mt-3 leading-snug">
                Pulls from the full UMD catalog and ranks by high average GPA and reviews mentioning online, async, no attendance, or no exams. If any GenEds are still unmet, results narrow to courses that fulfill them.
              </p>
            )}
            <label className="mt-4 flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showPrereqOnly}
                onChange={(e) => setShowPrereqOnly(e.target.checked)}
                className="w-4 h-4 rounded accent-[var(--umd-red)] cursor-pointer"
              />
              <span className="text-xs font-medium text-[var(--text-primary)]">
                Only courses I can take now
              </span>
            </label>
          </div>

          {/* Scoring Weights */}
          <div className="bg-[var(--bg-secondary)] rounded-2xl p-5 border border-[var(--border-dark)] shadow-sm">
            <h3 className="text-sm font-bold text-[var(--text-primary)] mb-4">Scoring Weights</h3>
            <div className="space-y-4">
              {Object.entries(FACTOR_LABELS).map(([key, label]) => {
                const raw = weights[key as keyof WeightConfig];
                const rawPct = Math.round(raw * 100);
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium text-[var(--text-primary)]">{label}</span>
                      <span className="text-xs font-bold text-[var(--text-muted)]">{rawPct}%</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={rawPct}
                      onChange={(e) => handleWeightChange(key, Number(e.target.value) / 100)}
                      className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-[var(--umd-red)]"
                    />
                  </div>
                );
              })}
            </div>
            <button
              onClick={handleApplyWeights}
              disabled={loading}
              className="mt-5 w-full py-2 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Loading..." : "Apply Weights"}
            </button>
          </div>

          {/* Professor filter */}
          <div className="bg-[var(--bg-secondary)] rounded-2xl p-5 border border-[var(--border-dark)] shadow-sm">
            <h3 className="text-sm font-bold text-[var(--text-primary)] mb-4">Professor Filter</h3>
            <div className="relative">
              <input
                type="text"
                value={profSearchQuery}
                onChange={(e) => handleProfSearchChange(e.target.value)}
                onBlur={() => setTimeout(() => setProfSearchOpen(false), 150)}
                placeholder="Search professor..."
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-dark)] text-sm bg-[var(--bg-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)]"
              />
              {profSearchOpen && profSearchResults.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-[var(--bg-secondary)] border border-[var(--border-dark)] rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {profSearchResults.map((p) => (
                    <button
                      key={p.slug}
                      onMouseDown={() => handleSelectProfessor(p)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--bg-elevated)] transition-colors"
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {selectedProfessors.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {selectedProfessors.map((p) => (
                  <span
                    key={p.slug}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--umd-red)]/10 text-[var(--umd-red)] text-xs font-medium"
                  >
                    {p.name}
                    <button
                      onClick={() => handleRemoveProfessor(p.slug)}
                      className="hover:text-[var(--umd-red)]/70 ml-0.5"
                    >
                      x
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Advanced Filters */}
          <div className="bg-[var(--bg-secondary)] rounded-2xl border border-[var(--border-dark)] shadow-sm overflow-hidden">
            <button
              onClick={() => setFiltersOpen((v) => !v)}
              className="w-full flex items-center justify-between px-5 py-4 text-sm font-bold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <span>Advanced Filters</span>
              <span className="text-[var(--text-muted)] text-xs">{filtersOpen ? "▲" : "▼"}</span>
            </button>

            {filtersOpen && (
              <div className="px-5 pb-5 space-y-5 border-t border-[var(--border-dark)]">
                {/* Min GPA */}
                <div className="pt-4">
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-medium text-[var(--text-muted)]">Min GPA</label>
                    <span className="text-xs font-bold text-[var(--text-primary)]">{minGpa.toFixed(1)}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={4}
                    step={0.1}
                    value={minGpa}
                    onChange={(e) => setMinGpa(Number(e.target.value))}
                    className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-[var(--umd-red)]"
                  />
                  <div className="flex justify-between text-[10px] text-[var(--text-muted)] mt-1">
                    <span>0.0</span>
                    <span>4.0</span>
                  </div>
                </div>

                {/* Course Level checkboxes */}
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-2">Course Level</label>
                  <div className="flex flex-wrap gap-2">
                    {COURSE_LEVELS.map((level) => (
                      <button
                        key={level}
                        onClick={() => handleToggleLevel(level)}
                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                          selectedLevels.includes(level)
                            ? "bg-[var(--umd-red)] text-white border-[var(--umd-red)]"
                            : "bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border-dark)] hover:border-[var(--umd-red)]/40"
                        }`}
                      >
                        {level}s
                      </button>
                    ))}
                  </div>
                </div>

                {/* Department pills */}
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-2">Department</label>
                  <div className="flex flex-wrap gap-1.5">
                    {UMD_DEPARTMENTS.map((dept) => (
                      <button
                        key={dept}
                        onClick={() => handleToggleDepartment(dept)}
                        className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                          selectedDepartments.includes(dept)
                            ? "bg-[var(--umd-red)] text-white border-[var(--umd-red)]"
                            : "bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border-dark)] hover:border-[var(--umd-red)]/40"
                        }`}
                      >
                        {dept}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Preference Tags */}
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-2">Preference Tags</label>
                  <div className="flex flex-wrap gap-1.5">
                    {ALL_PREFERENCE_TAGS.map((tag) => (
                      <button
                        key={tag}
                        onClick={() => handleToggleTag(tag)}
                        className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                          selectedTags.includes(tag)
                            ? "bg-[var(--umd-gold)] text-[var(--text-primary)] border-[var(--umd-gold)]"
                            : "bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border-dark)] hover:border-[var(--umd-gold)]/60"
                        }`}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Exclude Courses */}
                <div>
                  <label className="text-xs font-medium text-[var(--text-muted)] block mb-2">Exclude Courses</label>
                  <input
                    type="text"
                    value={excludeInput}
                    onChange={(e) => setExcludeInput(e.target.value)}
                    onKeyDown={handleExcludeKeyDown}
                    placeholder="Type course ID and press Enter"
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border-dark)] text-xs bg-[var(--bg-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)]"
                  />
                  {excludedCourses.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {excludedCourses.map((course) => (
                        <span
                          key={course}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--bg-elevated)] text-[var(--text-muted)] text-xs font-medium"
                        >
                          {course}
                          <button
                            onClick={() => handleRemoveExcluded(course)}
                            className="hover:text-[var(--text-primary)] ml-0.5"
                          >
                            x
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Save Preferences */}
                <button
                  onClick={handleSavePreferences}
                  disabled={savingPrefs}
                  className="w-full py-2 rounded-lg border border-[var(--umd-red)] text-[var(--umd-red)] text-xs font-semibold hover:bg-[var(--umd-red)]/5 transition-colors disabled:opacity-50"
                >
                  {savingPrefs ? "Saving..." : savedNotice ? "Saved!" : "Save Preferences"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-[var(--text-muted)]">
              Showing <span className="font-bold text-[var(--text-primary)]">{recommendations.length}</span> recommendations
            </p>
          </div>

          {error && (
            <div className="text-center py-8 text-red-600">
              <p className="text-sm">{error}</p>
              <button onClick={() => fetchRecs(weights)} className="mt-2 text-xs underline">Retry</button>
            </div>
          )}

          {loading && !error && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-[var(--bg-secondary)] rounded-2xl border border-[var(--border-dark)] p-5 animate-pulse">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-white/10" />
                    <div className="flex-1 space-y-2">
                      <div className="h-5 bg-white/10 rounded w-32" />
                      <div className="h-3 bg-white/10 rounded w-64" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && (() => {
            const major = recommendations.filter((r) => r.section === "major_requirement");
            const other = recommendations.filter((r) => r.section === "other_course");
            const renderCard = (rec: Recommendation) => (
              <RecommendationCard
                key={rec.course_id}
                rec={rec}
                expanded={expandedId === rec.course_id}
                onToggle={() => setExpandedId(expandedId === rec.course_id ? null : rec.course_id)}
                inCart={cartIds.has(rec.course_id)}
                onAddToCart={handleAddToCart}
                wishlisted={wishlistIds.has(rec.course_id)}
                onToggleWishlist={handleToggleWishlist}
              />
            );
            return (
              <>
                {major.length > 0 && (
                  <div className="space-y-4">
                    <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Major Requirements ({major.length})
                    </h2>
                    {major.map(renderCard)}
                  </div>
                )}
                {other.length > 0 && (
                  <div className="space-y-4 mt-6">
                    <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Other Courses ({other.length})
                    </h2>
                    {other.map(renderCard)}
                  </div>
                )}
              </>
            );
          })()}

          {!loading && !error && recommendations.length === 0 && (
            <div className="text-center py-16 text-[var(--text-muted)]">
              <p className="text-lg font-medium">No courses match your filters.</p>
              <p className="text-sm mt-1">Try adjusting your filters or weights.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function RecommendationsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-white/40">Loading...</div>}>
      <RecommendationsPageInner />
    </Suspense>
  );
}
