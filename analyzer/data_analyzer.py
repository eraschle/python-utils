#!/usr/bin/env python3
"""
DataFrame Analyzer
============================

Script for analyzing data structures and automatic detection
of data types and units. Optimized for performance with vectorized operations.

Supports:
- pandas DataFrames
- Lists of dictionaries
- Lists of lists

/// script
dependencies = [
    "pandas>=2.0.0",
    "pyyaml>=6.0",
]
///
"""

import argparse
import json
import logging
import re
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar, NotRequired, Self, TypedDict

import pandas as pd
import yaml

# Configure logging
log = logging.getLogger(__name__)
if not log.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.WARNING)


class UnitType(Enum):
    NONE = "none"  # Keine Einheit
    UNKNOWN = "unknown"  # Unbekannte Einheit
    LENGTH = "length"  # Laenge (mm, cm, m, km)
    AREA = "area"  # Flaeche (mm², cm², m²)
    VOLUME = "volume"  # Volumen (mm³, cm³, m³, l)
    MASS = "mass"  # Masse/Gewicht (g, kg, t)
    CURRENCY = "currency"  # Waehrung (Euro, Dollar, etc.)
    QUANTITY = "quantity"  # Anzahl/Stueckzahl (Stk, Pieces)
    TIME = "time"  # Zeit (s, min, h)
    PRESSURE = "pressure"  # Druck (Pa, bar, psi)
    TEMPERATURE = "temperature"  # Temperatur (°C, °F, K)
    VOLTAGE = "voltage"  # Spannung (V, kV)
    CURRENT = "current"  # Strom (A, mA)
    POWER = "power"  # Leistung (W, kW)
    ENERGY = "energy"  # Energie (kWh, J)
    VELOCITY = "velocity"  # Geschwindigkeit (m/s, km/h)
    FLOW_RATE = "flow_rate"  # Durchfluss (l/s, m³/h)
    ANGLE = "angle"  # Winkel (°, rad)
    ROTATION = "rotation"  # Drehzahl (rpm, rps)


def is_unit_type_convertable(unit_type: UnitType) -> bool:
    """Check if a unit type can be converted.

    Parameters
    ----------
    unit_type : UnitType
        The unit type to check.

    Returns
    -------
    bool
        True if the unit type is convertable, False otherwise.
    """
    return unit_type not in (UnitType.NONE, UnitType.UNKNOWN)


def get_unit_type_by(value: str | None) -> UnitType:
    """Get unit type by its string value.

    Parameters
    ----------
    value : str or None
        String value to look up.

    Returns
    -------
    UnitType
        Corresponding UnitType or UnitType.UNKNOWN if not found.
    """
    if value is None:
        return UnitType.UNKNOWN
    for unit_type in UnitType:
        if value != unit_type.value:
            continue
        return unit_type
    return UnitType.UNKNOWN


class DataType(Enum):
    UNKNOWN = "unknown"
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


def get_data_type_by(value: str | None) -> DataType:
    """Get data type by its string value.

    Parameters
    ----------
    value : str or None
        String value to look up.

    Returns
    -------
    DataType
        Corresponding DataType or DataType.UNKNOWN if not found.
    """
    if value is None:
        return DataType.UNKNOWN
    for data_type in DataType:
        if value != data_type.value:
            continue
        return data_type
    return DataType.UNKNOWN


@dataclass(frozen=True)
class Unit:
    """Represents a physical unit with conversion capabilities.

    This class defines a unit of measurement with its name, symbol, type,
    and conversion factor to a base unit within its unit type.

    Parameters
    ----------
    name : str
        Full name of the unit (e.g., "Millimeter").
    symbol : str
        Short symbol representation (e.g., "mm").
    unit_type : UnitType
        Category of the unit (e.g., UnitType.LENGTH).
    base_factor : float, default 1.0
        Conversion factor to the base unit of this type.

    Examples
    --------
    >>> mm = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
    >>> print(mm.convertable)  # True
    >>> print(str(mm))  # "mm"
    """

    name: str = field(compare=False)
    symbol: str = field(compare=True)
    unit_type: UnitType = field(compare=True)
    base_factor: float = field(default=1.0, compare=False)
    convert_func: Callable[[float], float] = field(default=None, compare=False)

    @property
    def is_unknown(self) -> bool:
        """Check if this unit is unknown.

        Returns
        -------
        bool
            True if the unit is UNKNOWN.
        """
        return self == Units.UNKNOWN

    @property
    def is_none_unit_type(self) -> bool:
        """Check if this unit is of UnitType.NONE.

        Returns
        -------
        bool
            True if the unit has UnitType.NONE.
        """
        return self.unit_type == UnitType.NONE

    @property
    def is_convertable(self) -> bool:
        """Check if this unit can be converted to other units.

        Returns
        -------
        bool
            True if the unit can be converted (not NONE, UNKNOWN, or QUANTITY).
        """
        if self.is_unknown or self.is_none_unit_type:
            return False
        return self.unit_type not in (UnitType.QUANTITY,)

    @property
    def is_any_unit_type(self) -> bool:
        """Check if this unit is a generic placeholder for its unit type.

        Returns
        -------
        bool
            True if this unit represents any unit of its type (placeholder unit).
        """
        if not self.is_convertable:
            return False
        one_of_type = Units.one_unit_of(self.unit_type)
        return one_of_type == self

    @property
    def full_name(self) -> str:
        """Get the full name of the unit with type.

        Returns
        -------
        str
            Full name like "length (mm)" or just type value for NONE units.
        """
        if self.unit_type == UnitType.NONE:
            return self.unit_type.value
        return f"{self.unit_type.value} ({self.symbol})"

    def convert_to(self, value: float, to_unit: Self) -> float:
        """Convert a value from this unit to another unit.

        Parameters
        ----------
        value : float
            The value to convert.
        to_unit : Unit
            The target unit to convert to.

        Returns
        -------
        float
            The converted value, or original value if conversion not possible.
        """
        if not self.is_convertable or self.unit_type != to_unit.unit_type:
            return value
        if self.convert_func:
            return self.convert_func(value)
        return value * self.base_factor / to_unit.base_factor

    def __str__(self) -> str:
        return self.full_name


