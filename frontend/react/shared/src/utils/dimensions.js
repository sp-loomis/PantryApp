/**
 * Dimensions (measures)
 *
 * Product rule: every item is "one unit". The only user-facing measure is a
 * single OPTIONAL weight OR volume. Count is never sent (the backend's
 * user-editable count is slated for removal). These helpers convert between the
 * item form's measure shape `{ type, value, unit }` and the backend's
 * `dimensions: [{ dimension_type, value, unit }]`.
 *
 * Valid (type, unit) pairs mirror backend/dimensions.py.
 */

export const MEASURE_TYPES = ['weight', 'volume'];

export const UNITS = {
  weight: ['g', 'kg', 'oz', 'lb'],
  volume: ['ml', 'l', 'tsp', 'tbsp', 'fl oz', 'cup', 'pint', 'quart', 'gallon'],
};

/** Sensible default unit when a user first picks a type. */
export const DEFAULT_UNIT = { weight: 'kg', volume: 'l' };

/** An empty measure (no weight/volume set). */
export const EMPTY_MEASURE = { type: '', value: '', unit: '' };

export function isValidUnit(type, unit) {
  return UNITS[type]?.includes(unit) ?? false;
}

function hasValue(value) {
  return value !== '' && value !== null && value !== undefined;
}

/**
 * Validate a measure. The measure is optional, so a fully-empty one is valid.
 * @returns {string|null} error message or null if valid.
 */
export function validateMeasure({ type, value, unit } = {}) {
  const filledType = MEASURE_TYPES.includes(type);
  const filledValue = hasValue(value);

  // Nothing entered → valid (no measure on this item).
  if (!filledType && !filledValue) return null;

  if (!filledType) return 'Choose weight or volume';
  if (!filledValue) return 'Enter an amount';

  const num = Number(value);
  if (Number.isNaN(num) || num <= 0) return 'Amount must be a positive number';
  if (!isValidUnit(type, unit)) return 'Choose a valid unit';

  return null;
}

/**
 * Convert the form measure to the backend `dimensions` array.
 * Returns `[]` when no measure is set. Never includes a count dimension.
 */
export function measureToDimensions({ type, value, unit } = {}) {
  if (!MEASURE_TYPES.includes(type) || !hasValue(value)) return [];
  const num = Number(value);
  if (Number.isNaN(num)) return [];
  return [{ dimension_type: type, value: num, unit }];
}

/** Extract the single weight/volume measure from an item's dimensions (ignores count). */
export function dimensionsToMeasure(dimensions = []) {
  const found = dimensions.find(
    (d) => d.dimension_type === 'weight' || d.dimension_type === 'volume'
  );
  return found
    ? { type: found.dimension_type, value: found.value, unit: found.unit }
    : { ...EMPTY_MEASURE };
}

/** Render one dimension as e.g. "2 lb". */
export function formatDimension(dimension) {
  if (!dimension) return '';
  return `${dimension.value} ${dimension.unit}`;
}

/** Render an item's weight/volume measure as a short string, or '' if none. */
export function formatMeasure(dimensions = []) {
  const found = dimensions.find(
    (d) => d.dimension_type === 'weight' || d.dimension_type === 'volume'
  );
  return found ? formatDimension(found) : '';
}
