"""
Unit tests for dimension functionality.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from decimal import Decimal
from dimensions import (
    Dimension, DimensionType, WeightUnit, VolumeUnit,
    aggregate_dimensions, validate_dimension,
    WEIGHT_TO_GRAMS, VOLUME_TO_ML
)


class TestDimension(unittest.TestCase):
    """Test the Dimension class."""

    def test_create_count_dimension(self):
        """Test creating a count dimension."""
        dim = Dimension(
            dimension_type=DimensionType.COUNT,
            value=Decimal("5"),
            unit="units"
        )
        self.assertEqual(dim.dimension_type, DimensionType.COUNT)
        self.assertEqual(dim.value, Decimal("5"))
        self.assertEqual(dim.unit, "units")

    def test_create_weight_dimension(self):
        """Test creating a weight dimension."""
        dim = Dimension(
            dimension_type=DimensionType.WEIGHT,
            value=Decimal("2.5"),
            unit=WeightUnit.POUND.value
        )
        self.assertEqual(dim.dimension_type, DimensionType.WEIGHT)
        self.assertEqual(dim.value, Decimal("2.5"))
        self.assertEqual(dim.unit, "lb")

    def test_create_volume_dimension(self):
        """Test creating a volume dimension."""
        dim = Dimension(
            dimension_type=DimensionType.VOLUME,
            value=Decimal("1"),
            unit=VolumeUnit.GALLON.value
        )
        self.assertEqual(dim.dimension_type, DimensionType.VOLUME)
        self.assertEqual(dim.value, Decimal("1"))
        self.assertEqual(dim.unit, "gallon")

    def test_to_dict(self):
        """Test converting dimension to dictionary."""
        dim = Dimension(
            dimension_type=DimensionType.WEIGHT,
            value=Decimal("10"),
            unit=WeightUnit.KILOGRAM.value
        )
        dim_dict = dim.to_dict()
        self.assertEqual(dim_dict["dimension_type"], "weight")
        self.assertEqual(dim_dict["value"], 10.0)
        self.assertEqual(dim_dict["unit"], "kg")

    def test_from_dict(self):
        """Test creating dimension from dictionary."""
        dim_dict = {
            "dimension_type": "volume",
            "value": 2.5,
            "unit": "cup"
        }
        dim = Dimension.from_dict(dim_dict)
        self.assertEqual(dim.dimension_type, DimensionType.VOLUME)
        self.assertEqual(dim.value, Decimal("2.5"))
        self.assertEqual(dim.unit, "cup")

    def test_weight_to_base_unit(self):
        """Test converting weight to base unit (grams)."""
        # 2 pounds to grams
        dim = Dimension(
            dimension_type=DimensionType.WEIGHT,
            value=Decimal("2"),
            unit=WeightUnit.POUND.value
        )
        base_value = dim.to_base_unit()
        expected = Decimal("2") * WEIGHT_TO_GRAMS[WeightUnit.POUND]
        self.assertEqual(base_value, expected)

    def test_volume_to_base_unit(self):
        """Test converting volume to base unit (milliliters)."""
        # 1 gallon to milliliters
        dim = Dimension(
            dimension_type=DimensionType.VOLUME,
            value=Decimal("1"),
            unit=VolumeUnit.GALLON.value
        )
        base_value = dim.to_base_unit()
        expected = VOLUME_TO_ML[VolumeUnit.GALLON]
        self.assertEqual(base_value, expected)

    def test_count_to_base_unit(self):
        """Test that count dimensions don't need conversion."""
        dim = Dimension(
            dimension_type=DimensionType.COUNT,
            value=Decimal("10"),
            unit="units"
        )
        base_value = dim.to_base_unit()
        self.assertEqual(base_value, Decimal("10"))

    def test_from_base_unit_weight(self):
        """Test creating weight dimension from base unit."""
        # 1000 grams to kilograms
        dim = Dimension.from_base_unit(
            DimensionType.WEIGHT,
            Decimal("1000"),
            WeightUnit.KILOGRAM.value
        )
        self.assertEqual(dim.dimension_type, DimensionType.WEIGHT)
        self.assertEqual(dim.value, Decimal("1"))
        self.assertEqual(dim.unit, "kg")

    def test_from_base_unit_volume(self):
        """Test creating volume dimension from base unit."""
        # 3785.41 ml to gallons
        dim = Dimension.from_base_unit(
            DimensionType.VOLUME,
            Decimal("3785.41"),
            VolumeUnit.GALLON.value
        )
        self.assertEqual(dim.dimension_type, DimensionType.VOLUME)
        self.assertAlmostEqual(float(dim.value), 1.0, places=2)
        self.assertEqual(dim.unit, "gallon")


