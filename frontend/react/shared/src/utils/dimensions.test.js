import { describe, it, expect } from 'vitest';
import {
  UNITS,
  validateMeasure,
  measureToDimensions,
  dimensionsToMeasure,
  formatMeasure,
  isValidUnit,
} from './dimensions.js';

describe('unit tables', () => {
  it('only exposes weight and volume (no count)', () => {
    expect(Object.keys(UNITS).sort()).toEqual(['volume', 'weight']);
  });

  it('validates (type, unit) pairs against the backend contract', () => {
    expect(isValidUnit('weight', 'lb')).toBe(true);
    expect(isValidUnit('volume', 'ml')).toBe(true);
    expect(isValidUnit('weight', 'ml')).toBe(false);
    expect(isValidUnit('count', 'units')).toBe(false);
  });
});

describe('validateMeasure', () => {
  it('treats a fully-empty measure as valid (measure is optional)', () => {
    expect(validateMeasure({ type: '', value: '', unit: '' })).toBeNull();
  });

  it('requires a type when an amount is given', () => {
    expect(validateMeasure({ type: '', value: '2', unit: '' })).toMatch(/weight or volume/i);
  });

  it('requires a positive amount when a type is chosen', () => {
    expect(validateMeasure({ type: 'weight', value: '', unit: 'kg' })).toMatch(/amount/i);
    expect(validateMeasure({ type: 'weight', value: '0', unit: 'kg' })).toMatch(/positive/i);
    expect(validateMeasure({ type: 'weight', value: '-1', unit: 'kg' })).toMatch(/positive/i);
  });

  it('rejects an invalid unit for the type', () => {
    expect(validateMeasure({ type: 'weight', value: '2', unit: 'ml' })).toMatch(/valid unit/i);
  });

  it('accepts a well-formed measure', () => {
    expect(validateMeasure({ type: 'weight', value: '2', unit: 'kg' })).toBeNull();
    expect(validateMeasure({ type: 'volume', value: '1.5', unit: 'l' })).toBeNull();
  });
});

describe('measureToDimensions', () => {
  it('returns [] for an empty measure', () => {
    expect(measureToDimensions({ type: '', value: '', unit: '' })).toEqual([]);
  });

  it('never emits a count dimension', () => {
    const dims = measureToDimensions({ type: 'weight', value: '2', unit: 'kg' });
    expect(dims).toEqual([{ dimension_type: 'weight', value: 2, unit: 'kg' }]);
    expect(dims.some((d) => d.dimension_type === 'count')).toBe(false);
  });

  it('coerces the value to a number', () => {
    expect(measureToDimensions({ type: 'volume', value: '1.5', unit: 'l' })[0].value).toBe(1.5);
  });
});

describe('dimensionsToMeasure', () => {
  it('extracts the weight/volume measure, ignoring count', () => {
    const measure = dimensionsToMeasure([
      { dimension_type: 'count', value: 1, unit: 'units' },
      { dimension_type: 'weight', value: 2, unit: 'lb' },
    ]);
    expect(measure).toEqual({ type: 'weight', value: 2, unit: 'lb' });
  });

  it('returns an empty measure when there is no weight/volume', () => {
    expect(dimensionsToMeasure([])).toEqual({ type: '', value: '', unit: '' });
  });
});

describe('formatMeasure', () => {
  it('formats the weight/volume dimension', () => {
    expect(formatMeasure([{ dimension_type: 'weight', value: 2, unit: 'lb' }])).toBe('2 lb');
  });
  it('returns empty string when there is no measure', () => {
    expect(formatMeasure([])).toBe('');
  });
});
