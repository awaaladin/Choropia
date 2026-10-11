import { X } from "lucide-react";
import { useEffect, useId, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn, initials } from "@/lib/utils";

export function Avatar({ src, name, size = 36, className }: { src?: string | null; name?: string | null; size?: number; className?: string }) {
  const style = { width: size, height: size, fontSize: Math.max(10, size * 0.32) };
  if (src) return <img src={src} alt="" style={style} className={cn("shrink-0 rounded-full object-cover", className)} />;
  return (
    <span style={style} className={cn("grid shrink-0 place-items-center rounded-full bg-foreground font-bold text-background", className)}>
      {initials(name)}
    </span>
  );
}

export function Badge({ tone = "muted", className, ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: "muted" | "success" | "primary" | "danger" }) {
  const tones = {
    muted: "bg-accent text-muted-foreground",
    success: "bg-success/15 text-success",
    primary: "bg-primary/10 text-primary",
    danger: "bg-destructive/10 text-destructive",
  };
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold", tones[tone], className)} {...props} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function ListingSkeleton({ view = "editorial" }: { view?: "editorial" | "grid" }) {
  return (
    <div className={cn("panel overflow-hidden", view === "editorial" ? "flex flex-col sm:flex-row" : "flex flex-col")}>
      <Skeleton className={cn("aspect-[4/3] rounded-none", view === "editorial" ? "sm:aspect-auto sm:w-52 sm:self-stretch" : "w-full")} />
      <div className="flex-1 space-y-3 p-4">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
        <div className="flex gap-2 pt-3">
          <Skeleton className="h-9 w-9" />
          <Skeleton className="ml-auto h-9 w-24" />
          <Skeleton className="h-9 w-28" />
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ icon, title, hint, action }: { icon: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="editorial-enter flex flex-col items-center gap-2 px-6 py-14 text-center">
      <span className="grid size-12 place-items-center rounded-full bg-accent text-muted-foreground">{icon}</span>
      <p className="font-display text-sm font-semibold">{title}</p>
      {hint && <p className="max-w-xs text-xs leading-relaxed text-muted-foreground">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="panel editorial-enter p-6 text-center">
      <p className="text-sm font-semibold text-destructive">Something went wrong</p>
      <p className="mt-1 text-xs text-muted-foreground">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-3 text-xs font-semibold text-primary hover:underline">
          Try again
        </button>
      )}
    </div>
  );
}

const fieldBase =
  "w-full rounded-md border border-border bg-panel px-3 py-2 text-sm text-foreground outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(fieldBase, "min-h-10", className)} {...props} />;
}
export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(fieldBase, className)} {...props} />;
}
export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(fieldBase, "min-h-10", className)} {...props} />;
}
export function Field({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 block text-xs font-semibold text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

export function Pill({ active, className, ...props }: HTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        "whitespace-nowrap rounded-full px-3 py-1.5 text-xs transition-colors",
        active ? "bg-foreground text-background" : "border border-border bg-panel text-muted-foreground hover:text-foreground",
        className,
      )}
      {...props}
    />
  );
}

/** Two-way segmented control used for Buying/Selling and the preference toggles. */
export function Segmented<T extends string>({ options, value, onChange, labels }: { options: readonly T[]; value: T; onChange: (v: T) => void; labels?: Partial<Record<T, string>> }) {
  return (
    <div className="grid gap-2 rounded-lg bg-accent p-1" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={cn(
            "rounded-md px-3 py-2 text-sm capitalize transition-all",
            value === option ? "bg-popover text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {labels?.[option] ?? option}
        </button>
      ))}
    </div>
  );
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="animate-fade-in fixed inset-0 z-50 grid place-items-center bg-foreground/25 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="animate-pop-in w-full max-w-md rounded-xl border border-border bg-popover p-5 shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id={titleId} className="text-base font-semibold">
            {title}
          </h2>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
