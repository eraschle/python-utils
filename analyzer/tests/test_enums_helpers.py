"""Tests für Enums und Hilfsfunktionen."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_analyzer import (
    DataType,
    UnitType,
    get_data_type_by,
    get_unit_type_by,
    is_unit_type_convertable,
)


class TestUnitTypeEnum:
    """Tests für UnitType Enum."""

    def test_unit_type_values(self):
        """Test dass alle UnitType Werte korrekt definiert sind."""
        assert UnitType.NONE.value == "none"
        assert UnitType.UNKNOWN.value == "unknown"
        assert UnitType.LENGTH.value == "length"
        assert UnitType.AREA.value == "area"
        assert UnitType.VOLUME.value == "volume"
        assert UnitType.MASS.value == "mass"
        assert UnitType.CURRENCY.value == "currency"
        assert UnitType.QUANTITY.value == "quantity"
        assert UnitType.TIME.value == "time"
        assert UnitType.PRESSURE.value == "pressure"
        assert UnitType.TEMPERATURE.value == "temperature"
        assert UnitType.VOLTAGE.value == "voltage"
        assert UnitType.CURRENT.value == "current"
        assert UnitType.POWER.value == "power"
        assert UnitType.ENERGY.value == "energy"
        assert UnitType.VELOCITY.value == "velocity"
        assert UnitType.FLOW_RATE.value == "flow_rate"
        assert UnitType.ANGLE.value == "angle"
        assert UnitType.ROTATION.value == "rotation"

    def test_unit_type_count(self):
        """Test dass alle erwarteten UnitTypes vorhanden sind."""
        unit_types = list(UnitType)
        assert len(unit_types) == 19


class TestDataTypeEnum:
    """Tests für DataType Enum."""

    def test_data_type_values(self):
        """Test dass alle DataType Werte korrekt definiert sind."""
        assert DataType.UNKNOWN.value == "unknown"
        assert DataType.STRING.value == "string"
        assert DataType.INTEGER.value == "integer"
        assert DataType.FLOAT.value == "float"
        assert DataType.BOOLEAN.value == "boolean"

    def test_data_type_count(self):
        """Test dass alle erwarteten DataTypes vorhanden sind."""
        data_types = list(DataType)
        assert len(data_types) == 5


class TestIsUnitTypeConvertable:
    """Tests für is_unit_type_convertable Funktion."""

    def test_non_convertable_types(self):
        """Test dass NONE und UNKNOWN nicht konvertierbar sind."""
        assert is_unit_type_convertable(UnitType.NONE) is False
        assert is_unit_type_convertable(UnitType.UNKNOWN) is False

    def test_convertable_types(self):
        """Test dass alle anderen UnitTypes konvertierbar sind."""
        convertable_types = [
            UnitType.LENGTH,
            UnitType.AREA,
            UnitType.VOLUME,
            UnitType.MASS,
            UnitType.CURRENCY,
            UnitType.QUANTITY,
            UnitType.TIME,
            UnitType.PRESSURE,
            UnitType.TEMPERATURE,
            UnitType.VOLTAGE,
            UnitType.CURRENT,
            UnitType.POWER,
            UnitType.ENERGY,
            UnitType.VELOCITY,
            UnitType.FLOW_RATE,
            UnitType.ANGLE,
            UnitType.ROTATION,
        ]
        for unit_type in convertable_types:
            assert is_unit_type_convertable(unit_type) is True


class TestGetUnitTypeBy:
    """Tests für get_unit_type_by Funktion."""

    def test_valid_unit_type_values(self):
        """Test dass gültige Werte korrekt zugeordnet werden."""
        assert get_unit_type_by("none") == UnitType.NONE
        assert get_unit_type_by("unknown") == UnitType.UNKNOWN
        assert get_unit_type_by("length") == UnitType.LENGTH
        assert get_unit_type_by("area") == UnitType.AREA
        assert get_unit_type_by("volume") == UnitType.VOLUME
        assert get_unit_type_by("mass") == UnitType.MASS
        assert get_unit_type_by("currency") == UnitType.CURRENCY
        assert get_unit_type_by("quantity") == UnitType.QUANTITY
        assert get_unit_type_by("time") == UnitType.TIME
        assert get_unit_type_by("pressure") == UnitType.PRESSURE
        assert get_unit_type_by("temperature") == UnitType.TEMPERATURE
        assert get_unit_type_by("voltage") == UnitType.VOLTAGE
        assert get_unit_type_by("current") == UnitType.CURRENT
        assert get_unit_type_by("power") == UnitType.POWER
        assert get_unit_type_by("energy") == UnitType.ENERGY
        assert get_unit_type_by("velocity") == UnitType.VELOCITY
        assert get_unit_type_by("flow_rate") == UnitType.FLOW_RATE
        assert get_unit_type_by("angle") == UnitType.ANGLE
        assert get_unit_type_by("rotation") == UnitType.ROTATION

    def test_invalid_unit_type_values(self):
        """Test dass ungültige Werte UNKNOWN zurückgeben."""
        assert get_unit_type_by("invalid") == UnitType.UNKNOWN
        assert get_unit_type_by("") == UnitType.UNKNOWN
        assert get_unit_type_by("LENGTH") == UnitType.UNKNOWN  # Case-sensitive
        assert get_unit_type_by("123") == UnitType.UNKNOWN

    def test_none_value(self):
        """Test dass None UNKNOWN zurückgibt."""
        assert get_unit_type_by(None) == UnitType.UNKNOWN


class TestGetDataTypeBy:
    """Tests für get_data_type_by Funktion."""

    def test_valid_data_type_values(self):
        """Test dass gültige Werte korrekt zugeordnet werden."""
        assert get_data_type_by("unknown") == DataType.UNKNOWN
        assert get_data_type_by("string") == DataType.STRING
        assert get_data_type_by("integer") == DataType.INTEGER
        assert get_data_type_by("float") == DataType.FLOAT
        assert get_data_type_by("boolean") == DataType.BOOLEAN

    def test_invalid_data_type_values(self):
        """Test dass ungültige Werte UNKNOWN zurückgeben."""
        assert get_data_type_by("invalid") == DataType.UNKNOWN
        assert get_data_type_by("") == DataType.UNKNOWN
        assert get_data_type_by("STRING") == DataType.UNKNOWN  # Case-sensitive
        assert get_data_type_by("123") == DataType.UNKNOWN

    def test_none_value(self):
        """Test dass None UNKNOWN zurückgibt."""
        assert get_data_type_by(None) == DataType.UNKNOWN
