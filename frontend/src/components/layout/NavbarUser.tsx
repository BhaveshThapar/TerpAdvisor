"use client";

import { useEffect, useRef, useState } from "react";
import { useUserStore, resetAllData } from "@/lib/userStore";

export default function NavbarUser() {
  const name = useUserStore((s) => s.displayName);
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setConfirming(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleReset() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    resetAllData();
    window.location.href = "/onboarding";
  }

  const initials = name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-8 h-8 rounded-full bg-[var(--umd-red)] flex items-center justify-center text-xs font-bold text-white hover:ring-2 hover:ring-white/20 transition"
        aria-label="User menu"
      >
        {initials || "?"}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-56 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-dark)] shadow-xl py-2 z-50">
          <div className="px-3 py-2 border-b border-[var(--border-dark)]">
            <p className="text-sm font-medium text-[var(--text-primary)] truncate">{name || "Guest"}</p>
            <p className="text-[11px] text-[var(--text-muted)]">Local profile</p>
          </div>
          <button
            onClick={handleReset}
            className="w-full text-left px-3 py-2 text-xs text-white/70 hover:text-white hover:bg-[var(--bg-elevated)] transition-colors"
          >
            {confirming ? "Click again to confirm reset" : "Reset data"}
          </button>
        </div>
      )}
    </div>
  );
}
