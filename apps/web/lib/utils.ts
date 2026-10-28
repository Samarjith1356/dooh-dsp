import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMicros(micros: number, currency = "GBP") {
  const value = micros / 1_000_000;
  return new Intl.NumberFormat("en-GB", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
}

export function formatNumber(n: number, digits = 1) {
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: digits }).format(n);
}
