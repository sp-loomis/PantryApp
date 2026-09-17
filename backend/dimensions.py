"""
Dimension models and unit conversion utilities for the Pantry App.

Supports Count, Weight, and Volume dimensions with automatic unit conversion.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
from decimal import Decimal


class DimensionType(str, Enum):
    """Types of dimensions that can be attached to items."""
    COUNT = "count"
    WEIGHT = "weight"
    VOLUME = "volume"


class WeightUnit(str, Enum):
    """Weight units with conversion factors to grams (base unit)."""
    GRAM = "g"
    KILOGRAM = "kg"
    OUNCE = "oz"
    POUND = "lb"


class VolumeUnit(str, Enum):
    """Volume units with conversion factors to milliliters (base unit)."""
    MILLILITER = "ml"
    LITER = "l"
    TEASPOON = "tsp"
    TABLESPOON = "tbsp"
    FLUID_OUNCE = "fl oz"
    CUP = "cup"
    PINT = "pint"
    QUART = "quart"
    GALLON = "gallon"


# Conversion factors to base units
WEIGHT_TO_GRAMS = {
    WeightUnit.GRAM: Decimal("1"),
    WeightUnit.KILOGRAM: Decimal("1000"),
    WeightUnit.OUNCE: Decimal("28.349523125"),
    WeightUnit.POUND: Decimal("453.59237"),
}

VOLUME_TO_ML = {
    VolumeUnit.MILLILITER: Decimal("1"),
    VolumeUnit.LITER: Decimal("1000"),
    VolumeUnit.TEASPOON: Decimal("4.92892"),
    VolumeUnit.TABLESPOON: Decimal("14.7868"),
    VolumeUnit.FLUID_OUNCE: Decimal("29.5735"),
    VolumeUnit.CUP: Decimal("236.588"),
    VolumeUnit.PINT: Decimal("473.176"),
    VolumeUnit.QUART: Decimal("946.353"),
    VolumeUnit.GALLON: Decimal("3785.41"),
}


@dataclass
class Dimension:
    """Represents a single dimension (count, weight, or volume) of an item."""
    dimension_type: DimensionType
    value: Decimal
    unit: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "dimension_type": self.dimension_type.value,
            "value": float(self.value),
            "unit": self.unit
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Dimension":
        """Create from dictionary."""
        return cls(
            dimension_type=DimensionType(data["dimension_type"]),
            value=Decimal(str(data["value"])),
            unit=data["unit"]
        )

    def to_base_unit(self) -> Decimal:
        """Convert this dimension to its base unit value."""
        if self.dimension_type == DimensionType.COUNT:
            return self.value
        elif self.dimension_type == DimensionType.WEIGHT:
            return self.value * WEIGHT_TO_GRAMS.get(WeightUnit(self.unit), Decimal("1"))
        elif self.dimension_type == DimensionType.VOLUME:
            return self.value * VOLUME_TO_ML.get(VolumeUnit(self.unit), Decimal("1"))
        return self.value

    @classmethod
    def from_base_unit(cls, dimension_type: DimensionType, base_value: Decimal, target_unit: str) -> "Dimension":
        """Create a dimension from a base unit value, converting to target unit."""
        if dimension_type == DimensionType.COUNT:
            return cls(dimension_type=dimension_type, value=base_value, unit="units")
        elif dimension_type == DimensionType.WEIGHT:
            conversion_factor = WEIGHT_TO_GRAMS.get(WeightUnit(target_unit), Decimal("1"))
            return cls(
                dimension_type=dimension_type,
                value=base_value / conversion_factor,
                unit=target_unit
            )
        elif dimension_type == DimensionType.VOLUME:
            conversion_factor = VOLUME_TO_ML.get(VolumeUnit(target_unit), Decimal("1"))
            return cls(
                dimension_type=dimension_type,
                value=base_value / conversion_factor,
                unit=target_unit
            )
        return cls(dimension_type=dimension_type, value=base_value, unit=target_unit)


def aggregate_dimensions(items: List[Dict[str, Any]]) -> Dict[str, Dimension]:
    """
    Aggregate dimensions across multiple items.

    Returns a dictionary mapping dimension type to aggregated dimension in an appropriate unit.
    """
    # Accumulate base unit values for each dimension type
    base_totals: Dict[DimensionType, Decimal] = {}

    for item in items:
        dimensions = item.get("dimensions", [])
        for dim_data in dimensions:
            dim = Dimension.from_dict(dim_data)
            dim_type = dim.dimension_type

            if dim_type not in base_totals:
                base_totals[dim_type] = Decimal("0")

            base_totals[dim_type] += dim.to_base_unit()

    # Convert to appropriate units
    result = {}
    for dim_type, base_value in base_totals.items():
        if base_value == 0:
            continue

        if dim_type == DimensionType.COUNT:
            result[dim_type.value] = Dimension(
                dimension_type=dim_type,
                value=base_value,
                unit="units"
            )
        elif dim_type == DimensionType.WEIGHT:
            result[dim_type.value] = _convert_weight_to_appropriate_unit(base_value)
        elif dim_type == DimensionType.VOLUME:
            result[dim_type.value] = _convert_volume_to_appropriate_unit(base_value)

    return result


def aggregate_by_category(
    items: List[Dict[str, Any]], categories: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Aggregate a set of items grouped by their category.

    For each category that has at least one matching item in ``items``, returns a
    rollup honoring the category's declared ``measure_type``:

    - ``count``  -> ``value`` is the *number of items* in the category; ``unit`` is
      ``"items"`` (dimension values are ignored).
    - ``weight`` / ``volume`` -> ``value`` is the sum of that dimension across the
      items, converted to the category's ``preferred_unit`` (base-unit sum when no
      preferred_unit is set).

    Items whose ``category_id`` is unset or points at a category not in
    ``categories`` are excluded. Returns a list of
    ``{category_id, name, measure_type, value (float), unit}`` ordered by category
    name.
    """
    by_id = {c["category_id"]: c for c in categories}

    # Group items under the categories we know about.
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        cat_id = item.get("category_id")
        if cat_id and cat_id in by_id:
            grouped.setdefault(cat_id, []).append(item)

    results: List[Dict[str, Any]] = []
    for cat_id, cat_items in grouped.items():
        category = by_id[cat_id]
        measure_type = category.get("measure_type")
        preferred_unit = category.get("preferred_unit")

        if measure_type == DimensionType.COUNT.value:
            value = Decimal(len(cat_items))
            unit = "items"
        else:
            # Sum the matching dimension across items in base units.
            base_total = Decimal("0")
            for item in cat_items:
                for dim_data in item.get("dimensions", []):
                    if dim_data.get("dimension_type") == measure_type:
                        base_total += Dimension.from_dict(dim_data).to_base_unit()
            if preferred_unit:
                dim = Dimension.from_base_unit(
                    DimensionType(measure_type), base_total, preferred_unit
                )
                value, unit = dim.value, dim.unit
            else:
                value, unit = base_total, _base_unit_for(measure_type)

        results.append({
            "category_id": cat_id,
            "name": category.get("name"),
            "measure_type": measure_type,
            "value": float(value),
            "unit": unit,
        })

    results.sort(key=lambda r: (r["name"] or "").lower())
    return results


