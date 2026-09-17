/**
 * Expiry-filter helpers, shared by the ExpiryFilter control, the Search page, and
 * report query builders. Kept out of the component file so fast-refresh stays
 * happy (a component module should export only components).
 */

// Preset expiry spans (days from today). 'custom' reveals a date picker.
export const EXPIRY_PRESETS = [
  { value: '3', label: 'Within 3 days' },
  { value: '7', label: 'Within 1 week' },
  { value: '14', label: 'Within 2 weeks' },
  { value: '30', label: 'Within 1 month' },
  { value: 'custom', label: 'By a date…' },
];

/** Local YYYY-MM-DD (the backend accepts date-only ISO and rejects a trailing Z). */
export function toLocalYMD(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Resolve a preset span (days from today) to a date-only upper bound. */
export function presetToDate(days) {
  const d = new Date();
  d.setDate(d.getDate() + Number(days));
  return toLocalYMD(d);
}
