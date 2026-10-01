import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { StethoscopeIcon } from "@/components/icons";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Eximion Clinical Cases", template: "%s · Eximion" },
  description: "Solve clinical cases and get an instant, explainable score.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0f16" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="ambient" aria-hidden="true">
          <span />
        </div>

        <a className="skip-link" href="#main">
          Skip to content
        </a>

        <header className="site-header">
          <div className="shell site-header__inner">
            <Link href="/" className="brand">
              <span className="brand__mark" aria-hidden="true">
                <StethoscopeIcon width={18} height={18} />
              </span>
              <span className="brand__name">
                Eximion
                <span className="brand__sub">Clinical Olympics</span>
              </span>
            </Link>
          </div>
        </header>

        <main id="main" className="shell site-main">
          {children}
        </main>

        <footer className="site-footer">
          <div className="shell">Synthetic cases for demonstration. Not for clinical use.</div>
        </footer>
      </body>
    </html>
  );
}
