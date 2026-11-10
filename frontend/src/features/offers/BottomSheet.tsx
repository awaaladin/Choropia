import { AnimatePresence, motion, useDragControls, type PanInfo } from "motion/react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { fade, spring, useCalmMotion } from "./motion";

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * A sheet that springs up from the bottom. Drag the handle (or the header) down to dismiss: it follows the finger and
 * springs back if let go early. Focus moves into the sheet, is trapped there, and returns to whatever opened it.
 * With reduced motion it crossfades and can't be dragged.
 */
export function BottomSheet({
  open,
  onClose,
  title,
  description,
  children,
  initialFocusRef,
  dismissible = true,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
  /** False while something must not be interrupted (a payment being opened). */
  dismissible?: boolean;
}) {
  const calm = useCalmMotion();
  const controls = useDragControls();
  const sheetRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const frame = requestAnimationFrame(() => {
      const target = initialFocusRef?.current ?? sheetRef.current?.querySelector<HTMLElement>(FOCUSABLE);
      target?.focus();
    });
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
      returnFocusRef.current?.focus?.();
    };
  }, [open, initialFocusRef]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape" && dismissible) {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !sheetRef.current) return;
    const nodes = Array.from(sheetRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((n) => n.offsetParent !== null);
    if (!nodes.length) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const onDragEnd = (_: unknown, info: PanInfo) => {
    if (dismissible && (info.offset.y > 120 || info.velocity.y > 650)) onClose();
  };

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" onKeyDown={onKeyDown}>
          <motion.div
            className="absolute inset-0 bg-[rgb(7_15_34/0.45)] backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={fade}
            onClick={() => dismissible && onClose()}
            aria-hidden="true"
          />
          <motion.div
            ref={sheetRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={description ? descId : undefined}
            className={cn(
              "relative z-10 flex max-h-[92svh] w-full flex-col overflow-hidden rounded-t-o-lg bg-o-raised text-o-text shadow-o-card",
              "sm:max-w-md sm:rounded-o-lg",
            )}
            initial={calm ? { opacity: 0 } : { y: "100%" }}
            animate={calm ? { opacity: 1 } : { y: 0 }}
            exit={calm ? { opacity: 0 } : { y: "100%" }}
            transition={calm ? fade : spring}
            drag={calm || !dismissible ? false : "y"}
            dragControls={controls}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.7 }}
            onDragEnd={onDragEnd}
          >
            <div
              className="flex shrink-0 cursor-grab touch-none flex-col items-center px-5 pt-2 active:cursor-grabbing"
              onPointerDown={(event) => !calm && dismissible && controls.start(event)}
            >
              <span className="h-1 w-10 rounded-full bg-o-hairline" aria-hidden="true" />
              <div className="mt-3 flex w-full items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 id={titleId} className="font-display text-lg font-semibold tracking-tight">
                    {title}
                  </h2>
                  {description && (
                    <p id={descId} className="mt-0.5 text-sm text-o-muted">
                      {description}
                    </p>
                  )}
                </div>
                {dismissible && (
                  <button
                    type="button"
                    onClick={onClose}
                    onPointerDown={(e) => e.stopPropagation()}
                    className="-mr-2 grid size-11 shrink-0 place-items-center rounded-full text-o-muted hover:bg-o-tide focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent"
                    aria-label="Close"
                  >
                    <X size={20} strokeWidth={1.75} />
                  </button>
                )}
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-3">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
