/** TokenGuard mark: a shield holding three shrinking bars (fewer tokens). */
export function Logo({ className = "size-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <defs>
        <linearGradient id="tg-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2d5bff" />
          <stop offset="1" stopColor="#14b88a" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#tg-logo)" />
      <path
        d="M16 6.5 9 9.2v5.1c0 4.3 2.9 7.7 7 8.9 4.1-1.2 7-4.6 7-8.9V9.2l-7-2.7Z"
        fill="#ffffff26"
        stroke="#fff"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <rect x="12.2" y="11.6" width="7.6" height="1.9" rx=".95" fill="#fff" />
      <rect x="12.2" y="14.6" width="5.6" height="1.9" rx=".95" fill="#fff" opacity=".85" />
      <rect x="12.2" y="17.6" width="3.4" height="1.9" rx=".95" fill="#fff" opacity=".7" />
    </svg>
  );
}
