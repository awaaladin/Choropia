import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { spring, useCalmMotion } from "./motion";

/**
 * The escrow padlock. When `play` becomes true the open shackle drops into the body and the lock settles with a small
 * spring dip: the moment money is held. Without `play` it simply shows its state. Reduced motion: no movement.
 */
export function Padlock({ locked, play, size = 28 }: { locked: boolean; play: boolean; size?: number }) {
  const calm = useCalmMotion();
  const [closed, setClosed] = useState(locked && !play);

  useEffect(() => {
    if (!locked) return setClosed(false);
    if (!play || calm) return setClosed(true);
    const t = window.setTimeout(() => setClosed(true), 120); // let the card morph first
    return () => window.clearTimeout(t);
  }, [locked, play, calm]);

  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      animate={play && closed && !calm ? { scale: [1, 0.9, 1.04, 1], y: [0, 1.5, 0, 0] } : { scale: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 0.68, 0, 1] }}
    >
      {/* shackle: raised and swung open, or seated */}
      <motion.path
        d="M7.5 11V7.5a4.5 4.5 0 0 1 9 0V11"
        initial={false}
        animate={closed ? { y: 0, rotate: 0 } : { y: -2.5, rotate: -8 }}
        style={{ originX: "16.5px", originY: "11px" }}
        transition={calm ? { duration: 0 } : { ...spring, stiffness: 420, damping: 18 }}
      />
      <rect x="4.5" y="11" width="15" height="10" rx="2.5" />
      <motion.circle
        cx="12"
        cy="16"
        r="1.4"
        fill="currentColor"
        stroke="none"
        initial={false}
        animate={{ opacity: closed ? 1 : 0.35 }}
        transition={{ duration: 0.2 }}
      />
    </motion.svg>
  );
}
