import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function naira(value: number | string) {
  return `₦${Number(value).toLocaleString()}`;
}

export function initials(name?: string | null) {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function timeAgo(iso: string) {
  const seconds = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  const steps: [number, string][] = [
    [60, "s"],
    [60, "m"],
    [24, "h"],
    [7, "d"],
  ];
  let value = seconds;
  for (const [size, unit] of steps) {
    if (value < size) return `${value}${unit} ago`;
    value = Math.floor(value / size);
  }
  return new Date(iso).toLocaleDateString();
}

export const STATUS_LABELS: Record<string, string> = {
  pending_payment: "Awaiting payment",
  paid_escrow: "Paid — in escrow",
  courier_assigned: "Courier assigned",
  in_transit: "In transit",
  delivered: "Delivered",
  confirmed: "Confirmed",
  disputed: "Disputed",
  completed: "Completed",
  refunded: "Refunded",
};
