"use client";

interface SliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  displayName?: string;
}

export default function Slider({
  label,
  value,
  onChange,
  displayName,
}: SliderProps) {
  const pct = Math.round(value * 100);

  return (
    <div className="w-full">
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700">
          {displayName ?? label}
        </span>
        <span className="font-semibold" style={{ color: "#e21833" }}>
          {pct}%
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={pct}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-gray-200
          [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:rounded-full
          [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-[#e21833]
          [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none
          [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#e21833]"
        aria-label={label}
      />
    </div>
  );
}
