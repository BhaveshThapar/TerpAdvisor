/**
 * Client-side user state management via localStorage.
 * All user-specific data (profile, completed courses, cart, wishlist, preferences)
 * is stored locally and persists across page reloads on the same device.
 */

import type { CompletedCourse, UserPreferences, WeightConfig } from "@/types";

// ── State Shape ──────────────────────────────
export interface LocalUserState {
  displayName: string;
  major: string;
  track: string;
  minor: string | null;
  ulcPrefix: string | null;
  completedCourses: CompletedCourse[];
  cart: string[];
  wishlist: string[];
  preferences: UserPreferences | null;
  onboarded: boolean;
}

const STORAGE_KEY = "terpadvisor_state";

const DEFAULT_STATE: LocalUserState = {
  displayName: "Terp Student",
  major: "Computer Science",
  track: "General",
  minor: null,
  ulcPrefix: null,
  completedCourses: [],
  cart: [],
  wishlist: [],
  preferences: null,
  onboarded: false,
};

// ── Internal helpers ──────────────────────────

function loadState(): LocalUserState {
  if (typeof window === "undefined") return { ...DEFAULT_STATE };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_STATE };
    return { ...DEFAULT_STATE, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_STATE };
  }
}

function saveState(state: LocalUserState): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  // Invalidate cached snapshot so getSnapshot returns fresh data
  cachedSnapshot = state;
  // Notify all subscribers
  listeners.forEach((fn) => fn());
}

// ── Subscription (useSyncExternalStore) ──────
type Listener = () => void;
const listeners = new Set<Listener>();

// Cache the snapshot so useSyncExternalStore gets a stable reference
let cachedSnapshot: LocalUserState = loadState();

function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): LocalUserState {
  return cachedSnapshot;
}

// ── Public API ────────────────────────────────

export function getState(): LocalUserState {
  return loadState();
}

export function setState(partial: Partial<LocalUserState>): void {
  const current = loadState();
  saveState({ ...current, ...partial });
}

// Profile
export function updateProfile(data: { displayName?: string; major?: string; track?: string; minor?: string | null; ulcPrefix?: string | null }): void {
  const s = loadState();
  if (data.displayName !== undefined) s.displayName = data.displayName;
  if (data.major !== undefined) s.major = data.major;
  if (data.track !== undefined) s.track = data.track;
  if (data.minor !== undefined) s.minor = data.minor;
  if (data.ulcPrefix !== undefined) s.ulcPrefix = data.ulcPrefix;
  saveState(s);
}

// Completed Courses
export function addCompletedCourse(course: CompletedCourse): void {
  const s = loadState();
  if (s.completedCourses.some((c) => c.course_id === course.course_id)) return;
  s.completedCourses = [...s.completedCourses, course];
  saveState(s);
}

export function bulkAddCompletedCourses(courses: CompletedCourse[]): void {
  const s = loadState();
  const existing = new Set(s.completedCourses.map((c) => c.course_id));
  const newCourses: CompletedCourse[] = [];
  for (const c of courses) {
    if (!existing.has(c.course_id)) {
      newCourses.push(c);
      existing.add(c.course_id);
    }
  }
  s.completedCourses = [...s.completedCourses, ...newCourses];
  saveState(s);
}

export function removeCompletedCourse(courseId: string): void {
  const s = loadState();
  s.completedCourses = s.completedCourses.filter((c) => c.course_id !== courseId);
  saveState(s);
}

// Grades that don't count toward prerequisite satisfaction or degree credit.
// XF (Academic Dishonesty) and F appear in the transcript for display, but must
// not be treated as "completed" when checking prerequisites or auditing progress.
const NON_CREDIT_GRADES = new Set(["XF", "F"]);

export function getCompletedCourseIds(): string[] {
  return loadState()
    .completedCourses
    .filter((c) => !NON_CREDIT_GRADES.has(c.grade ?? ""))
    .map((c) => c.course_id);
}

// Cart
export function addToCart(courseId: string): void {
  const s = loadState();
  if (s.cart.includes(courseId)) return;
  s.cart = [...s.cart, courseId];
  saveState(s);
}

export function removeFromCart(courseId: string): void {
  const s = loadState();
  s.cart = s.cart.filter((id) => id !== courseId);
  saveState(s);
}

export function clearCart(): void {
  const s = loadState();
  s.cart = [];
  saveState(s);
}

export function isInCart(courseId: string): boolean {
  return loadState().cart.includes(courseId);
}

// Wishlist
export function addToWishlist(courseId: string): void {
  const s = loadState();
  if (s.wishlist.includes(courseId)) return;
  s.wishlist = [...s.wishlist, courseId];
  saveState(s);
}

export function removeFromWishlist(courseId: string): void {
  const s = loadState();
  s.wishlist = s.wishlist.filter((id) => id !== courseId);
  saveState(s);
}

export function clearWishlist(): void {
  const s = loadState();
  s.wishlist = [];
  saveState(s);
}

export function isInWishlist(courseId: string): boolean {
  return loadState().wishlist.includes(courseId);
}

export function moveWishlistToCart(courseId: string): void {
  const s = loadState();
  s.wishlist = s.wishlist.filter((id) => id !== courseId);
  if (!s.cart.includes(courseId)) {
    s.cart = [...s.cart, courseId];
  }
  saveState(s);
}

// Preferences
export function updatePreferences(partial: Partial<UserPreferences>): void {
  const s = loadState();
  s.preferences = { ...(s.preferences || { weight_overrides: null, preference_tags: null, filters: null, schedule_preferences: null }), ...partial };
  saveState(s);
}

// Reset
export function resetAllData(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
  // Also clear legacy keys
  localStorage.removeItem("terp_token");
  localStorage.removeItem("terp_user");
  cachedSnapshot = { ...DEFAULT_STATE };
  listeners.forEach((fn) => fn());
}

// ── React Hook ────────────────────────────────

import { useSyncExternalStore } from "react";

export function useUserStore(): LocalUserState;
export function useUserStore<T>(selector: (state: LocalUserState) => T): T;
export function useUserStore<T>(selector?: (state: LocalUserState) => T): T | LocalUserState {
  const state = useSyncExternalStore(subscribe, getSnapshot, () => DEFAULT_STATE);
  return selector ? selector(state) : state;
}
