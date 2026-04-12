import { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

export default function Card({ children, className = "", onClick }: CardProps) {
  return (
    <div
      className={`rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-dark)] transition-colors duration-200 hover:border-white/15 ${
        onClick ? "cursor-pointer" : ""
      } ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