class Units:
    """Collection of predefined units and utility methods.

    This class provides a comprehensive set of predefined units and methods
    to work with them. All units are defined as class attributes and can be
    accessed directly or through utility methods.

    Examples
    --------
    >>> Units.MILLIMETER
    Unit(name='Millimeter', symbol='mm', unit_type=<UnitType.LENGTH: 'length'>, base_factor=0.001)

    >>> length_units = Units.get_units_of(UnitType.LENGTH)
    >>> len(length_units)  # Number of length units

    >>> all_units = Units.get_all_units()
    >>> convertable = Units.get_convertable_units()
    """

    @staticmethod
    def one_unit_of(unit_type: UnitType) -> Unit:
        """Create a placeholder unit for a specific unit type.

        This method creates a generic unit that represents "one unit of the given type"
        without specifying the exact unit. Useful for pattern matching when the
        specific unit is not known but the type is clear.

        Parameters
        ----------
        unit_type : UnitType
            The type of unit to create a placeholder for.

        Returns
        -------
        Unit
            A placeholder unit with symbol "~" representing the unit type.

        Examples
        --------
        >>> length_unit = Units.one_unit_of(UnitType.LENGTH)
        >>> print(length_unit.symbol)  # "~"
        >>> print(length_unit.unit_type)  # UnitType.LENGTH
        """
        return Unit(f"One of unit type '{unit_type.value.upper()}", "~", unit_type)

    @classmethod
    def get_units_of(cls, unit_type: UnitType) -> list[Unit]:
        """Get all units of a specific type.

        Parameters
        ----------
        unit_type : UnitType
            The unit type to filter by.

        Returns
        -------
        list[Unit]
            List of all units matching the specified type.

        Examples
        --------
        >>> length_units = Units.get_units_of(UnitType.LENGTH)
        >>> pressure_units = Units.get_units_of(UnitType.PRESSURE)
        """
        return [unit for unit in cls.get_all_units() if unit.unit_type == unit_type]

    @classmethod
    def get_all_units(cls) -> list[Unit]:
        """Get all predefined units from this class.

        Returns
        -------
        list[Unit]
            List of all Unit instances defined as class attributes.

        Examples
        --------
        >>> all_units = Units.get_all_units()
        >>> print(f"Total units available: {len(all_units)}")
        """
        all_units = []
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            unit = getattr(cls, attr_name)
            if not isinstance(unit, Unit):
                continue
            all_units.append(unit)
        return all_units

    @classmethod
    def get_convertable_units(cls) -> list[Unit]:
        """Get all units that can be converted to other units.

        Excludes NONE and UNKNOWN units which cannot be converted.

        Returns
        -------
        list[Unit]
            List of all convertable units.

        Examples
        --------
        >>> convertable = Units.get_convertable_units()
        >>> non_convertable = [u for u in Units.get_all_units() if not u.convertable]
        """
        return [unit for unit in cls.get_all_units() if unit.is_convertable]

    @classmethod
    def get_unit_by(cls, full_name: str) -> Unit | None:
        """Get a unit by its full name.

        Parameters
        ----------
        full_name : str
            The full name of the unit to search for.

        Returns
        -------
        Unit or None
            The unit with matching full name, or None if not found.

        Examples
        --------
        >>> unit = Units.get_unit_by("length (mm)")
        >>> print(unit.symbol)  # "mm"
        """
        for unit in cls.get_all_units():
            if unit.full_name != full_name:
                continue
            return unit
        unit_type_name = full_name.split()[0]
        unit_type = get_unit_type_by(unit_type_name)
        one_of_unit = cls.one_unit_of(unit_type)
        if one_of_unit.full_name != full_name:
            return None
        return one_of_unit

    NONE = Unit("None", "", UnitType.NONE, 1.0)
    UNKNOWN = Unit("Unknown", "?", UnitType.UNKNOWN, 1.0)

    # Length units
    MILLIMETER = Unit("Millimeter", "mm", UnitType.LENGTH, 0.001)
    CENTIMETER = Unit("Centimeter", "cm", UnitType.LENGTH, 0.01)
    METER = Unit("Meter", "m", UnitType.LENGTH, 1.0)
    KILOMETER = Unit("Kilometer", "km", UnitType.LENGTH, 1000.0)

    # Area units
    SQUARE_MILLIMETER = Unit("Quadratmillimeter", "mm²", UnitType.AREA, 0.000001)
    SQUARE_CENTIMETER = Unit("Quadratzentimeter", "cm²", UnitType.AREA, 0.0001)
    SQUARE_METER = Unit("Quadratmeter", "m²", UnitType.AREA, 1.0)

    # Volumen
    CUBIC_MILLIMETER = Unit("Kubikmillimeter", "mm³", UnitType.VOLUME, 0.000000001)
    CUBIC_CENTIMETER = Unit("Kubikzentimeter", "cm³", UnitType.VOLUME, 0.000001)
    CUBIC_METER = Unit("Kubikmeter", "m³", UnitType.VOLUME, 1.0)
    LITER = Unit("Liter", "l", UnitType.VOLUME, 0.001)

    # Mass units
    GRAM = Unit("Gramm", "g", UnitType.MASS, 0.001)
    KILOGRAM = Unit("Kilogramm", "kg", UnitType.MASS, 1.0)
    TON = Unit("Tonne", "t", UnitType.MASS, 1000.0)

    # Time units
    SECOND = Unit("Sekunde", "s", UnitType.TIME, 1.0)
    MINUTE = Unit("Minute", "min", UnitType.TIME, 60.0)
    HOUR = Unit("Stunde", "h", UnitType.TIME, 3600.0)

    # Quantity units
    PIECE = Unit("Stück", "Stk", UnitType.QUANTITY, 1.0)

    # Pressure units
    PASCAL = Unit("Pascal", "Pa", UnitType.PRESSURE, 1.0)
    KILOPASCAL = Unit("Kilopascal", "kPa", UnitType.PRESSURE, 1000.0)
    MEGAPASCAL = Unit("Megapascal", "MPa", UnitType.PRESSURE, 1000000.0)
    BAR = Unit("Bar", "bar", UnitType.PRESSURE, 100000.0)
    PSI = Unit("Pounds per square inch", "psi", UnitType.PRESSURE, 6894.76)

    # Temperature units
    CELSIUS = Unit("Grad Celsius", "°C", UnitType.TEMPERATURE, 1.0, lambda value: value + 273)
    KELVIN = Unit("Kelvin", "K", UnitType.TEMPERATURE, 1.0, lambda value: value - 273)

    # Electrical units
    VOLT = Unit("Volt", "V", UnitType.VOLTAGE, 1.0)
    KILOVOLT = Unit("Kilovolt", "kV", UnitType.VOLTAGE, 1000.0)
    AMPERE = Unit("Ampere", "A", UnitType.CURRENT, 1.0)
    MILLIAMPERE = Unit("Milliampere", "mA", UnitType.CURRENT, 0.001)
    WATT = Unit("Watt", "W", UnitType.POWER, 1.0)
    KILOWATT = Unit("Kilowatt", "kW", UnitType.POWER, 1000.0)
    KILOWATT_HOUR = Unit("Kilowattstunde", "kWh", UnitType.ENERGY, 3600000.0)

    # Velocity units
    METER_PER_SECOND = Unit("Meter pro Sekunde", "m/s", UnitType.VELOCITY, 1.0)
    KILOMETER_PER_HOUR = Unit("Kilometer pro Stunde", "km/h", UnitType.VELOCITY, 0.277778)
    MILES_PER_HOUR = Unit("Miles per hour", "mph", UnitType.VELOCITY, 0.44704)

    # Flow rate units
    LITER_PER_SECOND = Unit("Liter pro Sekunde", "l/s", UnitType.FLOW_RATE, 0.001)
    LITER_PER_MINUTE = Unit("Liter pro Minute", "l/min", UnitType.FLOW_RATE, 0.0000167)
    CUBIC_METER_PER_HOUR = Unit("Kubikmeter pro Stunde", "m³/h", UnitType.FLOW_RATE, 0.000278)

    # Winkel
    DEGREE = Unit("Grad", "°", UnitType.ANGLE, 1.0)
    RADIAN = Unit("Radiant", "rad", UnitType.ANGLE, 57.2958)


class PatternDict(TypedDict):
    pattern: str
    data_type: str
    unit: NotRequired[str]


class ClassifierDict(TypedDict):
    name: str
    priority: int
    patterns: list[PatternDict]


@dataclass
class Configuration:
    merge_with_default: bool
    direct_mappings: dict[str, str]  # value to Unit.full_name
    context_mappings: dict[str, str]  # value to UnitType.value
    classifiers: dict[str, ClassifierDict]


@dataclass
class DataTypeUnit:
    """Result of unit extraction with detailed metrics.

    Provides comprehensive metrics about data convertibility and quality.
    """

    data_type: DataType
    unit: Unit
    confidence: float
    classifier_name: str
    total_values: int = 0  # Anzahl Werte ohne None/NaN
    null_count: int = 0  # Anzahl None/NaN Werte
    non_convertible_count: int = 0  # Anzahl nicht konvertierbare Werte (von total_values)

    @property
    def total_count(self) -> int:
        """Gesamtanzahl aller Werte inklusive None/NaN."""
        return self.total_values + self.null_count

    @property
    def convertible_count(self) -> int:
        """Anzahl der erfolgreich konvertierbaren Werte."""
        return self.total_values - self.non_convertible_count

    @property
    def convertible_percentage(self) -> float:
        """Prozentsatz der konvertierbaren Werte (ohne None/NaN)."""
        if self.total_values == 0:
            return 0.0
        return (self.convertible_count / self.total_values) * 100

    @property
    def null_percentage(self) -> float:
        """Prozentsatz der None/NaN Werte vom Gesamtdatensatz."""
        if self.total_count == 0:
            return 0.0
        return (self.null_count / self.total_count) * 100

    @property
    def data_quality_score(self) -> float:
        """Qualitätsscore basierend auf Konvertierbarkeit und Vollständigkeit (0-1)."""
        if self.total_count == 0:
            return 0.0
        # Kombination aus Vollständigkeit und Konvertierbarkeit
        completeness = self.total_values / self.total_count  # Anteil nicht-null Werte
        if self.total_values == 0:
            convertibility = 0.0
        else:
            convertibility = self.convertible_count / self.total_values
        # Gewichteter Score: 40% Vollständigkeit, 60% Konvertierbarkeit
        return (completeness * 0.4) + (convertibility * 0.6)


