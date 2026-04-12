interface BadgeProps {
  text: string;
  variant?: "success" | "warning" | "danger" | "info" | "neutral";
}

const variantStyles: Record<NonNullable<BadgeProps["variant"]>, string> = {
  success: "bg-green-500/15 text-green-300",
  warning: "bg-yellow-500/15 text-yellow-300",
  danger: "bg-[var(--umd-red)]/15 text-red-300",
  info: "bg-blue-500/15 text-blue-300",
  neutral: "bg-white/10 text-white/80",
};

export default function Badge({ text, variant = "neutral" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${variantStyles[variant]}`}
    >
      {text}
    </span>
  );
}
