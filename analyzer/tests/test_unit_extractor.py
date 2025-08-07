"""Tests für die UnitExtractor Klasse."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_analyzer import (
    Configuration,
    UnitExtractor,
    UnitType,
    Units,
)


class TestUnitExtractor:
    """Tests für die UnitExtractor Klasse."""

    def setup_method(self):
        """Setup für jeden Test."""
        self.extractor = UnitExtractor()

    def test_initialization(self):
        """Test dass UnitExtractor korrekt initialisiert wird."""
        assert self.extractor.direct_mappings is not None
        assert self.extractor.context_mappings is not None
        assert len(self.extractor.direct_mappings) > 0
        assert len(self.extractor.context_mappings) > 0

    def test_is_valid_unit_symbol(self):
        """Test die is_valid_unit_symbol Methode."""
        # Ungültige Symbole
        assert self.extractor.is_valid_unit_symbol("") is False
        assert self.extractor.is_valid_unit_symbol("?") is False
        assert self.extractor.is_valid_unit_symbol("~") is False

        # Ambiguöse einzelne Zeichen
        assert self.extractor.is_valid_unit_symbol("a") is False
        assert self.extractor.is_valid_unit_symbol("k") is False
        assert self.extractor.is_valid_unit_symbol("m") is False
        assert self.extractor.is_valid_unit_symbol("g") is False
        assert self.extractor.is_valid_unit_symbol("h") is False
        assert self.extractor.is_valid_unit_symbol("s") is False

        # Gültige Symbole
        assert self.extractor.is_valid_unit_symbol("mm") is True
        assert self.extractor.is_valid_unit_symbol("cm") is True
        assert self.extractor.is_valid_unit_symbol("kg") is True
        assert self.extractor.is_valid_unit_symbol("l") is True
        assert self.extractor.is_valid_unit_symbol("°c") is True

    def test_extract_unit_from_brackets(self):
        """Test Extraktion von Einheiten aus Klammern."""
        # Millimeter in Klammern
        result = self.extractor.extract_unit("Length (mm)")
        assert result is not None
        assert result.symbol == "mm"
        assert result.unit_type == UnitType.LENGTH

        # Kilogramm in Klammern
        result = self.extractor.extract_unit("Weight (kg)")
        assert result is not None
        assert result.symbol == "kg"
        assert result.unit_type == UnitType.MASS

        # Unbekannte Einheit in Klammern
        result = self.extractor.extract_unit("Something (xyz)")
        assert result is not None
        assert result == Units.UNKNOWN
        assert result.unit_type == UnitType.UNKNOWN

    def test_extract_unit_from_separators(self):
        """Test Extraktion von Einheiten mit Separatoren."""
        # Underscore
        result = self.extractor.extract_unit("length_mm")
        assert result is not None
        assert result.symbol == "mm"
        assert result.unit_type == UnitType.LENGTH

        # Bindestrich
        result = self.extractor.extract_unit("weight-kg")
        assert result is not None
        assert result.symbol == "kg"
        assert result.unit_type == UnitType.MASS

        # Punkt
        result = self.extractor.extract_unit("area.m2")
        assert result is not None
        assert result.symbol == "m²"
        assert result.unit_type == UnitType.AREA

        # Leerzeichen
        result = self.extractor.extract_unit("volume l")
        assert result is not None
        assert result.symbol == "l"
        assert result.unit_type == UnitType.VOLUME

    def test_extract_unit_from_context(self):
        """Test Extraktion von Einheiten aus Kontext."""
        # Länge Kontext
        result = self.extractor.extract_unit("länge")
        assert result is not None
        assert result.symbol == "~"  # one_unit_of
        assert result.unit_type == UnitType.LENGTH

        # Breite Kontext
        result = self.extractor.extract_unit("width")
        assert result is not None
        assert result.symbol == "~"
        assert result.unit_type == UnitType.LENGTH

        # Gewicht Kontext
        result = self.extractor.extract_unit("gewicht")
        assert result is not None
        assert result.symbol == "~"
        assert result.unit_type == UnitType.MASS

        # Temperatur Kontext
        result = self.extractor.extract_unit("temperature")
        assert result is not None
        assert result.symbol == "~"
        assert result.unit_type == UnitType.TEMPERATURE

    def test_extract_unit_no_match(self):
        """Test wenn keine Einheit gefunden wird."""
        result = self.extractor.extract_unit("random_column_name")
        assert result == Units.UNKNOWN

    def test_extract_unit_case_insensitive(self):
        """Test dass Extraktion case-insensitive ist."""
        # Großbuchstaben
        result = self.extractor.extract_unit("LENGTH_MM")
        assert result is not None
        assert result.symbol == "mm"

        # Gemischt
        result = self.extractor.extract_unit("Weight (Kg)")
        assert result is not None
        assert result.symbol == "kg"

    def test_load_configuration_merge_with_defaults(self):
        """Test Laden einer Konfiguration mit merge_with_default=True."""
        config = Configuration(
            merge_with_default=True,
            direct_mappings={"test_unit": "length (mm)"},
            context_mappings={"test_context": "mass"},
            classifiers={},
        )

        # Anzahl der Mappings vor dem Laden
        before_direct = len(self.extractor.direct_mappings)
        before_context = len(self.extractor.context_mappings)

        self.extractor.load_configuration(config)

        # Prüfe dass neue Mappings hinzugefügt wurden
        assert "test_unit" in self.extractor.direct_mappings
        assert self.extractor.direct_mappings["test_unit"].symbol == "mm"
        assert "test_context" in self.extractor.context_mappings
        assert self.extractor.context_mappings["test_context"] == UnitType.MASS

        # Prüfe dass alte Mappings noch vorhanden sind
        assert len(self.extractor.direct_mappings) > before_direct
        assert len(self.extractor.context_mappings) > before_context

    def test_load_configuration_without_merge(self):
        """Test Laden einer Konfiguration mit merge_with_defaults=False."""
        config = Configuration(
            merge_with_default=False,
            direct_mappings={"only_unit": "length (mm)"},
            context_mappings={"only_context": "mass"},
            classifiers={},
        )

        self.extractor.load_configuration(config)

        # Prüfe dass nur die neuen Mappings vorhanden sind
        assert "only_unit" in self.extractor.direct_mappings
        assert self.extractor.direct_mappings["only_unit"].symbol == "mm"
        assert "only_context" in self.extractor.context_mappings
        assert self.extractor.context_mappings["only_context"] == UnitType.MASS

        # Prüfe dass alte Mappings entfernt wurden
        assert "mm" not in self.extractor.direct_mappings  # Sollte nicht mehr direkt vorhanden sein

    def test_manual_mappings(self):
        """Test dass manuelle Mappings korrekt geladen werden."""
        # Deutsche Bezeichnungen
        assert "millimeter" in self.extractor.direct_mappings
        assert "kilogramm" in self.extractor.direct_mappings
        assert "liter" in self.extractor.direct_mappings

        # Englische Bezeichnungen
        assert "pieces" in self.extractor.direct_mappings
        assert "celsius" in self.extractor.direct_mappings

        # Abkürzungen
        assert "pcs" in self.extractor.direct_mappings
        assert "m3/h" in self.extractor.direct_mappings

    def test_context_mappings(self):
        """Test dass Kontext-Mappings korrekt geladen werden."""
        # Deutsche Kontexte
        assert "länge" in self.extractor.context_mappings
        assert "breite" in self.extractor.context_mappings
        assert "höhe" in self.extractor.context_mappings
        assert "gewicht" in self.extractor.context_mappings
        assert "temperatur" in self.extractor.context_mappings

        # Englische Kontexte
        assert "length" in self.extractor.context_mappings
        assert "width" in self.extractor.context_mappings
        assert "height" in self.extractor.context_mappings
        assert "weight" in self.extractor.context_mappings
        assert "temperature" in self.extractor.context_mappings

        # Technische Kontexte
        assert "pressure" in self.extractor.context_mappings
        assert "voltage" in self.extractor.context_mappings
        assert "velocity" in self.extractor.context_mappings

    def test_priority_of_extraction_methods(self):
        """Test die Priorität der Extraktionsmethoden."""
        # Klammern haben höchste Priorität
        result = self.extractor.extract_unit("length_cm (mm)")
        assert result is not None
        assert result.symbol == "mm"  # Klammer gewinnt über Separator

        # Separator hat Priorität über Kontext
        result = self.extractor.extract_unit("length_kg")
        assert result is not None
        assert result.symbol == "kg"  # Separator gewinnt über Kontext "length"
        assert result.unit_type == UnitType.MASS