@dataclass(slots=True)
class PatternMatch:
    pattern: str
    compiled_pattern: re.Pattern = field(init=False)
    data_type: DataType
    unit: Unit = Units.NONE
    unit_type: UnitType = UnitType.NONE

    def __post_init__(self):
        self.compiled_pattern = re.compile(self.pattern, re.IGNORECASE)
        if self.unit == Units.NONE and self.unit_type not in (
            UnitType.NONE,
            UnitType.UNKNOWN,
        ):
            self.unit = Units.one_unit_of(self.unit_type)

    def to_dict(self) -> PatternDict:
        if not self.unit.is_convertable:
            return {
                "pattern": self.pattern,
                "data_type": self.data_type.value,
            }
        return {
            "pattern": self.pattern,
            "data_type": self.data_type.value,
            "unit": self.unit.full_name,
        }


class UnitExtractor:
    """Extract units from column names without iterating over values.

    This class provides efficient unit extraction from column names using
    pattern matching and predefined mappings.

    Attributes
    ----------
    direct_mappings : dict[str, Unit]
        Direct mappings from string keys to Unit objects.
    context_mappings : dict[str, UnitType]
        Context-based mappings from string keys to UnitType objects.
    """

    def __init__(self):
        self.direct_mappings: dict[str, Unit] = {}
        self.context_mappings: dict[str, UnitType] = {}
        self._load_defaults()
        self.context_cache: dict[str, Unit] = {}
        self._units_cache: dict[str, Unit] = {}

    def clear_cache(self):
        """Clear the internal units cache."""
        self._units_cache.clear()

    def _load_defaults(self):
        """Load default mappings from code."""
        self._add_all_unit_symbols()
        self._add_manual_mappings()
        self._add_default_context_mappings()

    def _add_all_unit_symbols(self):
        """Add all unit symbols from Units class automatically."""
        for unit in Units.get_all_units():
            symbol_key = unit.symbol.lower().strip()
            if not self.is_valid_unit_symbol(symbol_key):
                continue
            self.direct_mappings[symbol_key] = unit

    def is_valid_unit_symbol(self, symbol_key: str) -> bool:
        """Check if a unit symbol is valid and unambiguous.

        Parameters
        ----------
        symbol_key : str
            The unit symbol to validate.

        Returns
        -------
        bool
            True if the symbol is valid and unambiguous, False otherwise.
        """
        # Exclude empty or problematic symbols
        if symbol_key in ["", "?", "~"]:
            return False

        # Exclude ambiguous single characters
        ambiguous_single_chars = ["a", "k", "m", "g", "h", "s"]
        return symbol_key not in ambiguous_single_chars

    def _load_direct_mapping(self, config: Configuration):
        """Load configuration and update direct mappings"""
        if not config.merge_with_default:
            self.direct_mappings.clear()

        mappings = {}
        for value, unit_name in config.direct_mappings.items():
            unit = Units.get_unit_by(unit_name)
            if not unit:
                continue
            mappings[value] = unit
        self.direct_mappings.update(mappings)

    def _load_context_mapping(self, config: Configuration):
        """Load configuration and update context mappings"""
        if not config.merge_with_default:
            self.context_mappings.clear()

        mappings = {}
        for value, unit_type_name in config.context_mappings.items():
            unit_type = get_unit_type_by(unit_type_name)
            if not unit_type:
                continue
            mappings[value] = unit_type
        self.context_mappings.update(mappings)

    def load_configuration(self, config: Configuration):
        """Update mappings from given configuration

        Parameters
        ----------
        config : Configuration
            Configuration object containing classifier and unit settings.
        """
        self._load_direct_mapping(config)
        self._load_context_mapping(config)

    def _add_manual_mappings(self):
        """Add additional manual mappings."""
        manual_mappings = {
            # Length units
            "millimeter": Units.MILLIMETER,
            "centimeter": Units.CENTIMETER,
            "meter": Units.METER,
            "kilometer": Units.KILOMETER,
            # Area units
            "mm2": Units.SQUARE_MILLIMETER,
            "cm2": Units.SQUARE_CENTIMETER,
            "m2": Units.SQUARE_METER,
            # Volume units
            "mm3": Units.CUBIC_MILLIMETER,
            "cm3": Units.CUBIC_CENTIMETER,
            "m3": Units.CUBIC_METER,
            "liter": Units.LITER,
            # Mass units
            "gramm": Units.GRAM,
            "kilogramm": Units.KILOGRAM,
            "tonne": Units.TON,
            # Time units
            "sekunde": Units.SECOND,
            "minute": Units.MINUTE,
            "stunde": Units.HOUR,
            # Quantity units
            "stück": Units.PIECE,
            "pieces": Units.PIECE,
            "pcs": Units.PIECE,
            "count": Units.PIECE,
            # Pressure units
            "pascal": Units.PASCAL,
            "kilopascal": Units.KILOPASCAL,
            "megapascal": Units.MEGAPASCAL,
            # Temperature units
            "celsius": Units.CELSIUS,
            "kelvin": Units.KELVIN,
            # Electrical units
            "volt": Units.VOLT,
            "kilovolt": Units.KILOVOLT,
            "ampere": Units.AMPERE,
            "milliampere": Units.MILLIAMPERE,
            "watt": Units.WATT,
            "kilowatt": Units.KILOWATT,
            "kilowattstunde": Units.KILOWATT_HOUR,
            # Flow rate units
            "m3/h": Units.CUBIC_METER_PER_HOUR,
            # Angle units
            "grad": Units.DEGREE,
            "degree": Units.DEGREE,
            "radiant": Units.RADIAN,
            "radian": Units.RADIAN,
        }
        self.direct_mappings.update(manual_mappings)

    def _add_default_context_mappings(self):
        """Add default context mappings from code."""
        default_context_mappings = {
            "länge": UnitType.LENGTH,
            "length": UnitType.LENGTH,
            "breite": UnitType.LENGTH,
            "width": UnitType.LENGTH,
            "höhe": UnitType.LENGTH,
            "height": UnitType.LENGTH,
            "tiefe": UnitType.LENGTH,
            "depth": UnitType.LENGTH,
            "dicke": UnitType.LENGTH,
            "thickness": UnitType.LENGTH,
            "durchmesser": UnitType.LENGTH,
            "diameter": UnitType.LENGTH,
            "fläche": UnitType.AREA,
            "area": UnitType.AREA,
            "grundfläche": UnitType.AREA,
            "footprint": UnitType.AREA,
            "volumen": UnitType.VOLUME,
            "volume": UnitType.VOLUME,
            "inhalt": UnitType.VOLUME,
            "capacity": UnitType.VOLUME,
            "gewicht": UnitType.MASS,
            "weight": UnitType.MASS,
            "masse": UnitType.MASS,
            "preis": UnitType.CURRENCY,
            "price": UnitType.CURRENCY,
            "kosten": UnitType.CURRENCY,
            "cost": UnitType.CURRENCY,
            "anzahl": UnitType.QUANTITY,
            "count": UnitType.QUANTITY,
            "menge": UnitType.QUANTITY,
            "quantity": UnitType.QUANTITY,
            # Technical units
            "temperatur": UnitType.TEMPERATURE,
            "temperature": UnitType.TEMPERATURE,
            "temp": UnitType.TEMPERATURE,
            "druck": UnitType.PRESSURE,
            "pressure": UnitType.PRESSURE,
            "spannung": UnitType.VOLTAGE,
            "voltage": UnitType.VOLTAGE,
            "strom": UnitType.CURRENT,
            "current": UnitType.CURRENT,
            "leistung": UnitType.POWER,
            "power": UnitType.POWER,
            "energie": UnitType.ENERGY,
            "energy": UnitType.ENERGY,
            "geschwindigkeit": UnitType.VELOCITY,
            "velocity": UnitType.VELOCITY,
            "speed": UnitType.VELOCITY,
            "durchfluss": UnitType.FLOW_RATE,
            "flow": UnitType.FLOW_RATE,
            "flowrate": UnitType.FLOW_RATE,
            "winkel": UnitType.ANGLE,
            "angle": UnitType.ANGLE,
            "rotation": UnitType.ROTATION,
            "drehzahl": UnitType.ROTATION,
        }
        self.context_mappings.update(default_context_mappings)

    def extract_unit(self, column_name: str) -> Unit:
        """Extract unit from column name.

        Parameters
        ----------
        column_name : str
            The column name to analyze for unit information.

        Returns
        -------
        tuple[Unit, UnitType] or None
            Extracted unit and unit type, or None if no unit found.
        """
        if column_name in self._units_cache:
            return self._units_cache[column_name]

        name_lower = column_name.lower()

        # 1. Brackets: "Length (mm)"
        bracket_match = re.search(r"\(([^)]+)\)", name_lower)
        if bracket_match:
            unit_candidate = bracket_match.group(1).strip()
            if unit_candidate in self.direct_mappings:
                unit = self.direct_mappings[unit_candidate]
                self._units_cache[column_name] = unit
                return unit

        # 2. Column name "length_mm" -> "mm"
        if column_name in self.direct_mappings:
            unit = self.direct_mappings[column_name]
            self._units_cache[column_name] = unit
            return unit

        # 3. Suffix: "length_mm" -> "mm"
        for sep in ["_", "-", ".", " "]:
            if sep not in name_lower:
                continue
            parts = name_lower.split(sep)
            if len(parts) < 2:
                continue
            unit_candidate = parts[-1].strip()
            if unit_candidate in self.direct_mappings:
                unit = self.direct_mappings[unit_candidate]
                self._units_cache[column_name] = unit
                return unit

        # 4. Context: "length" -> "m"
        for context, unit_type in self.context_mappings.items():
            if context not in name_lower:
                continue
            unit = Units.one_unit_of(unit_type)
            self._units_cache[column_name] = unit
            return unit

        self._units_cache[column_name] = Units.UNKNOWN
        return Units.UNKNOWN


