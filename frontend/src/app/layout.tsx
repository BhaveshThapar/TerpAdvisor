import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "TerpAdvisor",
  description: "Intelligent Course Recommendations for UMD Students",
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
