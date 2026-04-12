"use client";

import type { WeightConfig } from "@/types";
import Slider from "@/components/ui/Slider";

interface WeightSlidersProps {
  weights: WeightConfig;
  onChange: (weights: WeightConfig) => void;
}

const FACTOR_LABELS: Record<keyof WeightConfig, string> = {
  requirement: "Requirement Fulfillment",
  gpa: "GPA / Grade",
  professor: "Professor Rating",
  sentiment: "Review Sentiment",
  collaborative: "Collaborative Filtering",
  schedule_fit: "Schedule Fit",
};

const FACTOR_KEYS: (keyof WeightConfig)[] = [
  "requirement",
  "gpa",
  "professor",
  "sentiment",
  "collaborative",
  "schedule_fit",
];

export default function WeightSliders({
  weights,
  onChange,
}: WeightSlidersProps) {
  const rawSum = FACTOR_KEYS.reduce((s, k) => s + weights[k], 0);
  const normFactor = rawSum > 0 ? 1 / rawSum : 1;

  const handleChange = (key: keyof WeightConfig, val: number) => {
    onChange({ ...weights, [key]: val });
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">
        Recommendation Weights
      </h3>
      {FACTOR_KEYS.map((key) => {
        const normalizedPct = Math.round(weights[key] * normFactor * 100);
        return (
          <Slider
            key={key}
            label={key}
            value={weights[key]}
            onChange={(v) => handleChange(key, v)}
            displayName={`${FACTOR_LABELS[key]} (${normalizedPct}%)`}
          />
        );
      })}
    </div>
  );
}