def _get_unique_type_of(series: pd.Series) -> set[type]:
    serie_types = series.map(type)
    return set(serie_types.unique())


class TypeInference:
    """Vectorized data type inference without loops over individual values.

    This class provides efficient data type detection using pandas vectorized
    operations for optimal performance on large datasets.

    Parameters
    ----------
    boolean_values : set[str], optional
        Set of string values to recognize as boolean. If None, uses default set.
    numeric_threshold : float, default 0.9
        Minimum ratio of successful numeric conversions to classify as numeric.
    """

    default_boolean_values: ClassVar[set[str]] = {
        "true",
        "false",
        "yes",
        "no",
        "ja",
        "nein",
        "1",
        "0",
        "on",
        "off",
        "enabled",
        "disabled",
        "aktiv",
        "inaktiv",
        "checked",
        "unchecked",
        "selected",
        "unselected",
    }

    def __init__(self, boolean_values: set[str] | None = None, numeric_threshold: float = 0.9):
        self.boolean_values = boolean_values or self.default_boolean_values
        self.numeric_threshold = numeric_threshold
        self._data_type_cache: dict[str, DataType] = {}
        self._type_series_cache: dict[str, set[type]] = {}

    def clear_cache(self):
        """Clear all internal caches."""
        self._data_type_cache.clear()
        self._type_series_cache.clear()

    def infer_type(self, column_name: str, series: pd.Series) -> DataType:
        """Infer data type from pandas Series using vectorized operations.

        Uses hierarchical type detection: boolean -> int -> float -> str

        Parameters
        ----------
        series : pd.Series
            The pandas Series to analyze for data type.

        Returns
        -------
        DataType
            The inferred data type.
        """
        if column_name in self._data_type_cache:
            return self._data_type_cache[column_name]

        # Clean up
        clean_series = series.dropna()

        data_type = DataType.UNKNOWN
        if not clean_series.empty:
            # 1. Boolean check
            if self._is_boolean_series(clean_series.copy()):
                # Cache as bool type even though actual data may be strings like "yes"/"no"
                # This represents the logical data type, not the storage type
                self._type_series_cache[column_name] = {bool}
                data_type = DataType.BOOLEAN
            else:
                # 2. Numeric check
                numeric_result = pd.to_numeric(clean_series, errors="coerce")
                if not isinstance(numeric_result, pd.Series):
                    raise TypeError("Numeric conversion failed.")
                clean_numeric = numeric_result.notna()
                success_ratio = clean_numeric.sum() / len(clean_series)
                valid_numerics = numeric_result.dropna()

                unique_types = _get_unique_type_of(valid_numerics)

                # Decide based on success rate
                if success_ratio >= self.numeric_threshold and len(valid_numerics) > 0:
                    # Check if we have nulls in original series
                    has_nulls = series.isna().any()
                    all_integers = valid_numerics.apply(lambda x: x % 1 == 0).all()

                    # Logic:
                    # 1. If float64 dtype WITHOUT nulls → real floats → FLOAT
                    # 2. If any value has decimals → FLOAT
                    # 3. Otherwise (all integers) → INTEGER
                    if not has_nulls and series.dtype == "float64":
                        # Float dtype without nulls means real float values
                        data_type = DataType.FLOAT
                    elif not all_integers:
                        # At least one value has decimals
                        data_type = DataType.FLOAT
                    else:
                        # All values are integers (even if dtype is float64 due to nulls)
                        data_type = DataType.INTEGER

                # 3. String check
                if data_type == DataType.UNKNOWN:
                    unique_types = _get_unique_type_of(clean_series)
                    if len(unique_types) == 1 and str in unique_types:
                        data_type = DataType.STRING

        self._data_type_cache[column_name] = data_type
        return self._data_type_cache[column_name]

    def _is_boolean_series(self, series: pd.Series) -> bool:
        """Vectorized boolean detection without looping over values."""
        str_series = series.astype(str).str.lower().str.strip()
        return bool(str_series.isin(self.boolean_values).all())

    def get_unique_types_of(self, column_name: str, series: pd.Series) -> set[type]:
        """Get unique Python types in a series.

        Parameters
        ----------
        column_name : str
            Name of the column for caching.
        series : pd.Series
            The pandas Series to analyze.

        Returns
        -------
        set[type]
            Set of unique Python types found in the series.
        """
        if column_name not in self._type_series_cache:
            unique_types = _get_unique_type_of(series)
            self._type_series_cache[column_name] = unique_types
        return self._type_series_cache[column_name]


