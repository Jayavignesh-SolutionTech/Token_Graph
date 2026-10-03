import type { Metadata } from "next";
import Link from "next/link";
import { Geist_Mono, Inter } from "next/font/google";
import { GithubIcon } from "@/components/icons";
import { Logo } from "@/components/Logo";
import { Nav } from "@/components/Nav";
import { REPO_URL } from "@/lib/site";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const mono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TokenGuard",
  description: "See where your AI coding agents spend tokens, and reshape prompts to use fewer of them.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="glass-header sticky top-0 z-50">
          <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5 text-lg font-extrabold tracking-tight">
              <Logo className="size-8 -rotate-3 drop-shadow-[0_6px_14px_#2d5bff47]" />
              TokenGuard
            </Link>
            <Nav />
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary ml-auto hidden !py-2 text-sm sm:inline-flex"
            >
              <GithubIcon className="size-4" />
              Get the CLI
            </a>
          </div>
        </header>

        <main className="mx-auto w-full min-w-0 max-w-7xl flex-1 px-4 pb-20 pt-10 sm:px-6">{children}</main>

        <footer className="site-footer">
          <div className="relative mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:grid-cols-[1.4fr_1fr_1fr] sm:px-6">
            <div>
              <div className="flex items-center gap-2.5 text-lg font-extrabold text-white">
                <Logo className="size-8" />
                TokenGuard
              </div>
              <p className="mt-4 max-w-sm text-sm leading-relaxed text-[#aebbd0]">
                Cost reporting and token optimization for teams building with AI coding agents.
              </p>
            </div>
            <FooterColumn
              title="Product"
              links={[
                { href: "/", label: "Usage & cost" },
                { href: "/reshape", label: "Prompt reshaper" },
                { href: "/?sample=1", label: "Live demo" },
              ]}
            />
            <FooterColumn
              title="Resources"
              links={[
                { href: REPO_URL, label: "GitHub" },
                { href: `${REPO_URL}/tree/main/cli`, label: "CLI documentation" },
              ]}
            />
          </div>
          <div className="relative border-t border-white/10">
            <p className="mx-auto max-w-7xl px-4 py-5 text-xs text-[#8fa3c8] sm:px-6">
              Costs shown are API-equivalent at list prices. Your export file never leaves your browser.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}

function FooterColumn({ title, links }: { title: string; links: { href: string; label: string }[] }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <ul className="mt-4 space-y-2.5 text-sm">
        {links.map((l) => (
          <li key={l.label}>
            <a href={l.href} className="text-[#aebbd0] transition-colors hover:text-white">
              {l.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
