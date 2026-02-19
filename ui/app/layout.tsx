import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Lead Enrichment Demo",
  description: "Realtime lead enrichment with SingleStore",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="mx-auto max-w-6xl px-6 py-8">{children}</div>
      </body>
    </html>
  );
}
