import { AnimatePresence, motion } from "motion/react";
import { CircleAlert } from "lucide-react";
import { fade, spring, useCalmMotion } from "./motion";

/** An error shown where it happened, announced to screen readers. Renders nothing when there is no message. */
export function InlineError({ message, id }: { message?: string | null; id?: string }) {
  const calm = useCalmMotion();
  return (
    <div aria-live="assertive" aria-atomic="true">
      <AnimatePresence initial={false}>
        {message && (
          <motion.p
            id={id}
            key={message}
            role="alert"
            className="mt-2 flex items-start gap-2 rounded-o-sm bg-o-danger-bg px-3 py-2 text-sm text-o-danger"
            initial={calm ? { opacity: 0 } : { opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={calm ? fade : spring}
          >
            <CircleAlert size={16} strokeWidth={1.75} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>{message}</span>
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}
