import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://tilt.arcumet.com"),
  title: "TILT: Ground News for AI | Same question. Different AI. See the slant.",
  description:
    "Before you let AI shape your opinion, see how other AIs answer. TILT asks leading AIs the same question and exposes their differences side by side with verified passage evidence.",
  openGraph: {
    title: "TILT: Ground News for AI",
    description:
      "Before you let AI shape your opinion, see how other AIs answer. Compare how leading AI models frame controversial questions with verified passage evidence.",
    url: "https://tilt.arcumet.com",
    siteName: "TILT: Ground News for AI",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "TILT: Ground News for AI",
    description: "Before you let AI shape your opinion, see how other AIs answer.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#FAF6F0] text-[#141413] selection:bg-[#C83E2B]/20 selection:text-[#141413]">
        {children}
      </body>
    </html>
  );
}
