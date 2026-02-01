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
