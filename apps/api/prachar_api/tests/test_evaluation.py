"""Phase J tests — Prompt & Evaluation Framework.

Tests the evaluation framework: datasets, quality scorer, regression suite.
"""
from __future__ import annotations

import pytest

from prachar_api.runtime.evaluation import (
    CaseResult,
    EvaluationCase,
    QualityScorer,
    RegressionSuite,
    SuiteResult,
    create_default_datasets,
    export_datasets,
    import_datasets,
    get_regression_suite,
)


class TestEvaluationCase:
    """Evaluation case data model."""

    def test_case_to_dict(self):
        case = EvaluationCase(
            id="test_1",
            category="test",
            input={"key": "value"},
            expected_fields=["a", "b"],
            expected_min_quality=0.8,
            expected_types={"a": str},
            expected_contains={"a": "hello"},
            description="test case",
        )
        d = case.to_dict()
        assert d["id"] == "test_1"
        assert d["category"] == "test"
        assert d["expected_fields"] == ["a", "b"]
        assert d["expected_min_quality"] == 0.8
        assert d["expected_types"]["a"] == "str"
        assert d["expected_contains"]["a"] == "hello"

    def test_case_defaults(self):
        case = EvaluationCase()
        assert case.id == ""
        assert case.expected_fields == []
        assert case.expected_min_quality == 0.7


class TestQualityScorer:
    """Quality scorer — scores output against expected."""

    def test_perfect_score(self):
        case = EvaluationCase(
            expected_fields=["a", "b"],
            expected_types={"a": str, "b": list},
        )
        output = {"a": "hello world", "b": [1, 2, 3]}
        score, errors, warnings = QualityScorer.score(output, case)
        assert score == 1.0
        assert errors == []

    def test_missing_fields(self):
        case = EvaluationCase(
            expected_fields=["a", "b", "c"],
        )
        output = {"a": "test"}
        score, errors, _ = QualityScorer.score(output, case)
        assert score < 1.0
        assert any("Missing" in e for e in errors)

    def test_wrong_type(self):
        case = EvaluationCase(
            expected_fields=["a"],
            expected_types={"a": list},
        )
        output = {"a": "not a list"}
        score, errors, _ = QualityScorer.score(output, case)
        assert score < 1.0
        assert any("should be" in e for e in errors)

    def test_content_contains(self):
        case = EvaluationCase(
            expected_fields=["headline"],
            expected_contains={"headline": "sale"},
        )
        output = {"headline": "Summer Sale!"}
        score, _, _ = QualityScorer.score(output, case)
        assert score >= 0.8

    def test_content_missing(self):
        case = EvaluationCase(
            expected_fields=["headline"],
            expected_contains={"headline": "sale"},
        )
        output = {"headline": "Summer Special!"}
        score, _, warnings = QualityScorer.score(output, case)
        assert any("should contain" in w for w in warnings)

    def test_empty_fields_lower_score(self):
        case = EvaluationCase(
            expected_fields=["a", "b"],
            expected_types={"a": str, "b": str},
        )
        output = {"a": "", "b": ""}
        score, _, _ = QualityScorer.score(output, case)
        assert score <= 0.8  # empty fields reduce richness score

    def test_no_expected_fields_full_score(self):
        case = EvaluationCase()
        output = {"anything": "ok"}
        score, _, _ = QualityScorer.score(output, case)
        assert score == 1.0


class TestDatasets:
    """Default evaluation datasets."""

    def test_default_datasets_created(self):
        datasets = create_default_datasets()
        assert "campaign_brain" in datasets
        assert "creative_studio" in datasets
        assert "council" in datasets
        assert "performance" in datasets
        assert "artefacts" in datasets

    def test_campaign_brain_dataset(self):
        cases = create_default_datasets()["campaign_brain"]
        assert len(cases) >= 4
        categories = [c.category for c in cases]
        assert "campaign_brain.analyse" in categories
        assert "campaign_brain.strategy" in categories

    def test_creative_studio_dataset(self):
        cases = create_default_datasets()["creative_studio"]
        assert len(cases) >= 5
        # Check for intelligence fields (Phase I2)
        intelligence_case = next(c for c in cases if c.id == "cs_poster_intelligence")
        assert "rationale" in intelligence_case.expected_fields
        assert "brand_alignment" in intelligence_case.expected_fields

    def test_council_dataset(self):
        cases = create_default_datasets()["council"]
        assert len(cases) >= 2
        # Check for intelligence fields (Phase I3)
        decision_case = next(c for c in cases if c.id == "council_decision_fields")
        assert "agreement_score" in decision_case.expected_fields
        assert "disagreement_analysis" in decision_case.expected_fields

    def test_performance_dataset(self):
        cases = create_default_datasets()["performance"]
        assert len(cases) >= 4
        ids = [c.id for c in cases]
        assert "perf_explain" in ids
        assert "perf_recommend" in ids
        assert "perf_story" in ids
        assert "perf_forecast" in ids

    def test_artefact_dataset(self):
        cases = create_default_datasets()["artefacts"]
        assert len(cases) >= 4
        for case in cases:
            assert "artefacts" in case.expected_fields


