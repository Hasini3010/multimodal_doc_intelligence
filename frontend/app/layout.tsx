import type { Metadata } from "next";
import { config } from "@fortawesome/fontawesome-svg-core";
import "./globals.css";

// Prevent Font Awesome from dynamically adding CSS since we imported it in globals.css
config.autoAddCss = false;

export const metadata: Metadata = {
  title: "Document Intelligence | Grounded Q&A & Evidence Verification",
  description: "Enterprise multimodal document intelligence platform with cited evidence and audited calculations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-full bg-slate-50 text-slate-800 antialiased">{children}</body>
    </html>
  );
}
