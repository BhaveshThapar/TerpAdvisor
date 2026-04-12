interface ProgressBarProps {
  value: number;
  label?: string;
  color?: string;
}

export default function ProgressBar({
  value,
  label,
  color = "#e21833",
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className="w-full">
      {label && (
        <div className="mb-1 flex items-center justify-between text-sm font-medium text-[var(--text-primary)]">
          <span>{label}</span>
          <span className="text-[var(--text-muted)]">{Math.round(clamped)}%</span>
        </div>
      )}
      <div className="h-3 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${clamped}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}