class BaseClassifier(ABC):
    """Base class for all vectorized data classifiers.

    This abstract base class provides the foundation for domain-specific
    data classifiers that can efficiently analyze pandas Series using
    vectorized operations.

    Parameters
    ----------
    name : str
        Name of the classifier.
    priority : int
        Priority level for classifier selection (higher = more priority).
    type_inference : TypeInference
        Type inference engine for data type detection.
    unit_extractor : UnitExtractor
        Unit extraction engine for unit detection.

    Attributes
    ----------
    patterns : list[PatternData]
        List of pattern data objects for classification.
    """

    def __init__(self, name: str, priority: int, type_inference: TypeInference, unit_extractor: UnitExtractor):
        self.name = name
        self.priority = priority
        self.patterns: list[PatternMatch] = []
        self.type_inference = type_inference
        self.unit_extractor = unit_extractor

    def clear_patterns(self):
        """Clear all registered patterns."""
        self.patterns.clear()

    @abstractmethod
    def setup_patterns(self):
        """Setup classification patterns for this classifier.

        This method must be implemented by subclasses.
        """
        pass

    def classify_series(self, column_name: str, series: pd.Series) -> DataTypeUnit:
        """Classify a pandas Series using vectorized operations.

        Parameters
        ----------
        column_name : str
            Name of the column being classified.
        series : pd.Series
            The pandas Series to classify.

        Returns
        -------
        DataTypeUnit
            Classification result with data type, unit, and confidence.
        """
        # 1. Unit extraction (once per column)
        unit = self._extract_unit_from_name(column_name.lower())
        # 2. Type inference (vectorized on entire series)
        data_type = self.type_inference.infer_type(column_name, series)
        if unit.is_unknown and data_type not in (DataType.UNKNOWN,):
            unit = Units.NONE

        # 3. Calculate metrics for convertibility
        null_count = series.isna().sum()
        clean_series = series.dropna()
        total_values = len(clean_series)
        non_convertible_count = 0

        # Count non-convertible values for numeric types
        if data_type in (DataType.INTEGER, DataType.FLOAT) and total_values > 0:
            numeric_result = pd.to_numeric(clean_series, errors="coerce")
            non_convertible_count = numeric_result.isna().sum()

        # 4. Confidence calculation (array-based statistics)
        confidence = self._calculate_confidence(column_name, series, data_type, unit)

        return DataTypeUnit(
            data_type=data_type,
            unit=unit,
            confidence=confidence,
            classifier_name=self.name,
            total_values=total_values,
            null_count=null_count,
            non_convertible_count=non_convertible_count,
        )

    def _extract_with_extractor(self, name: str) -> Unit:
        """Extract unit from name using pattern matching."""
        return self.unit_extractor.extract_unit(name)

    def _extract_with_patterns(self, name: str) -> Unit:
        """Extract unit from name using pattern matching."""
        for pattern in self.patterns:
            if pattern.compiled_pattern.search(name):
                return pattern.unit
        return Units.UNKNOWN

    def _get_by_attr(self, attr: str, *units: Unit) -> list[Unit]:
        return [unit for unit in units if getattr(unit, attr) is True]

    def _check_same_unit_types(self, *units: Unit):
        unit_types = {unit.unit_type for unit in units}
        if len(unit_types) != 1:
            raise ValueError(f"Units have different types: {unit_types}")

    def _extract_unit_from_name(self, name: str) -> Unit:
        """Extract unit from name using pattern matching."""
        ext_unit = self._extract_with_extractor(name)
        pat_unit = self._extract_with_patterns(name)
        if ext_unit is None or pat_unit is None:
            raise ValueError(
                f"SHOULD NOT BE POSSIBLE: One Unit is NONE: Extract: {ext_unit is None} Pattern: {pat_unit is None}"
            )
        if ext_unit == pat_unit:
            return ext_unit
        convertable_units = self._get_by_attr("is_convertable", ext_unit, pat_unit)
        if len(convertable_units) > 0:
            if len(convertable_units) == 1:
                return convertable_units[0]
            # Both are convertable
            self._check_same_unit_types(*convertable_units)
            any_of_units = self._get_by_attr("is_any_unit_type", *convertable_units)
            if len(any_of_units) == 2:
                raise RuntimeError("SHOULD NOT BE POSSIBLE: Both units are any_unit_type, so equals")
            if len(any_of_units) == 1:
                if not ext_unit.is_any_unit_type:
                    return ext_unit
                return pat_unit
            raise NotImplementedError(f"Different symbol of same unit_type. Extract: {ext_unit} Pattern: {pat_unit}")
        without_unit_type = self._get_by_attr("is_none_unit_type", ext_unit, pat_unit)
        if len(without_unit_type) == 2:
            raise RuntimeError(f"Both have no UnitType but are not equals: Extract: {ext_unit} Pattern: {pat_unit}")
        if len(without_unit_type) == 1:
            return without_unit_type[0]

        unknown_units = self._get_by_attr("is_unknown", ext_unit, pat_unit)
        if len(unknown_units) == 1:
            if not ext_unit.is_unknown:
                return ext_unit
            return pat_unit
        return Units.UNKNOWN

    def _calculate_confidence(self, column_name: str, series: pd.Series, data_type: DataType, unit: Unit) -> float:
        """Calculate classification confidence using vectorized operations."""
        confidence = 0.0

        # Pattern match bonus
        name_lower = column_name.lower()
        for pattern in self.patterns:
            if pattern.compiled_pattern.search(name_lower):
                confidence += 0.6
                break

        # Unit bonus
        if unit == Units.one_unit_of(unit.unit_type):
            confidence += 0.2
        elif unit != Units.UNKNOWN:
            confidence += 0.3

        # Data quality: Vectorized operations
        null_ratio = series.isnull().sum() / len(series)
        data_quality = 1 - null_ratio
        confidence += 0.1 * data_quality

        unique_types = self.type_inference.get_unique_types_of(column_name, series)
        type_ratio = 1 / len(unique_types)
        type_confidence = 0.5 * type_ratio

        if data_type == DataType.UNKNOWN:
            confidence -= 0.2

        if data_type == DataType.STRING and str in unique_types:
            confidence += type_confidence

        elif data_type == DataType.INTEGER and int in unique_types:
            confidence += type_confidence

        elif data_type == DataType.FLOAT and float in unique_types:
            confidence += type_confidence

        if confidence < 0:
            confidence = 0.0
        return min(confidence, 1.0)

    def get_name(self) -> str:
        """Get the name of this classifier.

        Returns
        -------
        str
            The classifier name.
        """
        return self.name

    def get_priority(self) -> int:
        """Get the priority of this classifier.

        Returns
        -------
        int
            The classifier priority (higher = more priority).
        """
        return self.priority

    def to_dict(self) -> ClassifierDict:
        """Convert classifier to dictionary representation.

        Returns
        -------
        ClassifierDict
            Dictionary representation of the classifier.
        """
        classifier: ClassifierDict = {
            "name": self.get_name(),
            "priority": self.get_priority(),
            "patterns": [pattern.to_dict() for pattern in self.patterns],
        }
        return classifier


class DefaultClassifier(BaseClassifier):
    """Default data classifier.

    This classifier uses only unit extractor and type_inference.

    Parameters
    ----------
    type_inference : TypeInference
        Type inference engine for data type detection.
    unit_extractor : UnitExtractor
        Unit extraction engine for unit detection.
    """

    def __init__(self, type_inference: TypeInference, unit_extractor: UnitExtractor):
        super().__init__("Default", 0, type_inference, unit_extractor)

    def setup_patterns(self):
        """Setup patterns for the default classifier.

        Default classifier has no patterns, relies only on unit extractor.
        """
        self.patterns = []


class GeneralClassifier(BaseClassifier):
    """General purpose vectorized data classifier.

    This classifier handles common data patterns and serves as a fallback
    for data that doesn't match specialized domain classifiers.

    Parameters
    ----------
    priority : int
        Priority level for this classifier.
    type_inference : TypeInference
        Type inference engine for data type detection.
    unit_extractor : UnitExtractor
        Unit extraction engine for unit detection.
    """

    def __init__(self, priority: int, type_inference: TypeInference, unit_extractor: UnitExtractor):
        super().__init__("General", priority, type_inference, unit_extractor)

    def setup_patterns(self):
        """Setup general classification patterns.

        Defines patterns for common data types like boolean, length, area, etc.
        """
        self.patterns = [
            # Boolean patterns
            PatternMatch(
                pattern=r".*(?:boolean|bool|boolesche).*",
                data_type=DataType.BOOLEAN,
            ),
            PatternMatch(
                pattern=r".*(?:aktiv|active|enabled|on).*",
                data_type=DataType.BOOLEAN,
            ),
            PatternMatch(
                pattern=r".*(?:inaktiv|inactive|disabled|off).*",
                data_type=DataType.BOOLEAN,
            ),
            PatternMatch(
                pattern=r".*(?:sichtbar|visible|shown).*",
                data_type=DataType.BOOLEAN,
            ),
            PatternMatch(
                pattern=r".*(?:verfügbar|available).*",
                data_type=DataType.BOOLEAN,
            ),
            PatternMatch(
                pattern=r".*(?:ist.*|hat.*|besitzt.*)",
                data_type=DataType.BOOLEAN,
            ),
            PatternMatch(
                pattern=r".*(?:length|länge|abstand).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*(?:width|breite).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*(?:depth|tiefe).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*(?:height|höhe).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*(?:diameter|durchmesser).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*(?:thickness|dicke).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*(?:area|fläche).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.AREA,
            ),
            PatternMatch(
                pattern=r".*(?:volume|volumen).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.VOLUME,
            ),
            PatternMatch(
                pattern=r".*(?:weight|gewicht|mass|masse).*",
                data_type=DataType.FLOAT,
                unit_type=UnitType.MASS,
            ),
            PatternMatch(
                pattern=r".*(?:count|anzahl|quantity|menge).*",
                data_type=DataType.INTEGER,
                unit=Units.PIECE,
                unit_type=UnitType.QUANTITY,
            ),
        ]


class ArchitecturalClassifier(BaseClassifier):
    """Specialized classifier for architectural and BIM data.

    This classifier recognizes patterns common in building information
    modeling and architectural datasets.

    Parameters
    ----------
    priority : int
        Priority level for this classifier.
    type_inference : TypeInference
        Type inference engine for data type detection.
    unit_extractor : UnitExtractor
        Unit extraction engine for unit detection.
    """

    def __init__(self, priority: int, type_inference: TypeInference, unit_extractor: UnitExtractor):
        super().__init__("Architectural", priority, type_inference, unit_extractor)

    def setup_patterns(self):
        """Setup architectural domain-specific patterns.

        Defines patterns specific to architectural and BIM data.
        """
        self.patterns = [
            PatternMatch(
                pattern=r".*phase.*",
                data_type=DataType.STRING,
            ),
            PatternMatch(
                pattern=r".*thickness.*",
                data_type=DataType.FLOAT,
                unit=Units.MILLIMETER,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*elevation.*",
                data_type=DataType.FLOAT,
                unit=Units.METER,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*m\.ü\.m.*",
                data_type=DataType.FLOAT,
                unit=Units.METER,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*altitude.*",
                data_type=DataType.FLOAT,
                unit=Units.METER,
                unit_type=UnitType.LENGTH,
            ),
            PatternMatch(
                pattern=r".*material.*",
                data_type=DataType.STRING,
            ),
            PatternMatch(
                pattern=r".*(?:structural|tragend).*",
                data_type=DataType.BOOLEAN,
            ),
            PatternMatch(
                pattern=r".*(?:load.*bearing|lastentragend).*",
                data_type=DataType.BOOLEAN,
            ),
            PatternMatch(
                pattern=r".*(?:fire.*rated|feuerschutz).*",
                data_type=DataType.BOOLEAN,
            ),
        ]