class TestValidation(unittest.TestCase):
    """Test dimension validation."""

    def test_validate_count_dimension(self):
        """Test validating count dimensions."""
        self.assertTrue(validate_dimension("count", "units"))
        self.assertFalse(validate_dimension("count", "lb"))

    def test_validate_weight_dimension(self):
        """Test validating weight dimensions."""
        self.assertTrue(validate_dimension("weight", "lb"))
        self.assertTrue(validate_dimension("weight", "kg"))
        self.assertTrue(validate_dimension("weight", "oz"))
        self.assertTrue(validate_dimension("weight", "g"))
        self.assertFalse(validate_dimension("weight", "cup"))

    def test_validate_volume_dimension(self):
        """Test validating volume dimensions."""
        self.assertTrue(validate_dimension("volume", "gallon"))
        self.assertTrue(validate_dimension("volume", "cup"))
        self.assertTrue(validate_dimension("volume", "ml"))
        self.assertFalse(validate_dimension("volume", "lb"))

    def test_validate_invalid_type(self):
        """Test validation with invalid dimension type."""
        self.assertFalse(validate_dimension("invalid", "units"))


class TestAggregation(unittest.TestCase):
    """Test dimension aggregation."""

    def test_aggregate_single_dimension_type(self):
        """Test aggregating items with same dimension type."""
        items = [
            {
                "dimensions": [
                    {"dimension_type": "weight", "value": 1.0, "unit": "lb"}
                ]
            },
            {
                "dimensions": [
                    {"dimension_type": "weight", "value": 16.0, "unit": "oz"}
                ]
            }
        ]

        result = aggregate_dimensions(items)
        self.assertIn("weight", result)

        # 1 lb + 16 oz = 2 lb total
        weight_dim = result["weight"]
        self.assertEqual(weight_dim.dimension_type, DimensionType.WEIGHT)
        self.assertAlmostEqual(float(weight_dim.value), 2.0, places=1)

    def test_aggregate_multiple_dimension_types(self):
        """Test aggregating items with different dimension types."""
        items = [
            {
                "dimensions": [
                    {"dimension_type": "count", "value": 5.0, "unit": "units"},
                    {"dimension_type": "weight", "value": 1.0, "unit": "lb"}
                ]
            },
            {
                "dimensions": [
                    {"dimension_type": "count", "value": 3.0, "unit": "units"},
                    {"dimension_type": "volume", "value": 2.0, "unit": "cup"}
                ]
            }
        ]

        result = aggregate_dimensions(items)

        # Check count
        self.assertIn("count", result)
        count_dim = result["count"]
        self.assertEqual(float(count_dim.value), 8.0)

        # Check weight
        self.assertIn("weight", result)
        weight_dim = result["weight"]
        self.assertAlmostEqual(float(weight_dim.value), 1.0, places=1)

        # Check volume
        self.assertIn("volume", result)

    def test_aggregate_empty_dimensions(self):
        """Test aggregating items with no dimensions."""
        items = [
            {"dimensions": []},
            {"dimensions": []}
        ]

        result = aggregate_dimensions(items)
        self.assertEqual(len(result), 0)

    def test_aggregate_zero_values_not_reported(self):
        """Test that zero dimension values are not reported."""
        items = [
            {
                "dimensions": [
                    {"dimension_type": "weight", "value": 1.0, "unit": "lb"}
                ]
            }
        ]

        result = aggregate_dimensions(items)

        # Should only have weight, not count or volume
        self.assertIn("weight", result)
        self.assertNotIn("count", result)
        self.assertNotIn("volume", result)

    def test_aggregate_volume_unit_scaling(self):
        """Test that volume aggregation scales to appropriate units."""
        items = [
            {
                "dimensions": [
                    {"dimension_type": "volume", "value": 1.0, "unit": "gallon"}
                ]
            },
            {
                "dimensions": [
                    {"dimension_type": "volume", "value": 1.0, "unit": "gallon"}
                ]
            }
        ]

        result = aggregate_dimensions(items)
        self.assertIn("volume", result)

        # 2 gallons should be reported in gallons
        volume_dim = result["volume"]
        self.assertAlmostEqual(float(volume_dim.value), 2.0, places=1)
        self.assertEqual(volume_dim.unit, "gallon")

    def test_aggregate_weight_unit_scaling_to_ounces(self):
        """Test that small weights are reported in ounces."""
        items = [
            {
                "dimensions": [
                    {"dimension_type": "weight", "value": 4.0, "unit": "oz"}
                ]
            },
            {
                "dimensions": [
                    {"dimension_type": "weight", "value": 2.0, "unit": "oz"}
                ]
            }
        ]

        result = aggregate_dimensions(items)
        self.assertIn("weight", result)

        # 6 oz should be reported in ounces (less than 1 lb)
        weight_dim = result["weight"]
        self.assertEqual(weight_dim.unit, "oz")
        self.assertAlmostEqual(float(weight_dim.value), 6.0, places=1)


if __name__ == "__main__":
    unittest.main()
