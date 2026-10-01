import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";
import { StethoscopeIcon } from "@/components/icons";
import { I18nProvider } from "@/i18n/client";
import { getTranslations } from "@/i18n/server";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Eximion Clinical Cases", template: "%s · Eximion" },
  description: "Solve clinical cases and get an instant, explainable score.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f7fc" },
    { media: "(prefers-color-scheme: dark)", color: "#080b16" },
  ],
};

/** Applies the stored theme before first paint, so the page never flashes. */
const NO_FLASH = `(()=>{try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}})()`;

export default async function RootLayout({ children }: { children: ReactNode }) {
  const { locale, t } = await getTranslations();

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH }} />
      </head>
      <body>
        <I18nProvider locale={locale}>
          <div className="ambient" aria-hidden="true">
            <span />
          </div>
          <div className="grain" aria-hidden="true" />

          <a className="skip-link" href="#main">
            {t.nav.skip}
          </a>

          <header className="site-header">
            <div className="shell site-header__inner">
              <Link href="/" className="brand">
                <span className="brand__mark" aria-hidden="true">
                  <StethoscopeIcon width={18} height={18} />
                </span>
                <span className="brand__name">
                  {t.brand.name}
                  <span className="brand__sub">{t.brand.tagline}</span>
                </span>
              </Link>

              <div className="site-header__controls">
                <LocaleSwitcher />
                <ThemeToggle />
              </div>
            </div>
          </header>

          <main id="main" className="shell site-main">
            {children}
          </main>

          <footer className="site-footer">
            <div className="shell">{t.footer}</div>
          </footer>
        </I18nProvider>
      </body>
    </html>
  );
}
