"use client";
import { useUserStore, resetAllData } from "@/lib/userStore";
import { useState } from "react";

export default function SidebarUser() {
  const name = useUserStore((s) => s.displayName);
  const [confirming, setConfirming] = useState(false);

  function handleReset() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    resetAllData();
    setConfirming(false);
    window.location.href = "/onboarding";
  }

  const initials = name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="px-4 py-4 border-t border-white/10">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-[#e21833] flex items-center justify-center text-xs font-bold text-white">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate text-white">{name}</p>
          <button
            onClick={handleReset}
            className="text-xs text-white/40 hover:text-white/70 transition-colors"
          >
            {confirming ? "Confirm reset?" : "Reset Data"}
          </button>
        </div>
      </div>
    </div>
  );
}
