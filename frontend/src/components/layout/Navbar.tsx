"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import CourseSearch from "@/components/CourseSearch";
import CartButton from "@/components/CartButton";
import NavbarUser from "@/components/layout/NavbarUser";

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/plan", label: "Plan" },
  { href: "/schedule", label: "Schedule" },
  { href: "/wishlist", label: "Wishlist" },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <header className="sticky top-0 z-30 bg-[var(--bg-primary)]/90 backdrop-blur-md border-b border-[var(--border-dark)]">
      <div className="max-w-6xl mx-auto px-4 md:px-6 h-14 flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2.5 shrink-0">
          <div className="relative w-9 h-9 rounded-full bg-[var(--umd-red)] flex items-center justify-center font-bold text-xs text-white tracking-tight">
            TA
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[var(--accent-green)] border-2 border-[var(--bg-primary)]" />
          </div>
          <span className="hidden sm:inline text-base font-bold tracking-tight">
            TerpAdvisor
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-5 text-sm">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative py-1 transition-colors ${
                  active
                    ? "text-white"
                    : "text-white/70 hover:text-white"
                }`}
              >
                {item.label}
                {active && (
                  <span className="absolute left-0 right-0 -bottom-[17px] h-0.5 bg-[var(--umd-red)]" />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="flex-1" />

        <div className="hidden md:block w-64">
          <CourseSearch
            variant="compact"
            placeholder="Search courses..."
            onSelect={(course) => router.push(`/course/${course.course_id}`)}
          />
        </div>
        <CartButton variant="dark" />
        <NavbarUser />
      </div>
    </header>
  );
}
