import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMicros(micros: number, currency: "EUR" = "EUR") {
  const value = micros / 1_000_000;
  return new Intl.NumberFormat("en-IE", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
}

export function formatNumber(n: number, digits = 0) {
  return new Intl.NumberFormat("en-IE", { maximumFractionDigits: digits }).format(n);
}

export function eurosToMicros(euros: number) {
  return Math.round(euros * 1_000_000);
}

export function microsToEuros(micros: number) {
  return micros / 1_000_000;
}