class ConfigurableClassifier(BaseClassifier):
    """Generic classifier created from configuration.

    This classifier is dynamically created from configuration data,
    allowing for custom classification patterns without code changes.

    Parameters
    ----------
    config : ClassifierDict
        Configuration dictionary containing classifier settings.
    type_inference : TypeInference
        Type inference engine for data type detection.
    unit_extractor : UnitExtractor
        Unit extraction engine for unit detection.

    Raises
    ------
    ValueError
        If required configuration fields are missing or invalid.
    """

    def __init__(self, config: ClassifierDict, type_inference: TypeInference, unit_extractor: UnitExtractor):
        if not config["name"] or not config["priority"]:
            raise ValueError(f"Name or Priority is not value: {config}")
        super().__init__(
            name=config["name"],
            priority=config["priority"],
            type_inference=type_inference,
            unit_extractor=unit_extractor,
        )
        self._pattern_configs = config["patterns"]

    def setup_patterns(self):
        """Setup patterns from configuration.

        Creates pattern matches from the configuration data.
        """
        for config in self._pattern_configs:
            pattern = config["pattern"]
            if pattern is None:  # pyright: ignore[reportUnnecessaryComparison]
                raise ValueError(f"Missing pattern in config: {config}")
            data_type = get_data_type_by(config["data_type"])
            unit = Units.get_unit_by(config.get("unit", "none"))
            if unit is None:
                raise ValueError(f"Invalid unit: {config.get('unit', 'none')}")
            self.patterns.append(
                PatternMatch(
                    pattern=pattern,
                    data_type=data_type,
                    unit=unit,
                    unit_type=unit.unit_type,
                )
            )


class ClassifierRegistry:
    """Registry for managing vectorized data classifiers.

    This registry manages available classifiers and provides methods
    to register new ones and retrieve them by priority or name.
    """

    def __init__(self):
        self._classifiers: dict[str, BaseClassifier] = {}

    def register(self, classifier: BaseClassifier):
        """Register a new classifier.

        Parameters
        ----------
        classifier : BaseClassifier
            The classifier to register.
        """
        classifier.setup_patterns()
        self._classifiers[classifier.get_name().lower()] = classifier

    def get_classifiers(
        self, active_classifiers: list[str] | None = None, sorted_by_priority: bool = True
    ) -> list[BaseClassifier]:
        """Get all registered classifiers.

        Parameters
        ----------
        active_classifiers : list[str], optional
            List of classifier names to filter by. If None, returns all classifiers.
        sorted_by_priority : bool, default True
            Whether to sort classifiers by priority (highest first).

        Returns
        -------
        list[BaseClassifier]
            List of registered classifiers.
        """
        classifiers = list(self._classifiers.values())
        if active_classifiers:
            classifiers = [c for c in classifiers if c.get_name() in active_classifiers]
        if sorted_by_priority:
            classifiers.sort(key=lambda c: c.get_priority(), reverse=True)
        return classifiers

    def get_classifier(self, name: str) -> BaseClassifier | None:
        """Get a specific classifier by name.

        Parameters
        ----------
        name : str
            Name of the classifier to retrieve.

        Returns
        -------
        BaseClassifier or None
            The requested classifier, or None if not found.
        """
        classifier = self._classifiers.get(name)
        return classifier

    def clear_classifiers(self):
        """Clear all registered classifiers."""
        self._classifiers.clear()


class DataClassificationEngine:
    """Main classification engine with flexible input handling.

    This engine coordinates multiple classifiers to analyze data efficiently
    using vectorized operations when beneficial. It automatically decides
    between DataFrame and direct processing based on data size and structure.

    Parameters
    ----------
    type_inference : TypeInference, optional
        Type inference engine. If None, creates default instance.
    unit_extractor : UnitExtractor, optional
        Unit extraction engine. If None, creates default instance.
    min_confidence_threshold : float, default 0.7
        Minimum confidence required for classification results.
    small_data_threshold : int, default 100
        Data size threshold below which direct processing is preferred.
    large_data_threshold : int, default 10000
        Data size threshold above which DataFrame processing is always used.
    """

    def __init__(
        self,
        type_inference: TypeInference | None = None,
        unit_extractor: UnitExtractor | None = None,
        min_confidence_threshold: float = 0.6,
        small_data_threshold: int = 100,
        large_data_threshold: int = 10000,
    ):
        self.registry = ClassifierRegistry()
        self.type_inference = type_inference or TypeInference()
        self.unit_extractor = unit_extractor or UnitExtractor()
        # Performance thresholds for optimization decisions
        self.min_confidence_threshold = min_confidence_threshold
        self.small_data_threshold = small_data_threshold
        self.large_data_threshold = large_data_threshold
        self._register_defaults()

    def clear_cache(self):
        """Clear all internal caches of the engine."""
        self.unit_extractor.clear_cache()
        self.type_inference.clear_cache()

    def get_classifiers(self) -> list[str]:
        """Get list of available classifier names.

        Returns
        -------
        list[str]
            List of registered classifier names.
        """
        return list(self.registry._classifiers.keys())

    def load_configuration(self, config: Configuration):
        """Load configuration and update classifiers.

        Parameters
        ----------
        config : Configuration
            Configuration object with classifier and unit settings.
        """
        if not config.merge_with_default:
            self.registry.clear_classifiers()
        self.unit_extractor.load_configuration(config)
        for name, classifer_config in config.classifiers.items():
            classifier = self.registry.get_classifier(name)
            if classifier is None:
                classifier = ConfigurableClassifier(
                    config=classifer_config,
                    type_inference=self.type_inference,
                    unit_extractor=self.unit_extractor,
                )
            self.registry.register(classifier)

    def _register_defaults(self):
        """Register default classifiers."""
        self.registry.register(
            GeneralClassifier(
                priority=1,
                type_inference=self.type_inference,
                unit_extractor=self.unit_extractor,
            )
        )
        self.registry.register(
            ArchitecturalClassifier(
                priority=2,
                type_inference=self.type_inference,
                unit_extractor=self.unit_extractor,
            )
        )
        self.registry.register(
            DefaultClassifier(
                type_inference=self.type_inference,
                unit_extractor=self.unit_extractor,
            )
        )

    def analyze(
        self,
        data: pd.DataFrame | list[dict] | list[list],
        active_classifiers: list[str] | None = None,
        headers: list[str] | None = None,
        contains_headers: bool = False,
    ) -> dict[str, DataTypeUnit]:
        """Analyze any data format with automatic optimization.

        Parameters
        ----------
        data : pd.DataFrame or list[dict] or list[list]
            Input data to analyze. Can be a pandas DataFrame, list of dictionaries,
            or list of lists.
        headers : list[str], optional
            Column names for list input. If None and contains_headers=False,
            generates default column names.
        contains_headers : bool, default False
            If True, treats first row of list data as headers.
        active_classifiers : list[str], optional
            List of classifier names to use. If None, uses all classifiers.

        Returns
        -------
        dict[str, DataTypeUnit]
            Dictionary mapping column names to their classification results.
        """
        self.clear_cache()
        if isinstance(data, pd.DataFrame):
            return self._analyze_dataframe(data, active_classifiers)
        if isinstance(data, list):
            # Extract headers from first row if contains_headers is True
            if len(data) == 0 or (contains_headers and len(data) == 1 and isinstance(data[0], list)):
                return {}
            if contains_headers and isinstance(data[0], list):
                headers = [str(column) for column in data[0]]
                data = data[1:]

            if self._should_use_dataframe(data):
                df = self._convert_to_dataframe(data, headers)
                return self._analyze_dataframe(df, active_classifiers)
            else:
                return self._analyze_list_directly(data, headers, active_classifiers)
        raise ValueError("Unsupported data format")

    def analyze_dataframe(
        self, df: pd.DataFrame, active_classifiers: list[str] | None = None
    ) -> dict[str, DataTypeUnit]:
        """Analyze DataFrame using vectorized operations.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame to analyze.
        active_classifiers : list[str], optional
            List of classifier names to use. If None, uses all classifiers.

        Returns
        -------
        dict[str, DataTypeUnit]
            Dictionary mapping column names to their classification results.
        """
        self.clear_cache()
        return self._analyze_dataframe(df, active_classifiers)

    def _should_use_dataframe(self, data: list) -> bool:
        """Decide whether DataFrame conversion makes sense for performance."""
        data_size = len(data)

        if data_size < self.small_data_threshold:
            return False

        if data_size > self.large_data_threshold:
            return True

        # Medium size: depends on data structure
        if isinstance(data[0], dict):
            # Dict lists benefit more from DataFrame
            return data_size > 500
        else:
            # List of lists: DataFrame for medium+ sizes
            return data_size > 1000

    def _convert_to_dataframe(self, data: list, headers: list[str] | None) -> pd.DataFrame:
        """Convert list data to DataFrame."""
        if isinstance(data[0], dict):
            return pd.DataFrame(data)
        elif isinstance(data[0], list):
            if headers is not None:
                return pd.DataFrame(data, columns=headers)  # pyright: ignore[reportArgumentType]
            else:
                return pd.DataFrame(data)
        else:
            raise ValueError("Cannot convert data to DataFrame")

    def _analyze_dataframe(self, df: pd.DataFrame, active_classifiers: list[str] | None) -> dict[str, DataTypeUnit]:
        """Internal DataFrame analysis method."""
        classifiers = self.registry.get_classifiers(active_classifiers=active_classifiers, sorted_by_priority=True)
        results = {}

        for column in df.columns:
            series = df[column]
            if not isinstance(series, pd.Series):
                continue
            series = series.dropna()
            result = self._classify_series(column, series, classifiers)
            results[column] = result

        return results

    def _analyze_list_directly(
        self,
        data: list,
        headers: list[str] | None,
        active_classifiers: list[str] | None,
    ) -> dict[str, DataTypeUnit]:
        """Direct analysis without DataFrame for small datasets."""
        if not data:
            return {}

        if isinstance(data[0], dict):
            # Dict list
            columns = list(data[0].keys())
            series_data = {col: [row.get(col) for row in data] for col in columns}
        elif isinstance(data[0], list):
            # List of lists
            if not headers:
                headers = [f"Column_{idx}" for idx in range(len(data[0]))]
            columns = headers
            series_data = {
                col: [row[idx] if idx < len(row) else None for row in data] for idx, col in enumerate(columns)
            }
        else:
            raise ValueError("Unsupported data structure")

        classifiers = self.registry.get_classifiers(active_classifiers=active_classifiers, sorted_by_priority=True)
        results = {}
        for col_name, values in series_data.items():
            series = pd.Series(values, name=col_name)
            result = self._classify_series(col_name, series, classifiers)
            results[col_name] = result

        return results

    def _classify_series(self, column_name: str, series: pd.Series, classifiers: list[BaseClassifier]) -> DataTypeUnit:
        """Classify a single Series using vectorized operations."""

        best_result = None
        for classifier in classifiers:
            try:
                # Vectorized classification call
                result = classifier.classify_series(column_name, series)
                if result.confidence < self.min_confidence_threshold:
                    continue
                if best_result is None or result.confidence > best_result.confidence:
                    best_result = result

                # Early exit on high confidence
                if result.confidence >= 0.9:
                    break

            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                log.error(f"Classifier '{classifier.get_name()}' failed: {exc}")
                continue
            except Exception as exc:
                log.error(f"Unexpected error in classifier '{classifier.get_name()}': {exc}")
                continue

        # Create fallback result if no classifier succeeded
        fallback_result = DataTypeUnit(
            data_type=DataType.UNKNOWN,
            unit=Units.NONE,
            confidence=0.0,
            classifier_name="NO CLASSIFIER",
            total_values=len(series.dropna()),
            null_count=series.isna().sum(),
            non_convertible_count=0,
        )

        final_result = best_result or fallback_result

        # Log warnings for data quality issues
        if final_result.null_percentage > 50:
            log.warning(f"Column '{column_name}' has {final_result.null_percentage:.1f}% null values")
        if final_result.confidence < 0.3:
            log.warning(f"Low confidence ({final_result.confidence:.2f}) for column '{column_name}'")

        return final_result


