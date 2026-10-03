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
    <nav className="flex gap-1 text-sm">
      {LINKS.map(({ href, label }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 transition-colors ${
              active ? "bg-series-track text-text font-medium" : "text-text-2 hover:text-text"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
