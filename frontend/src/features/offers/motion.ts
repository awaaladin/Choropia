import { useReducedMotion, type Transition } from "motion/react";
import { usePrefs } from "@/lib/prefs";

/** Standard spring: sheets, cards, layout morphs. Interruptible by design (springs carry velocity into a reversal). */
export const spring: Transition = { type: "spring", stiffness: 300, damping: 28, mass: 1 };
/** Snappier spring for presses and small pops. */
export const snappy: Transition = { type: "spring", stiffness: 520, damping: 30, mass: 0.8 };
/** What replaces movement when motion is reduced: a short crossfade. */
export const fade: Transition = { duration: 0.16, ease: "easeOut" };

/** True when the person asked for less motion, in the OS or in Choropia's own settings. */
export function useCalmMotion(): boolean {
  const os = useReducedMotion();
  const { motion } = usePrefs();
  return Boolean(os) || motion === "reduced";
}

/** Press feedback for buttons and keys: scale to 0.97, spring back. No scale when motion is reduced. */
export function usePress(calm: boolean) {
  return calm ? {} : { whileTap: { scale: 0.97 }, transition: snappy };
}