# ============================================================================
# CLI Functions
# ============================================================================


def analyze_data(
    data: pd.DataFrame | list[dict] | list[list],
    headers: list[str] | None = None,
    contains_headers: bool = False,
    active_classifiers: list[str] | None = None,
    config_path: str | Path | None = None,
    merge_with_default: bool = False,
) -> dict[str, DataTypeUnit]:
    """Analyze data and return DataTypeUnit for each column.

    Parameters
    ----------
    data : pd.DataFrame or list[dict] or list[list]
        Input data to analyze. Can be a pandas DataFrame, list of dictionaries,
        or list of lists.
    headers : list[str], optional
        Column names for list input. If None and contains_headers=False,
        generates default column names.
    contains_headers : bool, default False
        If True, treats first row of list data as headers.
    active_classifiers : list[str], optional
        List of classifier names to use. If None, uses all classifiers.
    config_path : str or Path, optional
        Path to configuration file. If None, uses code defaults.
    merge_with_default : bool, optional
        If True, merges config with code defaults. If False, uses only config.
        Must be provided if config_path is given.

    Returns
    -------
    dict[str, DataTypeUnit]
        Dictionary mapping column names to their classification results.
    """
    type_inference = TypeInference()
    unit_extractor = UnitExtractor()
    engine = DataClassificationEngine(type_inference, unit_extractor)
    if merge_with_default is None and config_path:
        raise ValueError("merge_with_default can not be None if config_path is set")
    config = _load_configuration(config_path, merge_with_default)
    if config:
        engine.load_configuration(config)
    return engine.analyze(
        data=data,
        headers=headers,
        contains_headers=contains_headers,
        active_classifiers=active_classifiers,
    )


def _load_configuration(config_path: str | Path | None, merge_defaults: bool) -> Configuration | None:
    """Load configuration from YAML file."""
    if not config_path:
        return None

    try:
        with open(config_path, encoding="utf-8") as yaml_file:
            yaml_config = yaml.safe_load(yaml_file)
    except (OSError, FileNotFoundError, PermissionError) as exc:
        raise FileNotFoundError(f"Cannot read configuration file '{config_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in configuration file '{config_path}': {exc}") from exc
    config = Configuration(
        merge_with_default=merge_defaults,
        direct_mappings=yaml_config.get("direct_mappings", {}),
        context_mappings=yaml_config.get("context_mappings", {}),
        classifiers=yaml_config.get("classifiers", {}),
    )
    return config


def _load_input_file(filepath: str):
    """Load various file formats."""
    path = Path(filepath)
    suffix = path.suffix.lower()

    try:
        if suffix == ".csv":
            return pd.read_csv(filepath)
        elif suffix in [".xlsx", ".xls"]:
            return pd.read_excel(filepath)
        elif suffix == ".json":
            with open(filepath) as f:
                data = json.load(f)
                # Wenn es eine Liste ist, direkt zurückgeben
                if isinstance(data, list):
                    return data
                # Wenn es ein Dict ist, als DataFrame behandeln
                elif isinstance(data, dict):
                    return pd.DataFrame([data])
                else:
                    raise ValueError("JSON must contain list or dict")
    except (OSError, FileNotFoundError, PermissionError) as exc:
        raise FileNotFoundError(f"Cannot read file '{filepath}': {exc}") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"Cannot parse {suffix.upper()} file '{filepath}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in file '{filepath}': {exc}") from exc
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def _save_results(results: dict[str, DataTypeUnit], filepath: str, format: str):
    """Save analysis results in various formats."""

    if format == "json":
        json_data = {}
        for col, result in results.items():
            json_data[col] = {
                "data_type": result.data_type.value,
                "unit": result.unit.full_name,
                "confidence": result.confidence,
                "classifier": result.classifier_name,
            }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

    elif format == "csv":
        # Als CSV-Tabelle
        rows = []
        for col, result in results.items():
            rows.append(
                {
                    "column": col,
                    "data_type": result.data_type.value,
                    "unit": result.unit.full_name,
                    "confidence": result.confidence,
                    "classifier": result.classifier_name,
                }
            )

        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False)

    else:
        raise ValueError(f"Unsupported output format: {format}")


