"use client";

import type { ScheduleSection } from "@/types";

interface CalendarViewProps {
  sections: ScheduleSection[];
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"] as const;
const DAY_MAP: Record<string, number> = {
  Mon: 0, M: 0,
  Tue: 1, Tu: 1,
  Wed: 2, W: 2,
  Thu: 3, Th: 3,
  Fri: 4, F: 4,
};
const START_HOUR = 8;
const END_HOUR = 18;
const TOTAL_MINUTES = (END_HOUR - START_HOUR) * 60;
const SLOT_HOURS = Array.from(
  { length: END_HOUR - START_HOUR },
  (_, i) => START_HOUR + i
);

const COLORS = [
  "#e21833",
  "#2563eb",
  "#059669",
  "#d97706",
  "#7c3aed",
  "#db2777",
  "#0891b2",
  "#ca8a04",
];

function parseTime(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

function formatHour(h: number): string {
  const suffix = h >= 12 ? "PM" : "AM";
  const display = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `${display}${suffix}`;
}

export default function CalendarView({ sections }: CalendarViewProps) {
  // Assign a stable color per unique course_id
  const courseIds = [...new Set(sections.map((s) => s.course_id))];
  const colorMap = new Map(courseIds.map((id, i) => [id, COLORS[i % COLORS.length]]));

  // Build positioned blocks
  const blocks: {
    day: number;
    topPct: number;
    heightPct: number;
    color: string;
    course_id: string;
    professor: string;
  }[] = [];

  for (const section of sections) {
    for (const mtg of section.meetings) {
      const dayIdx = DAY_MAP[mtg.day];
      if (dayIdx === undefined) continue;
      const start = parseTime(mtg.start_time);
      const end = parseTime(mtg.end_time);
      const topPct = ((start - START_HOUR * 60) / TOTAL_MINUTES) * 100;
      const heightPct = ((end - start) / TOTAL_MINUTES) * 100;
      blocks.push({
        day: dayIdx,
        topPct,
        heightPct,
        color: colorMap.get(section.course_id) ?? COLORS[0],
        course_id: section.course_id,
        professor: section.professor,
      });
    }
  }

  return (
    <div className="overflow-x-auto rounded-xl bg-[var(--bg-secondary)] shadow-md">
      <div className="min-w-[700px]">
        {/* Day headers */}
        <div className="grid grid-cols-[60px_repeat(5,1fr)] border-b border-[var(--border-dark)]">
          <div className="p-2" />
          {DAYS.map((d) => (
            <div
              key={d}
              className="border-l border-[var(--border-dark)] p-2 text-center text-sm font-semibold text-white/80"
            >
              {d}
            </div>
          ))}
        </div>

        {/* Body */}
        <div className="grid grid-cols-[60px_repeat(5,1fr)]">
          {/* Time labels */}
          <div className="relative">
            {SLOT_HOURS.map((h) => (
              <div
                key={h}
                className="flex items-start justify-end pr-2 text-[11px] text-white/40"
                style={{ height: `${100 / (END_HOUR - START_HOUR)}%` }}
              >
                {formatHour(h)}
              </div>
            ))}
          </div>

          {/* Day columns */}
          {DAYS.map((_, di) => (
            <div
              key={di}
              className="relative border-l border-[var(--border-dark)]"
              style={{
                height: `${(END_HOUR - START_HOUR) * 3.5}rem`,
              }}
            >
              {/* Hour grid lines */}
              {SLOT_HOURS.map((h) => (
                <div
                  key={h}
                  className="absolute left-0 right-0 border-t border-[var(--border-dark)]"
                  style={{
                    top: `${((h - START_HOUR) / (END_HOUR - START_HOUR)) * 100}%`,
                  }}
                />
              ))}

              {/* Class blocks */}
              {blocks
                .filter((b) => b.day === di)
                .map((b, idx) => (
                  <div
                    key={idx}
                    className="absolute left-0.5 right-0.5 overflow-hidden rounded-md px-1.5 py-0.5 text-xs text-white"
                    style={{
                      top: `${b.topPct}%`,
                      height: `${b.heightPct}%`,
                      backgroundColor: b.color,
                    }}
                  >
                    <div className="font-bold leading-tight">
                      {b.course_id}
                    </div>
                    <div className="truncate leading-tight opacity-90">
                      {b.professor}
                    </div>
                  </div>
                ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
