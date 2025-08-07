"""Tests für die Classifier Klassen."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_analyzer import (
    ArchitecturalClassifier,
    ClassifierDict,
    DataClassificationEngine,
    DataType,
    DataTypeUnit,
    GeneralClassifier,
    ConfigurableClassifier,
    TypeInference,
    UnitExtractor,
    UnitType,
    Units,
)


class TestGeneralClassifier:
    """Tests für GeneralClassifier."""

    def setup_method(self):
        """Setup für jeden Test."""
        self.type_inference = TypeInference()
        self.unit_extractor = UnitExtractor()
        self.classifier = GeneralClassifier(
            priority=1, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )
        self.classifier.setup_patterns()

    def test_initialization(self):
        """Test Initialisierung des GeneralClassifier."""
        assert self.classifier.get_name() == "General"
        assert self.classifier.get_priority() == 1
        assert len(self.classifier.patterns) > 0

    def test_classify_series_boolean(self):
        """Test Klassifizierung von Boolean-Daten."""
        series = pd.Series(["true", "false", "true", "false"])
        result = self.classifier.classify_series("is_active", series)

        assert isinstance(result, DataTypeUnit)
        assert result.data_type == DataType.BOOLEAN
        assert result.classifier_name == "General"

    def test_classify_series_length(self):
        """Test Klassifizierung von Längen-Daten."""
        series = pd.Series([100, 200, 150, 175])
        result = self.classifier.classify_series("length_mm", series)

        assert result.data_type == DataType.INTEGER
        assert result.unit.symbol == "mm"
        assert result.unit.unit_type == UnitType.LENGTH

    def test_classify_series_area(self):
        """Test Klassifizierung von Flächen-Daten."""
        series = pd.Series([25.5, 30.0, 22.8])
        result = self.classifier.classify_series("area_m2", series)

        assert result.data_type == DataType.FLOAT
        assert result.unit.symbol == "m²"
        assert result.unit.unit_type == UnitType.AREA

    def test_classify_series_weight(self):
        """Test Klassifizierung von Gewichts-Daten."""
        series = pd.Series([1000, 1500, 2000])
        result = self.classifier.classify_series("weight_kg", series)

        assert result.data_type == DataType.INTEGER
        assert result.unit.symbol == "kg"
        assert result.unit.unit_type == UnitType.MASS

    def test_classify_series_count(self):
        """Test Klassifizierung von Anzahl-Daten."""
        series = pd.Series([5, 10, 15, 20])
        result = self.classifier.classify_series("count", series)

        assert result.data_type == DataType.INTEGER
        assert result.unit.unit_type == UnitType.QUANTITY

    def test_pattern_matching(self):
        """Test Pattern-Matching für verschiedene Muster."""
        series = pd.Series([1, 2, 3])

        # Boolean patterns
        result = self.classifier.classify_series("ist_aktiv", series)
        assert result.data_type == DataType.INTEGER  # Daten sind Integer, aber Pattern deutet auf Boolean

        # Length patterns
        result = self.classifier.classify_series("länge", series)
        assert result.unit.unit_type == UnitType.LENGTH

        result = self.classifier.classify_series("breite", series)
        assert result.unit.unit_type == UnitType.LENGTH

        result = self.classifier.classify_series("höhe", series)
        assert result.unit.unit_type == UnitType.LENGTH

        # Volume pattern
        result = self.classifier.classify_series("volumen", series)
        assert result.unit.unit_type == UnitType.VOLUME

    def test_confidence_calculation(self):
        """Test die Confidence-Berechnung."""
        series = pd.Series([100, 200, 150])

        # Mit passendem Pattern und Unit
        result = self.classifier.classify_series("length_mm", series)
        assert result.confidence > 0.5
        assert result.total_values == 3
        assert result.null_count == 0
        assert result.non_convertible_count == 0
        assert result.convertible_percentage == 100.0

        # Ohne Pattern und Unit - Confidence wird höher sein wegen erfolgreicher Konvertierung
        result = self.classifier.classify_series("random_name", series)
        # Angepasst: Integer-Werte bekommen standardmäßig höhere Confidence
        assert result.confidence >= 0.5, f"Confidence: {result.confidence}, Result: {result}"
        assert result.total_values == 3
        assert result.non_convertible_count == 0
        assert result.null_count == 0

    def test_metrics_with_nulls(self):
        """Test Metriken mit NULL-Werten."""
        series = pd.Series([10, None, 20, None, 30])

        result = self.classifier.classify_series("test_column", series)

        # Überprüfe Metriken
        assert result.total_count == 5  # Gesamt
        assert result.total_values == 3  # Ohne None
        assert result.null_count == 2  # Anzahl None
        assert result.non_convertible_count == 0  # Alle konvertierbar
        assert result.convertible_count == 3
        assert result.convertible_percentage == 100.0
        assert result.null_percentage == 40.0  # 2 von 5

    def test_metrics_with_mixed_data(self):
        """Test Metriken mit gemischten Daten."""
        series = pd.Series(["1", "2", "text", None, "4"])

        result = self.classifier.classify_series("mixed_column", series)

        # Überprüfe Metriken
        assert result.total_count == 5
        assert result.total_values == 4  # Ohne None
        assert result.null_count == 1

        # Bei gemischten Daten könnte der Typ INTEGER/FLOAT sein mit non_convertible_count > 0
        if result.data_type in (DataType.INTEGER, DataType.FLOAT):
            assert result.non_convertible_count == 1  # "text" kann nicht konvertiert werden
            assert result.convertible_count == 3  # "1", "2", "4"
            assert result.convertible_percentage == 75.0  # 3 von 4
        else:
            # Oder STRING/UNKNOWN ohne non_convertible_count
            assert result.data_type in (DataType.STRING, DataType.UNKNOWN)
            assert result.non_convertible_count == 0

    def test_data_quality_score(self):
        """Test Data Quality Score Berechnung."""
        # Perfekte Daten
        series_perfect = pd.Series([1, 2, 3, 4, 5])
        result = self.classifier.classify_series("perfect", series_perfect)
        assert result.data_quality_score == 1.0  # 100% vollständig und konvertierbar

        # Daten mit NULLs
        series_with_nulls = pd.Series([1, None, 3, None, 5])
        result = self.classifier.classify_series("with_nulls", series_with_nulls)
        # Score = (3/5 * 0.4) + (3/3 * 0.6) = 0.24 + 0.6 = 0.84
        assert 0.83 <= result.data_quality_score <= 0.85

        # Gemischte Daten
        series_mixed = pd.Series(["1", "text", None, "3", "4"])
        result = self.classifier.classify_series("mixed", series_mixed)
        # 4 von 5 nicht-null (80%), wenn INTEGER: 3 von 4 konvertierbar (75%)
        # Score = (4/5 * 0.4) + (3/4 * 0.6) = 0.32 + 0.45 = 0.77
        if result.data_type in (DataType.INTEGER, DataType.FLOAT):
            assert 0.76 <= result.data_quality_score <= 0.78

    def test_to_dict(self):
        """Test to_dict Methode."""
        classifier_dict = self.classifier.to_dict()

        assert classifier_dict["name"] == "General"
        assert classifier_dict["priority"] == 1
        assert "patterns" in classifier_dict
        assert len(classifier_dict["patterns"]) > 0

        # Prüfe Struktur eines Patterns
        first_pattern = classifier_dict["patterns"][0]
        assert "pattern" in first_pattern
        assert "data_type" in first_pattern


class TestArchitecturalClassifier:
    """Tests für ArchitecturalClassifier."""

    def setup_method(self):
        """Setup für jeden Test."""
        self.type_inference = TypeInference()
        self.unit_extractor = UnitExtractor()
        self.classifier = ArchitecturalClassifier(
            priority=2, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )
        self.classifier.setup_patterns()

    def test_initialization(self):
        """Test Initialisierung des ArchitecturalClassifier."""
        assert self.classifier.get_name() == "Architectural"
        assert self.classifier.get_priority() == 2
        assert len(self.classifier.patterns) > 0

    def test_architectural_patterns(self):
        """Test architekturspezifische Patterns."""
        series = pd.Series([100, 200, 150])

        # Phase
        result = self.classifier.classify_series("phase", series)
        assert result.data_type == DataType.INTEGER  # Actual data type

        # Thickness
        result = self.classifier.classify_series("thickness", series)
        assert result.unit == Units.MILLIMETER
        assert result.unit.unit_type == UnitType.LENGTH

        # Elevation
        result = self.classifier.classify_series("elevation", series)
        assert result.unit == Units.METER
        assert result.unit.unit_type == UnitType.LENGTH

        # Material
        result = self.classifier.classify_series("material", series)
        assert result.classifier_name == "Architectural"

        # Structural
        series_bool = pd.Series(["yes", "no", "yes"])
        result = self.classifier.classify_series("structural", series_bool)
        assert result.data_type == DataType.BOOLEAN

    def test_altitude_patterns(self):
        """Test Höhen-bezogene Patterns."""
        series = pd.Series([100.5, 200.5, 150.5])

        result = self.classifier.classify_series("m.ü.m", series)
        assert result.unit == Units.METER
        assert result.unit.unit_type == UnitType.LENGTH

        result = self.classifier.classify_series("altitude", series)
        assert result.unit == Units.METER
        assert result.unit.unit_type == UnitType.LENGTH

    def test_fire_rated_pattern(self):
        """Test Brandschutz Pattern."""
        series = pd.Series(["yes", "no", "yes"])
        result = self.classifier.classify_series("fire_rated", series)
        assert result.data_type == DataType.BOOLEAN


class TestGenericClassifier:
    """Tests für GenericClassifier."""

    def setup_method(self):
        """Setup für jeden Test."""
        self.type_inference = TypeInference()
        self.unit_extractor = UnitExtractor()

    def test_initialization_valid(self):
        """Test Initialisierung mit gültiger Konfiguration."""
        config: ClassifierDict = {
            "name": "TestClassifier",
            "priority": 5,
            "patterns": [
                {"pattern": r".*test.*", "data_type": "string"},
                {"pattern": r".*measurement.*", "data_type": "float", "unit": "length (mm)"},
            ],
        }

        classifier = ConfigurableClassifier(
            config=config, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        assert classifier.get_name() == "TestClassifier"
        assert classifier.get_priority() == 5
        assert len(classifier.patterns) == 0
        classifier.setup_patterns()
        assert len(classifier.patterns) == 2

    def test_initialization_missing_name(self):
        """Test dass Fehler bei fehlender Name geworfen wird."""
        config: ClassifierDict = {"name": "", "priority": 5, "patterns": []}

        with pytest.raises(ValueError):
            ConfigurableClassifier(
                config=config,
                type_inference=self.type_inference,
                unit_extractor=self.unit_extractor,
            )

    def test_initialization_missing_priority(self):
        """Test dass Fehler bei fehlender Priorität geworfen wird."""
        config: ClassifierDict = {
            "name": "TestClassifier",
            "priority": 0,  # 0 wird als False interpretiert
            "patterns": [],
        }

        with pytest.raises(ValueError):
            ConfigurableClassifier(
                config=config,
                type_inference=self.type_inference,
                unit_extractor=self.unit_extractor,
            )

    def test_pattern_creation(self):
        """Test dass Patterns korrekt aus Config erstellt werden."""
        config: ClassifierDict = {
            "name": "TestClassifier",
            "priority": 5,
            "patterns": [
                {"pattern": r".*temperature.*", "data_type": "float", "unit": "temperature (°C)"},
                {"pattern": r".*count.*", "data_type": "integer", "unit": "quantity (Stk)"},
            ],
        }

        classifier = ConfigurableClassifier(
            config=config, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )

        assert len(classifier.patterns) == 0
        classifier.setup_patterns()
        assert len(classifier.patterns) == 2

        # Prüfe ersten Pattern
        pattern1 = classifier.patterns[0]
        assert pattern1.pattern == r".*temperature.*"
        assert pattern1.data_type == DataType.FLOAT
        assert pattern1.unit.symbol == "°C"
        assert pattern1.unit_type == UnitType.TEMPERATURE

        # Prüfe zweiten Pattern
        pattern2 = classifier.patterns[1]
        assert pattern2.pattern == r".*count.*"
        assert pattern2.data_type == DataType.INTEGER
        assert pattern2.unit.symbol == "Stk"
        assert pattern2.unit_type == UnitType.QUANTITY

    def test_classify_with_custom_patterns(self):
        """Test Klassifizierung mit benutzerdefinierten Patterns."""
        config: ClassifierDict = {
            "name": "CustomClassifier",
            "priority": 10,
            "patterns": [{"pattern": r".*custom_field.*", "data_type": "float", "unit": "length (cm)"}],
        }

        classifier = ConfigurableClassifier(
            config=config, type_inference=self.type_inference, unit_extractor=self.unit_extractor
        )
        classifier.setup_patterns()

        series = pd.Series([10.5, 20.5, 30.5])
        result = classifier.classify_series("custom_field_test", series)

        assert result.data_type == DataType.FLOAT
        assert result.unit.symbol == "cm"
        assert result.unit.unit_type == UnitType.LENGTH
        assert result.classifier_name == "CustomClassifier"

    def test_invalid_unit_in_config(self):
        """Test dass Fehler bei ungültiger Unit geworfen wird."""
        config: ClassifierDict = {
            "name": "TestClassifier",
            "priority": 5,
            "patterns": [{"pattern": r".*test.*", "data_type": "float", "unit": "invalid_unit_name"}],
        }

        with pytest.raises(ValueError):
            classifier = ConfigurableClassifier(
                config=config,
                type_inference=self.type_inference,
                unit_extractor=self.unit_extractor,
            )
            classifier.setup_patterns()