def _base_unit_for(measure_type: str) -> str:
    """Base storage unit for a measure type (used when no preferred_unit is set)."""
    if measure_type == DimensionType.WEIGHT.value:
        return WeightUnit.GRAM.value
    if measure_type == DimensionType.VOLUME.value:
        return VolumeUnit.MILLILITER.value
    return "units"


def _convert_weight_to_appropriate_unit(grams: Decimal) -> Dimension:
    """Convert weight in grams to the most appropriate imperial unit."""
    # Convert to pounds first
    pounds = grams / WEIGHT_TO_GRAMS[WeightUnit.POUND]

    if pounds >= 1:
        return Dimension(
            dimension_type=DimensionType.WEIGHT,
            value=pounds,
            unit=WeightUnit.POUND.value
        )
    else:
        # Use ounces for smaller amounts
        ounces = grams / WEIGHT_TO_GRAMS[WeightUnit.OUNCE]
        return Dimension(
            dimension_type=DimensionType.WEIGHT,
            value=ounces,
            unit=WeightUnit.OUNCE.value
        )


def _convert_volume_to_appropriate_unit(ml: Decimal) -> Dimension:
    """Convert volume in milliliters to the most appropriate imperial unit."""
    # Convert to various units and choose the most readable
    gallons = ml / VOLUME_TO_ML[VolumeUnit.GALLON]
    quarts = ml / VOLUME_TO_ML[VolumeUnit.QUART]
    cups = ml / VOLUME_TO_ML[VolumeUnit.CUP]
    fluid_ounces = ml / VOLUME_TO_ML[VolumeUnit.FLUID_OUNCE]

    if gallons >= 1:
        return Dimension(
            dimension_type=DimensionType.VOLUME,
            value=gallons,
            unit=VolumeUnit.GALLON.value
        )
    elif quarts >= 1:
        return Dimension(
            dimension_type=DimensionType.VOLUME,
            value=quarts,
            unit=VolumeUnit.QUART.value
        )
    elif cups >= 1:
        return Dimension(
            dimension_type=DimensionType.VOLUME,
            value=cups,
            unit=VolumeUnit.CUP.value
        )
    else:
        return Dimension(
            dimension_type=DimensionType.VOLUME,
            value=fluid_ounces,
            unit=VolumeUnit.FLUID_OUNCE.value
        )


def validate_dimension(dimension_type: str, unit: str) -> bool:
    """Validate that a unit is appropriate for a dimension type."""
    try:
        dim_type = DimensionType(dimension_type)
        if dim_type == DimensionType.COUNT:
            return unit == "units"
        elif dim_type == DimensionType.WEIGHT:
            return unit in [u.value for u in WeightUnit]
        elif dim_type == DimensionType.VOLUME:
            return unit in [u.value for u in VolumeUnit]
        return False
    except ValueError:
        return False


def validate_category_measure(measure_type: str, preferred_unit: Optional[str]) -> None:
    """Validate a category's measure_type + preferred_unit pair, raising ValueError.

    - ``count``: aggregation counts items, so ``preferred_unit`` is not used and
      must be empty/None.
    - ``weight`` / ``volume``: ``preferred_unit`` is required and must be a valid
      unit for that dimension type.
    """
    try:
        dim_type = DimensionType(measure_type)
    except ValueError:
        valid = ", ".join(t.value for t in DimensionType)
        raise ValueError(f"Invalid measure_type {measure_type!r} (must be one of {valid})")

    if dim_type == DimensionType.COUNT:
        if preferred_unit:
            raise ValueError("preferred_unit is not allowed for a 'count' category")
        return

    if not preferred_unit:
        raise ValueError(f"preferred_unit is required for a '{measure_type}' category")
    if not validate_dimension(measure_type, preferred_unit):
        raise ValueError(
            f"Invalid preferred_unit {preferred_unit!r} for measure_type {measure_type!r}"
        )
