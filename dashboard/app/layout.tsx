import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Nav } from "@/components/Nav";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TokenGuard",
  description: "See where your AI coding agents spend tokens, and reshape prompts to use fewer of them.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans">
        <header className="border-b border-border bg-surface">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3">
            <span className="text-base font-semibold tracking-tight">TokenGuard</span>
            <Nav />
          </div>
        </header>
        <main className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
