// lib/utils.ts
// Utility functions for the application
// Contains cn function for className merging
// RELEVANT FILES: components/ui/*.tsx

import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}