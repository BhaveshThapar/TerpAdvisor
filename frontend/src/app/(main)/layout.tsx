import OnboardingGuard from "@/components/OnboardingGuard";
import MobileBottomNav from "@/components/layout/MobileBottomNav";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <OnboardingGuard />
      <Navbar />
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 md:px-6 py-8 pb-24 md:pb-12">
        {children}
      </main>
      <Footer />
      <MobileBottomNav />
    </div>
  );
}
