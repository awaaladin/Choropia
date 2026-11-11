import { useId } from "react";

/** Choropia's own verified mark: a rounded eight-point star seal with a check, the same size and feel as a social-app verified
 * badge but in the Choropia blue-to-teal. Shown only next to sellers and storefronts the team has verified. */
const POINTS = (() => {
  const n = 8;
  const out: string[] = [];
  for (let i = 0; i < n * 2; i++) {
    const radius = i % 2 === 0 ? 11 : 8.6;
    const angle = (Math.PI * i) / n - Math.PI / 2;
    out.push(`${(12 + radius * Math.cos(angle)).toFixed(2)},${(12 + radius * Math.sin(angle)).toFixed(2)}`);
  }
  return out.join(" ");
})();

export function VerifiedBadge({ size = 18, className, title = "Verified by Choropia" }: { size?: number; className?: string; title?: string }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" role="img" aria-label={title} className={`inline-block shrink-0 ${className ?? ""}`}>
      <title>{title}</title>
      <defs>
        <linearGradient id={id} x1="3" y1="2" x2="21" y2="22" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#2f6bd6" />
          <stop offset="1" stopColor="#12a58a" />
        </linearGradient>
      </defs>
      <polygon points={POINTS} fill={`url(#${id})`} stroke={`url(#${id})`} strokeWidth="2.4" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="6.2" fill="none" stroke="#ffffff" strokeOpacity="0.28" strokeWidth="0.8" />
      <path d="M8 12.4l2.7 2.7L16.2 9.2" fill="none" stroke="#ffffff" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
