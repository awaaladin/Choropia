import { Star } from "lucide-react";
import { useState } from "react";

/** Tap a star to rate from 1 to 5. */
export function StarPicker({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  const [hover, setHover] = useState(0);
  const shown = hover || value;
  return (
    <div className="flex gap-1" onMouseLeave={() => setHover(0)} role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} star${n === 1 ? "" : "s"}`}
          onClick={() => onChange(n)}
          onMouseEnter={() => setHover(n)}
          className="p-0.5"
        >
          <Star size={30} className={n <= shown ? "fill-primary text-primary" : "text-border"} />
        </button>
      ))}
    </div>
  );
}
