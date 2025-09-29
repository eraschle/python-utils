"""Tests für die Unit Klasse."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_analyzer import Unit, UnitType, Units


class TestUnit:
    """Tests für die Unit Dataclass."""

    def test_unit_creation(self):
        """Test dass Units korrekt erstellt werden."""
        unit = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
        assert unit.name == "Millimeter"
        assert unit.symbol == "mm"
        assert unit.unit_type == UnitType.LENGTH
        assert unit.base_factor == 0.001

    def test_unit_default_base_factor(self):
        """Test dass base_factor standardmäßig 1.0 ist."""
        unit = Unit("Test Unit", "tu", UnitType.LENGTH)
        assert unit.base_factor == 1.0

    def test_unit_is_convertable_property(self):
        """Test die is_convertable Property."""
        # Konvertierbare Einheiten
        mm = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
        assert mm.is_convertable is True

        kg = Unit("Kilogramm", "kg", UnitType.MASS, 1.0)
        assert kg.is_convertable is True

        # Nicht konvertierbare Einheiten
        none_unit = Unit("None", "", UnitType.NONE, 1.0)
        assert none_unit.is_convertable is False

        unknown_unit = Unit("Unknown", "?", UnitType.UNKNOWN, 1.0)
        assert unknown_unit.is_convertable is False

        quantity_unit = Unit("Pieces", "pcs", UnitType.QUANTITY, 1.0)
        assert quantity_unit.is_convertable is False

    def test_unit_full_name_property(self):
        """Test die full_name Property."""
        # Normale Einheit
        mm = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
        assert mm.full_name == "length (mm)"

        # NONE Einheit
        none_unit = Unit("None", "", UnitType.NONE, 1.0)
        assert none_unit.full_name == "none"

    def test_unit_str_method(self):
        """Test die __str__ Methode."""
        mm = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
        assert str(mm) == "length (mm)"

        none_unit = Unit("None", "", UnitType.NONE, 1.0)
        assert str(none_unit) == "none"

    def test_unit_frozen(self):
        """Test dass Unit frozen ist (unveränderlich)."""
        unit = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
        with pytest.raises(AttributeError):
            unit.name = "Centimeter"  # pyright: ignore[reportAttributeAccessIssue]
        with pytest.raises(AttributeError):
            unit.symbol = "cm"  # pyright: ignore[reportAttributeAccessIssue]
        with pytest.raises(AttributeError):
            unit.unit_type = UnitType.AREA  # pyright: ignore[reportAttributeAccessIssue]
        with pytest.raises(AttributeError):
            unit.base_factor = 0.01  # pyright: ignore[reportAttributeAccessIssue]

    def test_unit_equality(self):
        """Test Gleichheit von Units."""
        unit1 = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
        unit2 = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
        unit3 = Unit("Centimeter", "cm", UnitType.LENGTH, 0.01)

        assert unit1 == unit2
        assert unit1 != unit3

    def test_predefined_units(self):
        """Test einige vordefinierte Units aus der Units Klasse."""
        # Length
        assert Units.MILLIMETER.name == "Millimeter"
        assert Units.MILLIMETER.symbol == "mm"
        assert Units.MILLIMETER.unit_type == UnitType.LENGTH
        assert Units.MILLIMETER.base_factor == 0.001

        assert Units.METER.name == "Meter"
        assert Units.METER.symbol == "m"
        assert Units.METER.unit_type == UnitType.LENGTH
        assert Units.METER.base_factor == 1.0

        # Area
        assert Units.SQUARE_METER.name == "Quadratmeter"
        assert Units.SQUARE_METER.symbol == "m²"
        assert Units.SQUARE_METER.unit_type == UnitType.AREA
        assert Units.SQUARE_METER.base_factor == 1.0

        # Volume
        assert Units.LITER.name == "Liter"
        assert Units.LITER.symbol == "l"
        assert Units.LITER.unit_type == UnitType.VOLUME
        assert Units.LITER.base_factor == 0.001

        # Mass
        assert Units.KILOGRAM.name == "Kilogramm"
        assert Units.KILOGRAM.symbol == "kg"
        assert Units.KILOGRAM.unit_type == UnitType.MASS
        assert Units.KILOGRAM.base_factor == 1.0

        # Temperature
        assert Units.CELSIUS.name == "Grad Celsius"
        assert Units.CELSIUS.symbol == "°C"
        assert Units.CELSIUS.unit_type == UnitType.TEMPERATURE

        # Special units
        assert Units.NONE.name == "None"
        assert Units.NONE.symbol == ""
        assert Units.NONE.unit_type == UnitType.NONE
        assert Units.NONE.is_convertable is False

        assert Units.UNKNOWN.name == "Unknown"
        assert Units.UNKNOWN.symbol == "?"
        assert Units.UNKNOWN.unit_type == UnitType.UNKNOWN
        assert Units.UNKNOWN.is_convertable is False
