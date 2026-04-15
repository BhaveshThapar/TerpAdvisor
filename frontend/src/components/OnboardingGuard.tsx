"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useUserStore } from "@/lib/userStore";

export default function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const onboarded = useUserStore((s) => s.onboarded);

  const [hydrated, setHydrated] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (!onboarded && pathname !== "/onboarding") {
      setToastMessage("Please complete onboarding first.");
      router.replace("/onboarding");
    }
  }, [hydrated, onboarded, pathname, router]);

  useEffect(() => {
    if (!toastMessage) return;
    const t = setTimeout(() => setToastMessage(null), 3000);
    return () => clearTimeout(t);
  }, [toastMessage]);

  const blocked =
    !hydrated ||
    (!onboarded && pathname !== "/onboarding");

  return (
    <>
      {blocked ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="h-8 w-8 rounded-full border-2 border-[var(--text-secondary)] border-t-transparent animate-spin" />
        </div>
      ) : (
        children
      )}
      {toastMessage && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-24 md:bottom-8 left-1/2 -translate-x-1/2 z-50 px-4 py-3 rounded-lg bg-[var(--bg-elevated,#1f1f1f)] text-[var(--text-primary)] shadow-lg border border-[var(--border,rgba(255,255,255,0.1))] text-sm animate-[fadeIn_0.2s_ease-out]"
        >
          {toastMessage}
        </div>
      )}
    </>
  );
}
