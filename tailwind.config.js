/** @type {import('tailwindcss').Config} */
// Design tokens ported from the Stitch "Midnight Ledger" design system
// (android/stitch_choropia_marketplace_android_app/midnight_ledger/DESIGN.md).
//
// Colors resolve through CSS custom properties (defined as space-separated RGB channels in
// base.html, e.g. `--color-primary: 11 25 44;`) via Tailwind's `rgb(var(...) / <alpha-value>)`
// pattern. This is what lets `bg-primary/5`-style opacity modifiers keep working AND lets
// toggling the `dark` class on <html> re-theme the whole site instantly — no per-template
// `dark:` variants needed.
function withOpacity(variableName) {
  return `rgb(var(${variableName}) / <alpha-value>)`;
}

module.exports = {
  content: ["./core/templates/**/*.html", "./templates/**/*.html", "./core/static/core/**/*.js"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: withOpacity("--color-surface"),
        "surface-bright": withOpacity("--color-surface-bright"),
        "surface-container-lowest": withOpacity("--color-surface-container-lowest"),
        "surface-container-low": withOpacity("--color-surface-container-low"),
        "surface-container": withOpacity("--color-surface-container"),
        "on-surface": withOpacity("--color-on-surface"),
        "on-surface-variant": withOpacity("--color-on-surface-variant"),
        outline: withOpacity("--color-outline"),
        "outline-variant": withOpacity("--color-outline-variant"),
        primary: withOpacity("--color-primary"),
        "on-primary": withOpacity("--color-on-primary"),
        secondary: withOpacity("--color-secondary"),
        "on-secondary": withOpacity("--color-on-secondary"),
        "secondary-container": withOpacity("--color-secondary-container"),
        "on-secondary-container": withOpacity("--color-on-secondary-container"),
        error: withOpacity("--color-error"),
        "on-error": withOpacity("--color-on-error"),
        "error-container": withOpacity("--color-error-container"),
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        card: "0.5rem",
        sheet: "0.75rem",
        badge: "0.125rem",
      },
      boxShadow: {
        elevated: "0px 4px 16px -2px rgba(11, 25, 44, 0.06), 0px 1px 3px 0px rgba(11, 25, 44, 0.04)",
      },
    },
  },
  plugins: [],
};
