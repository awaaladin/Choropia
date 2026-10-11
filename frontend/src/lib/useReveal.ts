import { useEffect } from "react";
import { useLocation } from "react-router";

/** Fades/slides in any `[data-reveal]` element as it scrolls into view (see styles.css). */
export function useReveal() {
  const { pathname } = useLocation();
  useEffect(() => {
    const elements = document.querySelectorAll("[data-reveal]");
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }),
      { threshold: 0.08 },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [pathname]);
}
