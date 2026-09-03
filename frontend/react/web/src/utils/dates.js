/**
 * Date helpers for use-by dates and expiry badges.
 */

export function parseDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(iso) {
  const d = parseDate(iso);
  if (!d) return '';
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** Whole days from now until the date (negative = past). */
export function daysUntil(iso) {
  const d = parseDate(iso);
  if (!d) return null;
  return Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

/**
 * Expiry badge descriptor for an item's use_by_date, or null if none.
 * Red when expired or within 3 days, orange within a week, otherwise a plain date.
 */
export function expiryStatus(iso) {
  const days = daysUntil(iso);
  if (days === null) return null;
  if (days < 0) return { label: 'Expired', color: 'red' };
  if (days === 0) return { label: 'Today', color: 'red' };
  if (days <= 3) return { label: `${days}d left`, color: 'red' };
  if (days <= 7) return { label: `${days}d left`, color: 'orange' };
  return { label: formatDate(iso), color: 'gray' };
}
