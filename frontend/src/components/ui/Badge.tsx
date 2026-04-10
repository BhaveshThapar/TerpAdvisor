interface BadgeProps {
  text: string;
  variant?: "success" | "warning" | "danger" | "info" | "neutral";
}

const variantStyles: Record<NonNullable<BadgeProps["variant"]>, string> = {
  success: "bg-green-100 text-green-800",
  warning: "bg-yellow-100 text-yellow-800",
  danger: "bg-red-100 text-red-800",
  info: "bg-blue-100 text-blue-800",
  neutral: "bg-gray-100 text-gray-800",
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
