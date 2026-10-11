import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import { Link } from "./AppLink";

type Variant = "primary" | "secondary" | "ghost" | "icon" | "danger";

const variants: Record<Variant, string> = {
  primary: "bg-primary text-primary-foreground hover:bg-primary-hover shadow-button",
  secondary: "border border-border bg-panel text-foreground hover:bg-accent",
  ghost: "text-muted-foreground hover:bg-accent hover:text-foreground",
  icon: "bg-panel text-muted-foreground hover:bg-accent hover:text-foreground border border-border",
  danger: "border border-destructive/40 text-destructive hover:bg-destructive/10",
};

export function buttonClass(variant: Variant = "primary", className?: string) {
  return cn(
    "inline-flex min-h-9 items-center justify-center gap-2 rounded-md px-3 text-sm font-semibold transition-[transform,background-color,color,box-shadow] duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 active:translate-y-px",
    variants[variant],
    className,
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean };

export function Button({ className, variant = "primary", loading, disabled, children, ...props }: ButtonProps) {
  return (
    <button className={buttonClass(variant, className)} disabled={disabled || loading} {...props}>
      {loading && <Loader2 size={14} className="animate-spin" />}
      {children}
    </button>
  );
}

export function LinkButton({
  to,
  variant = "primary",
  className,
  children,
}: {
  to: string;
  variant?: Variant;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link to={to} className={buttonClass(variant, className)}>
      {children}
    </Link>
  );
}
