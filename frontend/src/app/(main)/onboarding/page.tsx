"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import CourseSearch from "@/components/CourseSearch";
import { courseApi } from "@/lib/api";
import { updateProfile, bulkAddCompletedCourses, setState } from "@/lib/userStore";
import type { CourseDetail, TranscriptParseResult } from "@/types";

type InputMode = "search" | "paste" | "upload";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [major, setMajor] = useState("");
  const [majorConfirmed, setMajorConfirmed] = useState(false); // Helper for validation
  const [majorDetected, setMajorDetected] = useState(false);
  const [track, setTrack] = useState("General");
  const [minor, setMinor] = useState("");
  const [courses, setCourses] = useState<Array<{ course_id: string; name: string }>>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1 input mode
  const [inputMode, setInputMode] = useState<InputMode>("search");

  // Paste transcript state
  const [pasteText, setPasteText] = useState("");
  const [parseResult, setParseResult] = useState<TranscriptParseResult | null>(null);
  const [parsedChecked, setParsedChecked] = useState<Set<string>>(new Set());
  const [parsing, setParsing] = useState(false);
  const [pasteError, setPasteError] = useState<string | null>(null);

  // Upload PDF state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAddCourse = (course: CourseDetail) => {
    if (courses.some((c) => c.course_id === course.course_id)) return;
    setCourses((prev) => [...prev, { course_id: course.course_id, name: course.name }]);
  };

  const handleRemoveCourse = (courseId: string) => {
    setCourses((prev) => prev.filter((c) => c.course_id !== courseId));
  };

  function applyParseResult(result: TranscriptParseResult) {
    setParseResult(result);
    setParsedChecked(new Set(result.courses.map((c) => c.course_id)));
    if (result.major) {
      setMajor(result.major);
      setMajorDetected(true);
    }
  }

  async function handleParse() {
    setPasteError(null);
    if (!pasteText.trim()) {
      setPasteError("Please paste some text before parsing.");
      return;
    }
    setParsing(true);
    try {
      const result = await courseApi.parseTranscript(pasteText);
      applyParseResult(result);
    } catch (e) {
      setPasteError(e instanceof Error ? e.message : "Failed to parse transcript.");
    } finally {
      setParsing(false);
    }
  }

  async function handleUploadPdf() {
    if (!uploadFile) {
      setUploadError("Please select a PDF file first.");
      return;
    }
    setUploadError(null);
    setUploading(true);
    try {
      const result = await courseApi.parseTranscriptPdf(uploadFile);
      applyParseResult(result);
      setInputMode("upload");
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Failed to parse PDF.");
    } finally {
      setUploading(false);
    }
  }

  function handleFileSelect(file: File | null) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Please select a PDF file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError("File is too large. Maximum size is 10 MB.");
      return;
    }
    setUploadFile(file);
    setUploadError(null);
    setParseResult(null);
  }

  function handleAddParsed() {
    if (!parseResult) return;
    const selectedCourses = parseResult.courses.filter((c) => parsedChecked.has(c.course_id));
    if (selectedCourses.length === 0) return;
    bulkAddCompletedCourses(
      selectedCourses.map((c) => ({
        course_id: c.course_id,
        semester: null,
        grade: c.grade || null,
        credits: c.credits,
        gen_eds: c.gen_eds,
        in_progress: c.in_progress,
      }))
    );
    const existing = new Set(courses.map((c) => c.course_id));
    const newCourses = selectedCourses
      .filter((c) => !existing.has(c.course_id))
      .map((c) => ({ course_id: c.course_id, name: c.name || c.course_id }));
    setCourses((prev) => [...prev, ...newCourses]);
    setParseResult(null);
    setPasteText("");
    setParsedChecked(new Set());
  }

  const MINOR_PREFIX_MAP: Record<string, string> = {
    "Mathematics": "MATH",
    "Statistics": "STAT",
    "Economics": "ECON",
    "Physics": "PHYS",
    "Chemistry": "CHEM",
    "Biology": "BIOL",
    "Psychology": "PSYC",
    "Linguistics": "LING",
    "Philosophy": "PHIL",
    "Business": "BMGT",
    "Entrepreneurship": "ENTR",
  };

  const handleFinish = () => {
    setSaving(true);
    setError(null);
    try {
      const plcPrefix = minor ? MINOR_PREFIX_MAP[minor] || null : null;
      updateProfile({ major, minor: minor || null, track, ulcPrefix: plcPrefix });
      if (courses.length > 0) {
        bulkAddCompletedCourses(courses.map((c) => ({ course_id: c.course_id, semester: null, grade: null })));
      }
      setState({ onboarded: true });
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[var(--umd-black)]">Welcome to TerpAdvisor</h1>
        <p className="text-sm text-[var(--umd-gray)] mt-1">
          Let&apos;s set up your profile so we can give you personalized recommendations.
        </p>
      </div>

      {/* Progress indicator */}
      <div className="flex items-center gap-3 mb-8">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
              s <= step ? "bg-[var(--umd-red)] text-white" : "bg-gray-200 text-[var(--umd-gray)]"
            }`}>
              {s < step ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : s}
            </div>
            <span className={`text-xs font-medium ${s <= step ? "text-[var(--umd-black)]" : "text-[var(--umd-gray)]"}`}>
              {s === 1 ? "Courses" : s === 2 ? "Major" : "Confirm"}
            </span>
            {s < 3 && <div className="w-12 h-0.5 bg-gray-200 rounded" />}
          </div>
        ))}
      </div>

      {/* Step 1: Add Completed Courses */}
      {step === 1 && (
        <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
          <h2 className="text-lg font-bold text-[var(--umd-black)] mb-1">Add Completed Courses</h2>
          <p className="text-sm text-[var(--umd-gray)] mb-4">
            Upload your Testudo transcript to automatically import your courses and detect your major.
          </p>

          {/* Mode toggle */}
          <div className="flex gap-1 p-1 bg-[var(--umd-light)] rounded-lg mb-4 w-fit">
            <button
              onClick={() => setInputMode("search")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                inputMode === "search"
                  ? "bg-white text-[var(--umd-black)] shadow-sm"
                  : "text-[var(--umd-gray)] hover:text-[var(--umd-black)]"
              }`}
            >
              Search Courses
            </button>
            <button
              onClick={() => setInputMode("paste")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                inputMode === "paste"
                  ? "bg-white text-[var(--umd-black)] shadow-sm"
                  : "text-[var(--umd-gray)] hover:text-[var(--umd-black)]"
              }`}
            >
              Paste Transcript
            </button>
            <button
              onClick={() => setInputMode("upload")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                inputMode === "upload"
                  ? "bg-white text-[var(--umd-black)] shadow-sm"
                  : "text-[var(--umd-gray)] hover:text-[var(--umd-black)]"
              }`}
            >
              Upload PDF
            </button>
          </div>

          {/* Search mode */}
          {inputMode === "search" && (
            <CourseSearch onSelect={handleAddCourse} />
          )}

          {/* Upload PDF mode */}
          {inputMode === "upload" && !parseResult && (
            <div className="space-y-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
              />

              {/* Drop zone */}
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const file = e.dataTransfer.files?.[0];
                  handleFileSelect(file || null);
                }}
                className={`flex flex-col items-center justify-center gap-3 py-10 px-6 rounded-xl border-2 border-dashed cursor-pointer transition-all ${
                  dragOver
                    ? "border-[var(--umd-red)] bg-[var(--umd-red)]/5"
                    : uploadFile
                    ? "border-emerald-300 bg-emerald-50"
                    : "border-black/15 bg-[var(--umd-light)] hover:border-[var(--umd-red)]/40 hover:bg-[var(--umd-red)]/5"
                }`}
              >
                {uploadFile ? (
                  <>
                    <svg className="w-10 h-10 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div className="text-center">
                      <p className="text-sm font-semibold text-[var(--umd-black)]">{uploadFile.name}</p>
                      <p className="text-xs text-[var(--umd-gray)] mt-0.5">
                        {(uploadFile.size / 1024).toFixed(0)} KB — Click to change
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <svg className="w-10 h-10 text-[var(--umd-gray)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9.75m0 0l2.25 2.25M9.75 14.25l2.25-2.25M6.375 20.25h8.25a2.25 2.25 0 002.25-2.25V6.108c0-.597-.237-1.17-.659-1.591l-2.608-2.609a2.25 2.25 0 00-1.591-.659H6.375a2.25 2.25 0 00-2.25 2.25v16.5a2.25 2.25 0 002.25 2.25z" />
                    </svg>
                    <div className="text-center">
                      <p className="text-sm font-semibold text-[var(--umd-black)]">
                        Drop your Testudo transcript here
                      </p>
                      <p className="text-xs text-[var(--umd-gray)] mt-0.5">
                        or click to browse — PDF files only, max 10 MB
                      </p>
                    </div>
                  </>
                )}
              </div>

              {uploadError && (
                <p className="text-sm text-red-600">{uploadError}</p>
              )}

              <button
                onClick={handleUploadPdf}
                disabled={!uploadFile || uploading}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors disabled:opacity-50"
              >
                {uploading ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Parsing PDF...
                  </>
                ) : "Parse Transcript"}
              </button>
            </div>
          )}

          {/* Paste mode */}
          {inputMode === "paste" && (
            <div className="space-y-3">
              <textarea
                value={pasteText}
                onChange={(e) => {
                  setPasteText(e.target.value);
                  if (parseResult) setParseResult(null);
                  setPasteError(null);
                }}
                rows={6}
                placeholder="Paste your transcript, course list, or any text containing course IDs (e.g., CMSC131, MATH140). We'll extract your courses and major automatically."
                className="w-full px-4 py-3 rounded-lg border border-black/10 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)] resize-none font-mono placeholder:font-sans placeholder:text-[var(--umd-gray)]"
              />

              {pasteError && (
                <p className="text-sm text-red-600">{pasteError}</p>
              )}

              <button
                onClick={handleParse}
                disabled={parsing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors disabled:opacity-50"
              >
                {parsing ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Parsing...
                  </>
                ) : "Parse Transcript"}
              </button>
            </div>
          )}

          {/* Parse results — shown for both paste and upload modes */}
          {(inputMode === "paste" || inputMode === "upload") && parseResult && (
            <div className="mt-4 rounded-xl border border-black/10 overflow-hidden">
              {/* Header */}
              <div className="p-4 border-b border-black/5 bg-green-50/50">
                <p className="text-sm font-semibold text-green-800 flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  Found {parseResult.courses.length} course{parseResult.courses.length !== 1 ? "s" : ""}
                  <span className="text-xs font-normal text-green-700">
                    · {parseResult.total_credits} total credits
                  </span>
                </p>
                {parseResult.major && (
                  <p className="text-xs text-green-700 mt-1">Major detected: <span className="font-semibold">{parseResult.major}</span></p>
                )}
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => setParsedChecked(new Set(parseResult.courses.map(c => c.course_id)))}
                    className="text-xs text-green-700 hover:text-green-900 font-medium"
                  >
                    Select All
                  </button>
                  <span className="text-xs text-green-400">·</span>
                  <button
                    onClick={() => setParsedChecked(new Set())}
                    className="text-xs text-green-700 hover:text-green-900 font-medium"
                  >
                    Deselect All
                  </button>
                </div>
              </div>

              {/* Course rows */}
              <div className="divide-y divide-black/5 max-h-[400px] overflow-y-auto">
                {parseResult.courses.map((c) => (
                  <label key={c.course_id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50/80 cursor-pointer transition-colors">
                    <input
                      type="checkbox"
                      checked={parsedChecked.has(c.course_id)}
                      onChange={(e) => {
                        setParsedChecked((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) next.add(c.course_id);
                          else next.delete(c.course_id);
                          return next;
                        });
                      }}
                      className="accent-[var(--umd-red)] w-4 h-4 flex-shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold font-mono text-[var(--umd-black)]">{c.course_id}</span>
                        {c.grade && (
                          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                            c.in_progress ? "bg-amber-100 text-amber-700"
                            : c.grade.startsWith("A") ? "bg-green-100 text-green-700"
                            : c.grade.startsWith("B") ? "bg-blue-100 text-blue-700"
                            : c.grade === "TR" ? "bg-purple-100 text-purple-700"
                            : "bg-gray-100 text-gray-600"
                          }`}>{c.in_progress ? "In Progress" : c.grade}{c.grade === "TR" ? " (Transfer)" : ""}</span>
                        )}
                        {!c.in_catalog && (
                          <span className="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded font-medium">Not in catalog</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        {c.name && (
                          <span className="text-xs text-[var(--umd-gray)] truncate">{c.name}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {c.gen_eds.length > 0 && (
                        <div className="flex gap-1">
                          {c.gen_eds.map((ge) => (
                            <span key={ge} className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
                              {ge}
                            </span>
                          ))}
                        </div>
                      )}
                      {c.credits != null && (
                        <span className="text-xs text-[var(--umd-gray)] font-medium w-8 text-right">{c.credits}cr</span>
                      )}
                    </div>
                  </label>
                ))}
              </div>

              {/* Empty state */}
              {parseResult.courses.length === 0 && (
                <div className="p-4 text-sm text-[var(--umd-gray)]">
                  No course IDs found. Try a different transcript or include course codes like CMSC131 or MATH140.
                </div>
              )}

              {/* Add selected button */}
              {parseResult.courses.length > 0 && (
                <div className="p-4 border-t border-black/5">
                  <button
                    onClick={handleAddParsed}
                    disabled={parsedChecked.size === 0}
                    className="w-full py-2.5 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors disabled:opacity-40"
                  >
                    Add {parsedChecked.size} Course{parsedChecked.size !== 1 ? "s" : ""}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Added courses list */}
          {courses.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-medium text-[var(--umd-gray)]">{courses.length} course{courses.length !== 1 ? "s" : ""} added</p>
              <div className="flex flex-wrap gap-2">
                {courses.map((c) => (
                  <span
                    key={c.course_id}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--umd-light)] text-sm font-medium text-[var(--umd-black)]"
                  >
                    {c.course_id}
                    <button
                      onClick={() => handleRemoveCourse(c.course_id)}
                      className="text-[var(--umd-gray)] hover:text-[var(--umd-red)] transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="mt-6">
            <button
              onClick={() => {
                if (parseResult && parsedChecked.size > 0) handleAddParsed();
                setStep(2);
              }}
              className="w-full py-2.5 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Major & Minor */}
      {step === 2 && (
        <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
          <h2 className="text-lg font-bold text-[var(--umd-black)] mb-1">Your Major</h2>
          <p className="text-sm text-[var(--umd-gray)] mb-5">
            {majorDetected
              ? "We detected your major from your transcript. Confirm or edit it below."
              : "Enter your major below. You can update this later from your profile."}
          </p>

          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-[var(--umd-gray)] block mb-1.5">
                Major
                {majorDetected && (
                  <span className="ml-2 text-green-600 font-normal">· detected from transcript</span>
                )}
              </label>
              <input
                type="text"
                autoComplete="off"
                value={major}
                onChange={(e) => { setMajor(e.target.value); setMajorDetected(false); }}
                placeholder="e.g., Computer Science"
                className="w-full px-4 py-2.5 rounded-lg border border-black/10 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)]"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-[var(--umd-gray)] block mb-1.5">Track / Specialization</label>
              <select
                value={track}
                onChange={(e) => setTrack(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg border border-black/10 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)] bg-white"
              >
                <option value="General">General</option>
                <option value="Cybersecurity">Cybersecurity</option>
                <option value="Data Science">Data Science</option>
                <option value="Machine Learning">Machine Learning</option>
                <option value="Quantum Information">Quantum Information</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-[var(--umd-gray)] block mb-1.5">Minor (optional)</label>
              <input
                type="text"
                autoComplete="off"
                value={minor}
                onChange={(e) => setMinor(e.target.value)}
                placeholder="e.g., Statistics"
                className="w-full px-4 py-2.5 rounded-lg border border-black/10 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--umd-red)]/20 focus:border-[var(--umd-red)]"
              />
            </div>
          </div>

          <div className="mt-6 flex gap-3">
            <button
              onClick={() => setStep(1)}
              className="flex-1 py-2.5 rounded-lg border border-black/10 text-sm font-semibold text-[var(--umd-gray)] hover:bg-[var(--umd-light)] transition-colors"
            >
              Back
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={!major.trim()}
              className="flex-1 py-2.5 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors disabled:opacity-40"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Confirm */}
      {step === 3 && (
        <div className="bg-white rounded-2xl p-6 border border-black/5 shadow-sm">
          <h2 className="text-lg font-bold text-[var(--umd-black)] mb-4">Confirm Your Profile</h2>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-black/5">
              <span className="text-sm text-[var(--umd-gray)]">Major</span>
              <span className="text-sm font-semibold text-[var(--umd-black)]">{major}</span>
            </div>
            {minor && (
              <div className="flex items-center justify-between py-3 border-b border-black/5">
                <span className="text-sm text-[var(--umd-gray)]">Minor</span>
                <span className="text-sm font-semibold text-[var(--umd-black)]">{minor}</span>
              </div>
            )}
            <div className="py-3">
              <span className="text-sm text-[var(--umd-gray)]">Completed Courses ({courses.length})</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {courses.length > 0 ? courses.map((c) => (
                  <span key={c.course_id} className="text-xs font-medium bg-[var(--umd-light)] px-2.5 py-1 rounded-lg">
                    {c.course_id}
                  </span>
                )) : (
                  <span className="text-xs text-[var(--umd-gray)]">None added (you can add them later)</span>
                )}
              </div>
            </div>
          </div>

          {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

          <div className="mt-6 flex gap-3">
            <button
              onClick={() => setStep(2)}
              className="flex-1 py-2.5 rounded-lg border border-black/10 text-sm font-semibold text-[var(--umd-gray)] hover:bg-[var(--umd-light)] transition-colors"
            >
              Back
            </button>
            <button
              onClick={handleFinish}
              disabled={saving}
              className="flex-1 py-2.5 rounded-lg bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Start Exploring"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
