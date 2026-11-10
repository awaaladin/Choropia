import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Copy, EllipsisVertical, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

/**
 * WhatsApp-style message options: a small ⋮ button beside a message (shown on hover with a mouse, always on touch
 * screens) that opens a menu. Copy for any message with text; Delete for everyone on your own messages, confirmed inside
 * the menu.
 */
export function MessageMenu({
  mine,
  text,
  canDelete,
  deleting,
  onDelete,
}: {
  mine: boolean;
  text: string;
  canDelete: boolean;
  deleting: boolean;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const close = (focusButton = false) => {
    setOpen(false);
    setConfirming(false);
    if (focusButton) buttonRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close();
    };
    document.addEventListener("pointerdown", onPointer);
    requestAnimationFrame(() => menuRef.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus());
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  const items = [text.trim() ? "copy" : null, canDelete ? "delete" : null].filter(Boolean) as ("copy" | "delete")[];
  if (!items.length) return null;

  const onMenuKey = (event: React.KeyboardEvent) => {
    const nodes = Array.from(menuRef.current?.querySelectorAll<HTMLElement>("[role=menuitem]") ?? []);
    const index = nodes.indexOf(document.activeElement as HTMLElement);
    if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      nodes[(index + 1) % nodes.length]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      nodes[(index - 1 + nodes.length) % nodes.length]?.focus();
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      toast("Copied");
    } catch {
      toast.error("Couldn't copy on this browser.");
    }
    close(true);
  };

  return (
    <div ref={rootRef} className="relative shrink-0 self-center">
      <button
        ref={buttonRef}
        type="button"
        aria-label="Message options"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => (open ? close() : setOpen(true))}
        className={cn(
          "grid size-8 place-items-center rounded-full text-muted-foreground transition-opacity hover:bg-accent focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          // Hidden until hover on mouse devices; always visible on touch screens (no hover there).
          open ? "opacity-100" : "opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-60",
        )}
      >
        <EllipsisVertical size={16} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            ref={menuRef}
            role="menu"
            aria-label="Message options"
            onKeyDown={onMenuKey}
            initial={{ opacity: 0, scale: 0.95, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 520, damping: 32 }}
            className={cn(
              "absolute bottom-9 z-30 min-w-48 overflow-hidden rounded-xl border border-border bg-popover py-1 text-sm text-foreground shadow-lg",
              mine ? "right-0 origin-bottom-right" : "left-0 origin-bottom-left",
            )}
          >
            {items.includes("copy") && (
              <button type="button" role="menuitem" onClick={copy} className="flex min-h-11 w-full items-center gap-3 px-4 text-left hover:bg-accent focus:bg-accent focus:outline-none">
                <Copy size={16} className="text-muted-foreground" /> Copy text
              </button>
            )}
            {items.includes("delete") &&
              (confirming ? (
                <button
                  type="button"
                  role="menuitem"
                  disabled={deleting}
                  onClick={() => {
                    onDelete();
                    close(true);
                  }}
                  className="flex min-h-11 w-full items-center gap-3 px-4 text-left font-semibold text-destructive hover:bg-destructive/10 focus:bg-destructive/10 focus:outline-none"
                >
                  <Trash2 size={16} /> Tap again to delete for everyone
                </button>
              ) : (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => setConfirming(true)}
                  className="flex min-h-11 w-full items-center gap-3 px-4 text-left text-destructive hover:bg-accent focus:bg-accent focus:outline-none"
                >
                  <Trash2 size={16} /> Delete for everyone
                </button>
              ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
