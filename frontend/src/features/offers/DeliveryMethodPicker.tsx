import { motion } from "motion/react";
import { Bike, Check, MapPin, Truck, type LucideIcon } from "lucide-react";
import type { OfferDeliveryMethod } from "@/lib/types";
import { cn } from "@/lib/utils";
import { snappy, useCalmMotion, usePress } from "./motion";

export const DELIVERY: Record<OfferDeliveryMethod, { label: string; hint: string; icon: LucideIcon }> = {
  meetup: { label: "Meet up", hint: "Hand it over in person", icon: MapPin },
  seller_delivers: { label: "Seller delivers", hint: "The seller brings it to you", icon: Truck },
  rider: { label: "Choropia rider", hint: "A rider delivers it; delivery fee extra", icon: Bike },
};

const ORDER: OfferDeliveryMethod[] = ["meetup", "seller_delivers", "rider"];

/** Pick handover methods: several (seller, making the offer) or exactly one (buyer, paying). */
export function DeliveryMethodPicker({
  mode,
  options = ORDER,
  value,
  onChange,
  unavailable = [],
  legend,
}: {
  mode: "multiple" | "single";
  options?: OfferDeliveryMethod[];
  value: OfferDeliveryMethod[];
  onChange: (value: OfferDeliveryMethod[]) => void;
  unavailable?: OfferDeliveryMethod[];
  legend: string;
}) {
  const calm = useCalmMotion();
  const press = usePress(calm);
  const toggle = (method: OfferDeliveryMethod) => {
    if (mode === "single") return onChange([method]);
    onChange(value.includes(method) ? value.filter((m) => m !== method) : [...value, method]);
  };

  return (
    <fieldset>
      <legend className="text-sm font-medium text-o-text">{legend}</legend>
      <div className="mt-1.5 grid gap-2" role={mode === "single" ? "radiogroup" : "group"} aria-label={legend}>
        {ORDER.filter((m) => options.includes(m)).map((method) => {
          const { label, hint, icon: Icon } = DELIVERY[method];
          const checked = value.includes(method);
          const off = unavailable.includes(method);
          return (
            <motion.button
              key={method}
              type="button"
              {...press}
              role={mode === "single" ? "radio" : "checkbox"}
              aria-checked={checked}
              disabled={off}
              onClick={() => toggle(method)}
              className={cn(
                "flex min-h-14 items-center gap-3 rounded-o-md border px-4 py-3 text-left transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent disabled:opacity-45",
                checked ? "border-o-accent bg-o-tide" : "border-o-hairline bg-o-raised hover:bg-o-surface",
              )}
            >
              <Icon size={20} strokeWidth={1.75} className={checked ? "text-o-tide-fg" : "text-o-muted"} aria-hidden="true" />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-o-text">{label}</span>
                <span className="block text-xs text-o-muted">{off ? "Not set up for this listing" : hint}</span>
              </span>
              <span
                className={cn(
                  "grid size-5 shrink-0 place-items-center border-2 transition-colors",
                  mode === "single" ? "rounded-full" : "rounded-md",
                  checked ? "border-o-accent bg-o-accent text-o-accent-fg" : "border-o-hairline",
                )}
                aria-hidden="true"
              >
                {checked && (
                  <motion.span initial={calm ? false : { scale: 0.4 }} animate={{ scale: 1 }} transition={snappy}>
                    <Check size={12} strokeWidth={3} />
                  </motion.span>
                )}
              </span>
            </motion.button>
          );
        })}
      </div>
    </fieldset>
  );
}
