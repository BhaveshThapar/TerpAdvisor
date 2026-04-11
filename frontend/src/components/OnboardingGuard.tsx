"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useUserStore } from "@/lib/userStore";

export default function OnboardingGuard() {
  const router = useRouter();
  const pathname = usePathname();
  const onboarded = useUserStore((s) => s.onboarded);

  useEffect(() => {
    if (!onboarded && pathname !== "/onboarding") {
      router.replace("/onboarding");
    } else if (onboarded && pathname === "/onboarding") {
      router.replace("/dashboard");
    }
  }, [onboarded, pathname, router]);

  return null;
}
