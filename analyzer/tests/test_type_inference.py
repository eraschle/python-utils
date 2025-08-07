"""Tests für die TypeInference Klasse."""

import pandas as pd

from data_analyzer import DataType, TypeInference


class TestTypeInference:
    """Tests für die TypeInference Klasse."""

    def setup_method(self):
        """Setup für jeden Test."""
        self.inference = TypeInference()

    def test_initialization_default(self):
        """Test Standard-Initialisierung."""
        assert self.inference.boolean_values is not None
        assert self.inference.numeric_threshold == 0.9
        assert "true" in self.inference.boolean_values
        assert "false" in self.inference.boolean_values
        assert "yes" in self.inference.boolean_values
        assert "no" in self.inference.boolean_values

    def test_initialization_custom(self):
        """Test Initialisierung mit benutzerdefinierten Werten."""
        custom_bools = {"on", "off"}
        custom_threshold = 0.8
        inference = TypeInference(boolean_values=custom_bools, numeric_threshold=custom_threshold)

        assert inference.boolean_values == custom_bools
        assert inference.numeric_threshold == 0.8

    def test_infer_type_boolean(self):
        """Test Erkennung von Boolean-Typen."""
        # Englische Boolean-Werte
        series = pd.Series(["true", "false", "true", "false"])
        assert self.inference.infer_type("column", series) == DataType.BOOLEAN

        series = pd.Series(["yes", "no", "yes", "no"])
        assert self.inference.infer_type("column", series) == DataType.BOOLEAN

        # Deutsche Boolean-Werte
        series = pd.Series(["ja", "nein", "ja", "nein"])
        assert self.inference.infer_type("column", series) == DataType.BOOLEAN

        # Numerische Boolean-Werte
        series = pd.Series(["1", "0", "1", "0"])
        assert self.inference.infer_type("column", series) == DataType.BOOLEAN

        # Technische Boolean-Werte
        series = pd.Series(["enabled", "disabled", "enabled"])
        assert self.inference.infer_type("column", series) == DataType.BOOLEAN

        series = pd.Series(["on", "off", "on", "off"])
        assert self.inference.infer_type("column", series) == DataType.BOOLEAN

    def test_infer_type_integer(self):
        """Test Erkennung von Integer-Typen."""
        # Reine Integer
        series = pd.Series([1, 2, 3, 4, 5])
        assert self.inference.infer_type("column", series) == DataType.INTEGER

        # Integer als Strings
        series = pd.Series(["1", "2", "3", "4", "5"])
        assert self.inference.infer_type("column", series) == DataType.INTEGER

        # Große Integer
        series = pd.Series([1000, 2000, 3000, 4000])
        assert self.inference.infer_type("column", series) == DataType.INTEGER

        # Negative Integer
        series = pd.Series([-1, -2, -3, -4])
        assert self.inference.infer_type("column", series) == DataType.INTEGER

    def test_infer_type_float(self):
        """Test Erkennung von Float-Typen."""
        # Reine Floats
        series = pd.Series([1.5, 2.5, 3.5, 4.5])
        assert self.inference.infer_type("column", series) == DataType.FLOAT

        # Floats als Strings
        series = pd.Series(["1.5", "2.5", "3.5", "4.5"])
        assert self.inference.infer_type("column", series) == DataType.FLOAT

        # Gemischte Integer und Floats
        series = pd.Series([1, 2.5, 3, 4.5])
        assert self.inference.infer_type("column", series) == DataType.FLOAT

        # Wissenschaftliche Notation
        series = pd.Series(["1.5e-3", "2.5e-3", "3.5e-3"])
        assert self.inference.infer_type("column", series) == DataType.FLOAT

    def test_infer_type_string(self):
        """Test Erkennung von String-Typen."""
        # Reine Strings
        series = pd.Series(["hello", "world", "test"])
        assert self.inference.infer_type("column", series) == DataType.STRING

        # Gemischte Inhalte
        series = pd.Series(["text", "123", "test"])
        assert self.inference.infer_type("column", series) == DataType.STRING

        # Lange Strings
        series = pd.Series(["This is a long text", "Another long text"])
        assert self.inference.infer_type("column", series) == DataType.STRING

    def test_infer_type_with_nulls(self):
        """Test Typerkennung mit Null-Werten."""
        # Integer mit Nulls
        series = pd.Series([1, 2, None, 4, 5])
        self.inference.clear_cache()
        assert self.inference.infer_type("int_column", series) == DataType.INTEGER

        # Float mit Nulls
        self.inference.clear_cache()
        series = pd.Series([1.5, None, 3.5, 4.5])
        assert self.inference.infer_type("float_column", series) == DataType.FLOAT

        # String mit Nulls
        self.inference.clear_cache()
        series = pd.Series(["hello", None, "world"])
        assert self.inference.infer_type("str_column", series) == DataType.STRING

        # Boolean mit Nulls
        self.inference.clear_cache()
        series = pd.Series(["true", None, "false"])
        assert self.inference.infer_type("column", series) == DataType.BOOLEAN

    def test_infer_type_empty_series(self):
        """Test mit leerer Series."""
        series = pd.Series([])
        assert self.inference.infer_type("column", series) == DataType.UNKNOWN

        # Series nur mit Nulls
        series = pd.Series([None, None, None])
        assert self.inference.infer_type("column", series) == DataType.UNKNOWN

    def test_numeric_threshold(self):
        """Test die numeric_threshold Funktionalität."""
        # Mit Standard-Threshold (0.9)
        # 90% numerisch, 10% Text -> sollte numerisch sein
        self.inference.clear_cache()
        series = pd.Series(["1", "2", "3", "4", "5", "6", "7", "8", "9", "text"])
        assert self.inference.infer_type("str_col", series) == DataType.INTEGER, series

        # 80% numerisch, 20% Text -> sollte String sein
        self.inference.clear_cache()
        series = pd.Series(["1", "2", "3", "4", "text1", "text2"])
        result = self.inference.infer_type("str_col2", series)
        assert result == DataType.STRING, series

        # Mit niedrigerem Threshold
        self.inference.clear_cache()
        inference_low = TypeInference(numeric_threshold=0.7)
        series = pd.Series(["1", "2", "3", "4", "text1", "text2"])
        result = inference_low.infer_type("str_col", series)
        # 4/6 = 0.66 < 0.7, also immer noch String
        assert result == DataType.STRING

        self.inference.clear_cache()
        series = pd.Series(["1", "2", "3", "4", "5", "text1", "text2"])
        result = inference_low.infer_type("int_col", series)
        # 5/7 = 0.71 > 0.7, also Integer
        assert result == DataType.INTEGER

    def test_case_insensitive_boolean(self):
        """Test dass Boolean-Erkennung case-insensitive ist."""
        # Test verschiedene Schreibweisen von Boolean-Werten
        series = pd.Series(["TRUE", "FALSE", "True", "False"])
        assert self.inference.infer_type("bool_col", series) == DataType.BOOLEAN

        series = pd.Series(["YES", "NO", "yes", "no"])
        assert self.inference.infer_type("bool_col2", series) == DataType.BOOLEAN

        series = pd.Series(["ON", "OFF", "on", "off"])
        assert self.inference.infer_type("bool_col3", series) == DataType.BOOLEAN

    def test_mixed_numeric_types(self):
        """Test mit gemischten numerischen Typen."""
        # Integer und Float gemischt
        series = pd.Series([1, 2.0, 3, 4.0])
        assert self.inference.infer_type("float_col", series) == DataType.FLOAT

        series = pd.Series([1, 2.5, 3, 4.5])
        assert self.inference.infer_type("float_col", series) == DataType.FLOAT

    def test_special_numeric_values(self):
        """Test mit speziellen numerischen Werten."""
        # Mit Null
        series = pd.Series([0, 1, 2, 3])
        assert self.inference.infer_type("int_col", series) == DataType.INTEGER

        # Mit negativen Werten
        series = pd.Series([-1.5, -0.5, 0.5, 1.5])
        assert self.inference.infer_type("float_col", series) == DataType.FLOAT

    def test_dataframe_compatibility(self):
        """Test dass TypeInference mit DataFrame-Spalten funktioniert."""
        df = pd.DataFrame(
            {
                "int_col": [1, 2, 3],
                "float_col": [1.5, 2.5, 3.5],
                "string_col": ["a", "b", "c"],
                "bool_col": ["yes", "no", "yes"],
            }
        )

        assert self.inference.infer_type("int_col", df["int_col"]) == DataType.INTEGER  # type: ignore[reportArgumentType]
        assert self.inference.infer_type("float_col", df["float_col"]) == DataType.FLOAT  # type: ignore[reportArgumentType]
        assert self.inference.infer_type("string_col", df["string_col"]) == DataType.STRING  # type: ignore[reportArgumentType]
        assert self.inference.infer_type("bool_col", df["bool_col"]) == DataType.BOOLEAN  # type: ignore[reportArgumentType]
