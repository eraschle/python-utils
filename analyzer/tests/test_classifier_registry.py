"""Tests für die ClassifierRegistry Klasse."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_analyzer import (
    ArchitecturalClassifier,
    ClassifierRegistry,
    GeneralClassifier,
    TypeInference,
    UnitExtractor,
)


class TestClassifierRegistry:
    """Tests für ClassifierRegistry."""

    def setup_method(self):
        """Setup für jeden Test."""
        self.registry = ClassifierRegistry()
        self.type_inference = TypeInference()
        self.unit_extractor = UnitExtractor()

    def test_initialization(self):
        """Test dass Registry korrekt initialisiert wird."""
        assert self.registry._classifiers is not None
        assert len(self.registry._classifiers) == 0

    def test_register_classifier(self):
        """Test Registrierung eines Klassifikators."""
        classifier = GeneralClassifier(
            priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        self.registry.register(classifier)

        assert len(self.registry._classifiers) == 1
        assert "general" in self.registry._classifiers
        assert self.registry._classifiers["general"] == classifier

    def test_register_multiple_classifiers(self):
        """Test Registrierung mehrerer Klassifikatoren."""
        general = GeneralClassifier(priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor)
        architectural = ArchitecturalClassifier(
            priority=2, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        self.registry.register(general)
        self.registry.register(architectural)

        assert len(self.registry._classifiers) == 2
        assert "general" in self.registry._classifiers
        assert "architectural" in self.registry._classifiers

    def test_register_overwrites_existing(self):
        """Test dass Registrierung existierenden Klassifikator überschreibt."""
        classifier1 = GeneralClassifier(
            priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )
        classifier2 = GeneralClassifier(
            priority=5,  # Andere Priorität
            type_inference=self.type_inference,
            unit_extractor=self.unit_extractor,
        )

        self.registry.register(classifier1)
        assert self.registry._classifiers["general"].get_priority() == 1

        self.registry.register(classifier2)
        assert self.registry._classifiers["general"].get_priority() == 5

    def test_get_classifiers_empty(self):
        """Test get_classifiers mit leerer Registry."""
        classifiers = self.registry.get_classifiers()
        assert classifiers == []

    def test_get_classifiers_all(self):
        """Test get_classifiers gibt alle Klassifikatoren zurück."""
        general = GeneralClassifier(priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor)
        architectural = ArchitecturalClassifier(
            priority=2, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        self.registry.register(general)
        self.registry.register(architectural)

        classifiers = self.registry.get_classifiers()
        assert len(classifiers) == 2
        assert general in classifiers
        assert architectural in classifiers

    def test_get_classifiers_sorted_by_priority(self):
        """Test dass Klassifikatoren nach Priorität sortiert werden."""
        low_priority = GeneralClassifier(
            priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )
        high_priority = ArchitecturalClassifier(
            priority=10, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        # Registriere in umgekehrter Reihenfolge
        self.registry.register(low_priority)
        self.registry.register(high_priority)

        classifiers = self.registry.get_classifiers(sorted_by_priority=True)
        assert len(classifiers) == 2
        assert classifiers[0] == high_priority  # Höhere Priorität zuerst
        assert classifiers[1] == low_priority

    def test_get_classifiers_unsorted(self):
        """Test get_classifiers ohne Sortierung."""
        general = GeneralClassifier(priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor)
        architectural = ArchitecturalClassifier(
            priority=10, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        self.registry.register(general)
        self.registry.register(architectural)

        classifiers = self.registry.get_classifiers(sorted_by_priority=False)
        assert len(classifiers) == 2
        # Reihenfolge ist nicht garantiert, nur dass beide enthalten sind
        assert general in classifiers
        assert architectural in classifiers

    def test_get_classifiers_with_filter(self):
        """Test get_classifiers mit active_classifiers Filter."""
        general = GeneralClassifier(priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor)
        architectural = ArchitecturalClassifier(
            priority=2, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        self.registry.register(general)
        self.registry.register(architectural)

        # Filter nur General
        classifiers = self.registry.get_classifiers(active_classifiers=["General"])
        assert len(classifiers) == 1
        assert classifiers[0] == general

        # Filter nur Architectural
        classifiers = self.registry.get_classifiers(active_classifiers=["Architectural"])
        assert len(classifiers) == 1
        assert classifiers[0] == architectural

        # Filter beide
        classifiers = self.registry.get_classifiers(active_classifiers=["General", "Architectural"])
        assert len(classifiers) == 2

    def test_get_classifier_by_name(self):
        """Test get_classifier zum Abrufen eines spezifischen Klassifikators."""
        general = GeneralClassifier(priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor)

        self.registry.register(general)

        # Exact match (lowercase)
        result = self.registry.get_classifier("general")
        assert result == general

        # Case mismatch (sollte nicht funktionieren)
        result = self.registry.get_classifier("General")
        assert result is None

        # Nicht existierender Klassifikator
        result = self.registry.get_classifier("nonexistent")
        assert result is None

    def test_clear_classifiers(self):
        """Test clear_classifiers entfernt alle Klassifikatoren."""
        general = GeneralClassifier(priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor)
        architectural = ArchitecturalClassifier(
            priority=2, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        self.registry.register(general)
        self.registry.register(architectural)

        assert len(self.registry._classifiers) == 2

        self.registry.clear_classifiers()

        assert len(self.registry._classifiers) == 0
        assert self.registry.get_classifiers() == []

    def test_classifier_name_conversion(self):
        """Test dass Klassifikator-Namen in Kleinbuchstaben konvertiert werden."""
        classifier = GeneralClassifier(
            priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        self.registry.register(classifier)

        # Name wird zu Kleinbuchstaben konvertiert
        assert "general" in self.registry._classifiers
        assert "General" not in self.registry._classifiers
        assert "GENERAL" not in self.registry._classifiers
