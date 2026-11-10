/** Money in the offer screens is always integer kobo. These helpers never use floats for amounts. */

const grouping = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 });

/** "₦185,000" or "₦185,000.50" from kobo. */
export function formatKobo(kobo: number): string {
  const sign = kobo < 0 ? "-" : "";
  const abs = Math.abs(Math.trunc(kobo));
  const naira = Math.floor(abs / 100);
  const rest = abs % 100;
  return `${sign}₦${grouping.format(naira)}${rest ? `.${String(rest).padStart(2, "0")}` : ""}`;
}

/** What a screen reader should say: "185,000 naira". */
export function spokenKobo(kobo: number): string {
  const naira = Math.floor(Math.abs(kobo) / 100);
  const rest = Math.abs(kobo) % 100;
  return `${grouping.format(naira)} naira${rest ? ` ${rest} kobo` : ""}`;
}

/** Parses what a person typed ("185,000", "185000.5") into kobo, or null if it isn't an amount. String maths only. */
export function parseNairaToKobo(input: string): number | null {
  const clean = input.replace(/[₦,\s]/g, "");
  if (!/^\d{1,11}(\.\d{0,2})?$/.test(clean)) return null;
  const [whole, frac = ""] = clean.split(".");
  return Number(whole) * 100 + Number((frac + "00").slice(0, 2));
}

/** "185,000" for an input field (no currency sign; the field shows ₦ itself). */
export function koboToInput(kobo: number): string {
  const naira = Math.floor(kobo / 100);
  const rest = kobo % 100;
  return `${grouping.format(naira)}${rest ? `.${String(rest).padStart(2, "0")}` : ""}`;
}

/** Whole-percent discount from the listed price, e.g. 8 for 8% off. 0 when not lower. */
export function discountPercent(amountKobo: number, listedKobo: number): number {
  if (listedKobo <= 0 || amountKobo >= listedKobo) return 0;
  return Math.round(((listedKobo - amountKobo) * 100) / listedKobo);
}

/** "2:14:09" / "14:09" countdown text from seconds. */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(h ? 2 : 1, "0");
  return h ? `${h}:${mm}:${String(sec).padStart(2, "0")}` : `${mm}:${String(sec).padStart(2, "0")}`;
}

/** Light haptic tick where the device supports it (Android Chrome). Silent elsewhere. */
export function haptic(pattern: number | number[] = 8) {
  try {
    if (typeof navigator !== "undefined" && "vibrate" in navigator) navigator.vibrate(pattern);
  } catch {
    /* not supported */
  }
}
