"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Usage & cost" },
  { href: "/reshape", label: "Prompt reshaper" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 text-sm font-medium">
      {LINKS.map(({ href, label }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-lg px-3 py-2 transition-colors ${
              active ? "bg-accent-soft text-accent" : "text-text-2 hover:bg-accent-soft/60 hover:text-text"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
