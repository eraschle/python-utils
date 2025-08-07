"""Tests für die Units Klasse und ihre statischen Methoden."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_analyzer import Unit, UnitType, Units


class TestUnits:
    """Tests für die Units Klasse."""

    def test_one_unit_of(self):
        """Test die one_unit_of statische Methode."""
        # Test für LENGTH
        length_unit = Units.one_unit_of(UnitType.LENGTH)
        assert length_unit.name == "One of unit type 'LENGTH"
        assert length_unit.symbol == "~"
        assert length_unit.unit_type == UnitType.LENGTH
        assert length_unit.base_factor == 1.0

        # Test für MASS
        mass_unit = Units.one_unit_of(UnitType.MASS)
        assert mass_unit.name == "One of unit type 'MASS"
        assert mass_unit.symbol == "~"
        assert mass_unit.unit_type == UnitType.MASS

        # Test für NONE
        none_unit = Units.one_unit_of(UnitType.NONE)
        assert none_unit.symbol == "~"
        assert none_unit.unit_type == UnitType.NONE

    def test_get_units_of(self):
        """Test die get_units_of Klassenmethode."""
        # Test LENGTH units
        length_units = Units.get_units_of(UnitType.LENGTH)
        assert len(length_units) > 0
        assert all(unit.unit_type == UnitType.LENGTH for unit in length_units)

        # Prüfe dass bekannte LENGTH units enthalten sind
        length_symbols = [unit.symbol for unit in length_units]
        assert "mm" in length_symbols
        assert "cm" in length_symbols
        assert "m" in length_symbols
        assert "km" in length_symbols

        # Test AREA units
        area_units = Units.get_units_of(UnitType.AREA)
        assert len(area_units) > 0
        assert all(unit.unit_type == UnitType.AREA for unit in area_units)
        area_symbols = [unit.symbol for unit in area_units]
        assert "m²" in area_symbols

        # Test VOLUME units
        volume_units = Units.get_units_of(UnitType.VOLUME)
        assert len(volume_units) > 0
        assert all(unit.unit_type == UnitType.VOLUME for unit in volume_units)
        volume_symbols = [unit.symbol for unit in volume_units]
        assert "l" in volume_symbols
        assert "m³" in volume_symbols

        # Test für einen Type ohne definierte Units (falls vorhanden)
        currency_units = Units.get_units_of(UnitType.CURRENCY)
        assert currency_units == []  # Keine Currency units definiert

    def test_get_all_units(self):
        """Test die get_all_units Klassenmethode."""
        all_units = Units.get_all_units()

        assert len(all_units) > 0
        assert all(isinstance(unit, Unit) for unit in all_units)

        # Prüfe dass verschiedene Unit-Typen enthalten sind
        unit_types = set(unit.unit_type for unit in all_units)
        assert UnitType.LENGTH in unit_types
        assert UnitType.AREA in unit_types
        assert UnitType.VOLUME in unit_types
        assert UnitType.MASS in unit_types
        assert UnitType.TIME in unit_types
        assert UnitType.NONE in unit_types
        assert UnitType.UNKNOWN in unit_types

        # Prüfe dass spezifische Units enthalten sind
        symbols = [unit.symbol for unit in all_units]
        assert "mm" in symbols
        assert "kg" in symbols
        assert "l" in symbols
        assert "°C" in symbols

    def test_get_convertable_units(self):
        """Test die get_convertable_units Klassenmethode."""
        convertable = Units.get_convertable_units()

        assert len(convertable) > 0
        assert all(unit.is_convertable for unit in convertable)

        # Prüfe dass NONE und UNKNOWN nicht enthalten sind
        symbols = [unit.symbol for unit in convertable]
        assert "" not in symbols  # NONE hat leeres Symbol
        assert "?" not in symbols  # UNKNOWN hat ? als Symbol

        # Prüfe dass Quantity units nicht enthalten sind
        for unit in convertable:
            assert unit.unit_type != UnitType.QUANTITY

    def test_get_unit_by(self):
        """Test die get_unit_by Klassenmethode."""
        # Test mit vollständigem Namen
        mm_unit = Units.get_unit_by("length (mm)")
        assert mm_unit is not None
        assert mm_unit.symbol == "mm"
        assert mm_unit.unit_type == UnitType.LENGTH

        # Test mit anderem vollständigen Namen
        kg_unit = Units.get_unit_by("mass (kg)")
        assert kg_unit is not None
        assert kg_unit.symbol == "kg"
        assert kg_unit.unit_type == UnitType.MASS

        # Test mit NONE
        none_unit = Units.get_unit_by("none")
        assert none_unit is not None
        assert none_unit.symbol == ""
        assert none_unit.unit_type == UnitType.NONE

        # Test mit ungültigem Namen
        invalid_unit = Units.get_unit_by("invalid_unit_name")
        assert invalid_unit is None

        # Test mit one_unit_of pattern
        length_unit = Units.get_unit_by("length (~)")
        assert length_unit is not None
        assert length_unit.symbol == "~"
        assert length_unit.unit_type == UnitType.LENGTH

    def test_predefined_units_count(self):
        """Test dass eine angemessene Anzahl von Units definiert ist."""
        all_units = Units.get_all_units()
        # Sollte mindestens 30 Units haben (basierend auf dem Code)
        assert len(all_units) >= 30

    def test_unit_types_coverage(self):
        """Test dass Units für verschiedene UnitTypes definiert sind."""
        all_units = Units.get_all_units()
        covered_types = set(unit.unit_type for unit in all_units)

        expected_types = {
            UnitType.NONE,
            UnitType.UNKNOWN,
            UnitType.LENGTH,
            UnitType.AREA,
            UnitType.VOLUME,
            UnitType.MASS,
            UnitType.TIME,
            UnitType.QUANTITY,
            UnitType.PRESSURE,
            UnitType.TEMPERATURE,
            UnitType.VOLTAGE,
            UnitType.CURRENT,
            UnitType.POWER,
            UnitType.ENERGY,
            UnitType.VELOCITY,
            UnitType.FLOW_RATE,
            UnitType.ANGLE,
        }

        for expected_type in expected_types:
            assert expected_type in covered_types, f"Missing units for {expected_type}"

    def test_base_factors_consistency(self):
        """Test dass base_factors innerhalb eines UnitTypes konsistent sind."""
        # Test LENGTH units - Meter ist Basis (1.0)
        length_units = Units.get_units_of(UnitType.LENGTH)
        meter = next((u for u in length_units if u.symbol == "m"), None)
        assert meter is not None
        assert meter.base_factor == 1.0

        mm = next((u for u in length_units if u.symbol == "mm"), None)
        assert mm is not None
        assert mm.base_factor == 0.001

        km = next((u for u in length_units if u.symbol == "km"), None)
        assert km is not None
        assert km.base_factor == 1000.0

        # Test MASS units - Kilogramm ist Basis (1.0)
        mass_units = Units.get_units_of(UnitType.MASS)
        kg = next((u for u in mass_units if u.symbol == "kg"), None)
        assert kg is not None
        assert kg.base_factor == 1.0

        g = next((u for u in mass_units if u.symbol == "g"), None)
        assert g is not None
        assert g.base_factor == 0.001
