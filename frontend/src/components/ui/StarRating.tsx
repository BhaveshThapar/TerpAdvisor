type StarRatingProps = {
  rating: number;
  max?: number;
  showValue?: boolean;
  size?: "sm" | "md";
};

export default function StarRating({
  rating,
  max = 5,
  showValue = false,
  size = "md",
}: StarRatingProps) {
  const clamped = Math.max(0, Math.min(max, rating));
  const sizeClass = size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4";

  return (
    <span className="inline-flex items-center gap-1">
      <span className="inline-flex">
        {Array.from({ length: max }).map((_, i) => {
          const filled = i < Math.round(clamped);
          return (
            <svg
              key={i}
              className={`${sizeClass} ${filled ? "text-[var(--umd-red)]" : "text-white/20"}`}
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.957a1 1 0 00.95.69h4.162c.969 0 1.371 1.24.588 1.81l-3.37 2.448a1 1 0 00-.364 1.118l1.287 3.957c.3.921-.755 1.688-1.54 1.118l-3.37-2.448a1 1 0 00-1.175 0l-3.37 2.448c-.784.57-1.838-.197-1.539-1.118l1.287-3.957a1 1 0 00-.364-1.118L2.05 9.384c-.783-.57-.38-1.81.588-1.81h4.162a1 1 0 00.95-.69l1.286-3.957z" />
            </svg>
          );
        })}
      </span>
      {showValue && (
        <span className="text-xs font-medium text-[var(--text-muted)]">
          {clamped.toFixed(2)}
        </span>
      )}
    </span>
  );
}