class TestRegressionSuite:
    """Regression suite execution."""

    def test_suite_creation(self):
        suite = RegressionSuite()
        assert suite.total_cases > 0
        assert len(suite.datasets) >= 5

    def test_run_static(self):
        suite = RegressionSuite()
        result = suite.run_static()
        assert result.total > 0
        assert result.passed == result.total
        assert result.failed == 0
        assert result.avg_quality == 1.0

    def test_run_with_outputs_perfect(self):
        suite = RegressionSuite()
        # Build perfect outputs for each case
        outputs = {}
        for dataset_name, cases in suite.datasets.items():
            for case in cases:
                output = {}
                for field in case.expected_fields:
                    if field in case.expected_types:
                        t = case.expected_types[field]
                        if t == str:
                            output[field] = "test value that is long enough"
                        elif t == list:
                            output[field] = [1, 2, 3]
                        elif t == dict:
                            output[field] = {"key": "value"}
                        elif t == float:
                            output[field] = 1.0
                        elif t == int:
                            output[field] = 1
                    else:
                        output[field] = "test value"
                outputs[case.id] = output

        result = suite.run_with_outputs(outputs)
        assert result.total > 0
        assert result.passed == result.total
        assert result.avg_quality >= 0.9

    def test_run_with_outputs_failures(self):
        suite = RegressionSuite()
        # Empty outputs → all fail
        result = suite.run_with_outputs({})
        assert result.total > 0
        assert result.failed == result.total
        assert result.passed == 0

    def test_suite_result_summary(self):
        result = SuiteResult(total=10, passed=8, failed=2, avg_quality=0.85)
        summary = result.summary()
        assert "8/10" in summary
        assert "80.0%" in summary  # 8/10 = 80%
        assert "0.85" in summary

    def test_get_regression_suite_singleton(self):
        suite1 = get_regression_suite()
        suite2 = get_regression_suite()
        assert suite1 is suite2


class TestExportImport:
    """Dataset export and import."""

    def test_export_import_roundtrip(self, tmp_path):
        export_path = tmp_path / "datasets.json"
        export_datasets(str(export_path))
        assert export_path.exists()

        imported = import_datasets(str(export_path))
        assert "campaign_brain" in imported
        assert "creative_studio" in imported
        assert len(imported["campaign_brain"]) >= 4

    def test_import_preserves_case_structure(self, tmp_path):
        export_path = tmp_path / "datasets.json"
        export_datasets(str(export_path))
        imported = import_datasets(str(export_path))

        # Check a specific case
        cb_cases = imported["campaign_brain"]
        analyse_case = next(c for c in cb_cases if c.id == "cb_analyse_business")
        assert analyse_case.category == "campaign_brain.analyse"
        assert "business_profile" in analyse_case.expected_fields
        assert analyse_case.expected_types["business_profile"] == dict


class TestScoringEdgeCases:
    """Edge cases for the quality scorer."""

    def test_none_output(self):
        case = EvaluationCase(expected_fields=["a"])
        score, errors, _ = QualityScorer.score({}, case)
        assert score < 0.5
        assert len(errors) > 0

    def test_partial_fields(self):
        case = EvaluationCase(
            expected_fields=["a", "b", "c", "d"],
            expected_types={"a": str, "b": str, "c": str, "d": str},
        )
        output = {"a": "good value", "b": "another value"}
        score, errors, _ = QualityScorer.score(output, case)
        assert 0.3 < score < 0.7
        assert any("Missing" in e for e in errors)

    def test_rich_list_content(self):
        case = EvaluationCase(
            expected_fields=["items"],
            expected_types={"items": list},
        )
        output = {"items": [1, 2, 3, 4, 5]}
        score, _, _ = QualityScorer.score(output, case)
        assert score == 1.0

    def test_empty_list_reduces_score(self):
        case = EvaluationCase(
            expected_fields=["items"],
            expected_types={"items": list},
        )
        output = {"items": []}
        score, _, _ = QualityScorer.score(output, case)
        assert score < 1.0  # empty list reduces richness
