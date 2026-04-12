"use client";

import { useState } from "react";
import type { Explanation } from "@/types";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";

interface CourseCardProps {
  course_id: string;
  final_score: number;
  rank: number;
  top_reason: string;
  confidence: number;
  avg_gpa?: number | null;
  explanations: Explanation[];
}

function gpaBadgeVariant(gpa: number): "success" | "warning" | "danger" {
  if (gpa >= 3.5) return "success";
  if (gpa >= 2.5) return "warning";
  return "danger";
}

export default function CourseCard({
  course_id,
  final_score,
  rank,
  top_reason,
  confidence,
  avg_gpa,
  explanations,
}: CourseCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        {/* Rank badge */}
        <div
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
          style={{ backgroundColor: "#e21833" }}
        >
          {rank}
        </div>

        <div className="min-w-0 flex-1">
          {/* Header row */}
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-bold text-[var(--text-primary)]">{course_id}</h3>
            {avg_gpa != null && (
              <Badge
                text={`GPA: ${avg_gpa.toFixed(2)}`}
                variant={gpaBadgeVariant(avg_gpa)}
              />
            )}
            <Badge
              text={`Score: ${Math.round(final_score)}`}
              variant="info"
            />
            <Badge
              text={`${Math.round(confidence * 100)}% conf.`}
              variant="neutral"
            />
          </div>

          {/* Top reason */}
          <p className="mt-1 text-sm text-[var(--text-muted)]">{top_reason}</p>

          {/* Expand toggle */}
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 text-sm font-medium hover:underline"
            style={{ color: "#e21833" }}
          >
            {expanded ? "Hide details" : "Show details"}
          </button>

          {/* Expanded explanation breakdown */}
          {expanded && (
            <div className="mt-3 space-y-2 border-t border-[var(--border-dark)] pt-3">
              {explanations.map((exp) => (
                <div key={exp.factor} className="text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-white/80">
                      {exp.factor}
                    </span>
                    <span className="text-[var(--text-muted)]">
                      {(exp.score * 100).toFixed(0)} x{" "}
                      {(exp.weight * 100).toFixed(0)}% ={" "}
                      <span className="font-semibold text-[var(--text-primary)]">
                        {(exp.contribution * 100).toFixed(1)}
                      </span>
                    </span>
                  </div>
                  <p className="mt-0.5 text-[var(--text-muted)]">{exp.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
