export default function Footer() {
  return (
    <footer className="border-t border-[var(--border-dark)] mt-12 py-6 text-center text-xs text-[var(--text-muted)]">
      <div className="max-w-6xl mx-auto px-4">
        Copyright © 2026 TerpAdvisor · UMD Course Planner
        <span className="mx-2 text-white/20">|</span>
        <a href="#" className="hover:text-white transition-colors">Privacy</a>
        <span className="mx-2 text-white/20">|</span>
        <a href="#" className="hover:text-white transition-colors">Terms</a>
      </div>
    </footer>
  );
}