def _print_results(results: dict[str, DataTypeUnit], format: str):
    """Print analysis results to console."""

    if format == "json":
        json_data = {}
        for col, result in results.items():
            json_data[col] = {
                "data_type": result.data_type.value,
                "unit": result.unit.full_name,
                "confidence": result.confidence,
                "classifier": result.classifier_name,
            }
        print(json.dumps(json_data, indent=2, ensure_ascii=False))

    elif format == "table":
        _print_simple_table(results)

    elif format == "csv":
        # CSV-Format auf Konsole
        print("column,data_type,unit,confidence,classifier")
        for col, result in results.items():
            print(
                f"{col},{result.data_type.value},{result.unit.full_name},{result.confidence},{result.classifier_name}"
            )


def _print_simple_table(results: dict[str, DataTypeUnit]):
    """Simple table output for results."""
    print("=" * 100)
    print("DATENANALYSE-ERGEBNISSE")
    print("=" * 100)
    print(f"{'Spalte':<20} {'Daten Typ':<15} {'Einheit':<15} {'Konfidenz':<10} {'Klassifikator':<15}")
    print("-" * 100)

    for col, result in results.items():
        print(
            f"{col:<20} {result.data_type.value:<15} {result.unit.full_name:<15} "
            f"{result.confidence:<10.3f} {result.classifier_name:<15}"
        )

    print("=" * 100)


def export_default_config(output_path: str | Path, export_format: str = "yaml"):
    """Export the default classifier and unit configuration to a file.

    This function creates a configuration file containing all current
    unit mappings and classifier patterns. This file can be used as a
    starting point for custom configurations.

    Parameters
    ----------
    output_path : str or Path
        Path where the configuration file should be saved.
    format : str, default "yaml"
        Output format, either "yaml" or "json".

    Examples
    --------
    >>> export_default_config("my_config.yaml")
    >>> export_default_config("config.json", format="json")
    """

    # Collect unit data from VectorizedUnitExtractor
    config = {
        "direct_mappings": {},
        "context_mappings": {},
        "classifiers": {},
    }

    engine = DataClassificationEngine()
    automatic_symbols = set()
    for unit in Units.get_all_units():
        symbol_key = unit.symbol.lower().strip()
        if not engine.unit_extractor.is_valid_unit_symbol(symbol_key):
            continue
        automatic_symbols.add(symbol_key)

    # Export only manual mappings (alternative spellings)
    for key, unit in engine.unit_extractor.direct_mappings.items():
        # Skip automatic symbol mappings, only export manual alternatives
        if key in automatic_symbols:
            continue
        config["direct_mappings"][key] = unit.full_name

    # Export context mappings
    for context, unit_type in engine.unit_extractor.context_mappings.items():
        config["context_mappings"][context] = unit_type.value

    # Collect classifier data
    for classifier in engine.registry.get_classifiers(sorted_by_priority=False):
        name = classifier.get_name().lower()
        config["classifiers"][name] = classifier.to_dict()

    output_path = Path(output_path)
    if export_format.lower() == "yaml":
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    elif export_format.lower() == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    else:
        raise ValueError(f"Unsupported format: {export_format}. Use 'yaml' or 'json'.")

    print(f"✅ Configuration exported to: {output_path}")
    print(f"📊 {len(config['direct_mappings'])} direct unit mappings")
    print(f"📊 {len(config['context_mappings'])} context mappings")
    print(f"📊 {len(config['classifiers'])} classifiers")
    total_patterns = sum(len(c["patterns"]) for c in config["classifiers"].values())
    print(f"📊 {total_patterns} patterns total")


# ============================================================================
# DEMO
# ============================================================================


def demo_vectorized_classification():
    """Demonstrate vectorized classification capabilities."""
    print("🔍 DEMO: Standalone DataFrame Analyzer")
    print("=" * 50)

    data = {
        # Strings that should be recognized as numbers
        "room_number": ["R001", "R002", "R003"],
        "area_text": ["25.5", "30.0", "22.8"],  # Strings!
        "height_mm": ["2800", "2800", "2800"],  # Strings!
        "count_str": ["4", "6", "3"],  # Strings!
        # Real numeric data
        "area_numeric": [25.5, 30.0, 22.8],
        "cost_euro": [1500.50, 1800.00, 1200.75],
        # Boolean data
        "is_structural": [True, False, True],
        "fire_rated": ["yes", "no", "yes"],  # String booleans
        # Mixed/problematic data
        "thickness (mm)": ["100", "150", "120"],
        "material": ["Concrete", "Steel", "Wood"],
        "mixed_data": ["100", "n/a", "200"],  # Partially numeric
    }

    df = pd.DataFrame(data)
    print("Original DataFrame:")
    print(df)
    print("\nDataFrame dtypes:")
    print(df.dtypes)
    print()

    results = analyze_data(df)

    _print_results(results, "table")

    # Test different input formats
    print("\n" + "=" * 50)
    print("TEST: Different input formats")
    print("=" * 50)

    # List of dictionaries
    dict_data = [
        {"name": "Item1", "length_mm": "100", "active": "yes"},
        {"name": "Item2", "length_mm": "200", "active": "no"},
        {"name": "Item3", "length_mm": "150", "active": "yes"},
    ]

    print("\n1. List of dictionaries:")
    results_dict = analyze_data(dict_data)
    _print_results(results_dict, "table")

    # List of lists
    list_data = [
        ["Item1", "100", "yes"],
        ["Item2", "200", "no"],
        ["Item3", "150", "yes"],
    ]
    headers = ["name", "length_mm", "active"]

    print("\n2. List of lists with headers:")
    results_list = analyze_data(list_data, headers=headers)
    _print_results(results_list, "table")


def main():
    """Command line interface for the analyzer."""
    parser = argparse.ArgumentParser(
        description="Analysiert Datenstrukturen und erkennt Datentypen/Einheiten",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s data.csv
  %(prog)s data.xlsx --output results.json --format json
  %(prog)s data.json --format table --contains-headers
  %(prog)s --export-config my_config.yaml
        """,
    )

    parser.add_argument("input", nargs="?", help="Input file (CSV, Excel, JSON)")
    parser.add_argument("--output", "-o", help="Output file for results")
    parser.add_argument(
        "--format",
        choices=["json", "table", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--contains-headers",
        action="store_true",
        help="First row contains column headers (for list data)",
    )
    parser.add_argument("--export-config", metavar="FILE", help="Export default configuration to file")
    parser.add_argument("--config", metavar="FILE", help="Load configuration from file")
    parser.add_argument("--config-only", action="store_true", help="Use only config file (ignore code defaults)")

    args = parser.parse_args()

    # Handle config export
    if args.export_config:
        try:
            format_type = "yaml" if args.export_config.endswith((".yaml", ".yml")) else "json"
            export_default_config(args.export_config, format_type)
            return
        except (OSError, PermissionError, FileNotFoundError) as exc:
            log.error(f"File error exporting configuration: {exc}")
            print(f"❌ File error exporting configuration: {exc}")
            sys.exit(1)
        except (ValueError, TypeError) as exc:
            log.error(f"Configuration error: {exc}")
            print(f"❌ Configuration error: {exc}")
            sys.exit(1)
        except Exception as exc:
            log.error(f"Unexpected error exporting configuration: {exc}")
            print(f"❌ Unexpected error exporting configuration: {exc}")
            sys.exit(1)

    # Require input file for analysis
    if not args.input:
        parser.error("Input file is required")

    try:
        print(f"📂 Loading data from: {args.input}")
        data = _load_input_file(args.input)

        print("🔍 Analyzing data structure...")
        merge_with_default = not args.config_only
        results = analyze_data(
            data,
            contains_headers=args.contains_headers,
            config_path=args.config,
            merge_with_default=merge_with_default,
        )

        if args.output:
            print(f"💾 Saving results to: {args.output}")
            _save_results(results, args.output, args.format)
        else:
            _print_results(results, args.format)

        print(f"\n✅ Analysis completed! {len(results)} columns analyzed.")

    except (OSError, FileNotFoundError, PermissionError) as exc:
        log.error(f"File error: {exc}")
        print(f"❌ File error: {exc}")
        sys.exit(1)
    except (ValueError, TypeError, KeyError) as exc:
        log.error(f"Data error: {exc}")
        print(f"❌ Data error: {exc}")
        sys.exit(1)
    except Exception as exc:
        log.error(f"Unexpected error: {exc}")
        print(f"❌ Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    # Demo when run without arguments
    if len(sys.argv) == 1:
        demo_vectorized_classification()
    else:
        main()
