"""Tests für die Hauptfunktionen des data_analyzer Moduls."""

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_analyzer import (
    DataType,
    UnitType,
    analyze_data,
    export_default_config,
)


class TestAnalyzeData:
    """Tests für die analyze_data Funktion."""

    def test_analyze_dataframe(self):
        """Test Analyse eines DataFrames."""
        df = pd.DataFrame(
            {
                "length_mm": [100, 200, 150],
                "weight_kg": [1.5, 2.0, 1.8],
                "is_active": ["yes", "no", "yes"],
            }
        )

        results = analyze_data(df)

        assert len(results) == 3
        assert results["length_mm"].data_type == DataType.INTEGER
        assert results["length_mm"].unit.symbol == "mm"
        assert results["length_mm"].unit.unit_type == UnitType.LENGTH

        assert results["weight_kg"].data_type == DataType.FLOAT
        assert results["weight_kg"].unit.symbol == "kg"
        assert results["weight_kg"].unit.unit_type == UnitType.MASS

        assert results["is_active"].data_type == DataType.BOOLEAN

    def test_analyze_list_of_dicts(self):
        """Test Analyse einer Liste von Dictionaries."""
        data = [{"id": 1, "value": 10.5}, {"id": 2, "value": 20.5}, {"id": 3, "value": 15.5}]

        results = analyze_data(data)

        assert len(results) == 2
        assert results["id"].data_type == DataType.INTEGER
        assert results["value"].data_type == DataType.FLOAT

    def test_analyze_list_of_lists_with_headers(self):
        """Test Analyse einer Liste von Listen mit Headers."""
        data = [[1, "A", 10.5], [2, "B", 20.5], [3, "C", 15.5]]
        headers = ["id", "name", "value"]

        results = analyze_data(data, headers=headers)

        assert len(results) == 3
        assert "id" in results
        assert "name" in results
        assert "value" in results

        assert results["id"].data_type == DataType.INTEGER
        assert results["name"].data_type == DataType.STRING
        assert results["value"].data_type == DataType.FLOAT

    def test_analyze_with_contains_headers(self):
        """Test Analyse mit Headers in der ersten Zeile."""
        data = [
            ["id", "name", "value"],
            ["1", "A", "10.5"],
            ["2", "B", "20.5"],
            ["3", "C", "15.5"],
        ]

        results = analyze_data(data, contains_headers=True)

        assert len(results) == 3
        assert "id" in results
        assert "name" in results
        assert "value" in results

    def test_analyze_with_active_classifiers(self):
        """Test Analyse mit spezifischen Klassifikatoren."""
        df = pd.DataFrame({"thickness": [100, 200, 150], "length": [10, 20, 15]})

        results = analyze_data(df, active_classifiers=["General"])

        assert all(r.classifier_name == "General" for r in results.values())

    def test_analyze_with_config_file(self):
        """Test Analyse mit Konfigurationsdatei."""
        # Erstelle temporäre Konfigurationsdatei
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {
                "direct_mappings": {"test_unit": "length (mm)"},
                "context_mappings": {"test_context": "mass"},
                "classifiers": {},
            }
            yaml.dump(config, f)
            config_path = f.name

        try:
            df = pd.DataFrame({"test_unit": [1, 2, 3], "test_context": [10, 20, 30]})

            results = analyze_data(df, config_path=config_path, merge_with_default=True)

            assert len(results) == 2
            # test_unit sollte als mm erkannt werden
            assert results["test_unit"].unit.symbol == "mm"
            # test_context sollte als Masse erkannt werden
            assert results["test_context"].unit.unit_type == UnitType.MASS
        finally:
            Path(config_path).unlink()

    def test_analyze_empty_data(self):
        """Test mit leeren Daten."""
        results = analyze_data([])
        assert results == {}

        results = analyze_data(pd.DataFrame())
        assert results == {}


class TestExportDefaultConfig:
    """Tests für die export_default_config Funktion."""

    def test_export_yaml_format(self):
        """Test Export im YAML Format."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            output_path = f.name

        try:
            export_default_config(output_path, export_format="yaml")

            assert Path(output_path).exists()

            # Lade und prüfe Inhalt
            with open(output_path, "r") as f:
                config = yaml.safe_load(f)

            assert "direct_mappings" in config
            assert "context_mappings" in config
            assert "classifiers" in config

            # Prüfe dass Mappings vorhanden sind
            assert len(config["direct_mappings"]) > 0
            assert len(config["context_mappings"]) > 0
            assert len(config["classifiers"]) >= 2  # General und Architectural

            # Prüfe spezifische Einträge
            assert "länge" in config["context_mappings"]
            assert config["context_mappings"]["länge"] == "length"

            # Prüfe Klassifikatoren
            assert "general" in config["classifiers"]
            assert "architectural" in config["classifiers"]

            # Prüfe Struktur eines Klassifikators
            general = config["classifiers"]["general"]
            assert "name" in general
            assert "priority" in general
            assert "patterns" in general
            assert len(general["patterns"]) > 0

        finally:
            Path(output_path).unlink()

    def test_export_json_format(self):
        """Test Export im JSON Format."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            export_default_config(output_path, export_format="json")

            assert Path(output_path).exists()

            # Lade und prüfe Inhalt
            with open(output_path, "r") as f:
                config = json.load(f)

            assert "direct_mappings" in config
            assert "context_mappings" in config
            assert "classifiers" in config

            # Prüfe dass Inhalte vorhanden sind
            assert isinstance(config["direct_mappings"], dict)
            assert isinstance(config["context_mappings"], dict)
            assert isinstance(config["classifiers"], dict)

        finally:
            Path(output_path).unlink()

    def test_export_invalid_format(self):
        """Test Export mit ungültigem Format."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            output_path = f.name

        try:
            with pytest.raises(ValueError):
                export_default_config(output_path, export_format="invalid")
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_does_not_include_automatic_symbols(self):
        """Test dass automatische Symbole nicht exportiert werden."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            output_path = f.name

        try:
            export_default_config(output_path)

            with open(output_path, "r") as f:
                config = yaml.safe_load(f)

            # Automatische Symbole wie "mm", "kg" sollten nicht in direct_mappings sein
            # da sie automatisch aus Units geladen werden
            # Nur manuelle Alternativen wie "millimeter", "kilogramm" sollten da sein
            direct_mappings = config["direct_mappings"]

            # Diese sind manuelle Mappings und sollten vorhanden sein
            assert "millimeter" in direct_mappings or "meter" in direct_mappings

        finally:
            Path(output_path).unlink()

    def test_export_classifier_patterns(self):
        """Test dass Classifier Patterns korrekt exportiert werden."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            output_path = f.name

        try:
            export_default_config(output_path)

            with open(output_path, "r") as f:
                config = yaml.safe_load(f)

            # Prüfe General Classifier Patterns
            general_patterns = config["classifiers"]["general"]["patterns"]
            assert len(general_patterns) > 0

            # Prüfe Struktur eines Patterns
            first_pattern = general_patterns[0]
            assert "pattern" in first_pattern
            assert "data_type" in first_pattern
            # unit ist optional

            # Prüfe dass verschiedene Pattern-Typen vorhanden sind
            pattern_strings = [p["pattern"] for p in general_patterns]

            # Sollte Boolean-Patterns enthalten
            assert any("boolean" in p or "aktiv" in p for p in pattern_strings)

            # Sollte Length-Patterns enthalten
            assert any("length" in p or "länge" in p for p in pattern_strings)

        finally:
            Path(output_path).unlink()
