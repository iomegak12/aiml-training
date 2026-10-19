"""Tests for saving, loading and verifying models in the registry."""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from northwind_loans import registry


def make_pipeline() -> tuple[Pipeline, pd.DataFrame]:
    X = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [0.5, 0.1, 0.9, 0.3]})
    y = 2 * X["a"] + X["b"]
    return Pipeline([("scale", StandardScaler()), ("model", LinearRegression())]).fit(X, y), X


METADATA = {"metrics": {"test": {"r2": 0.99, "rmse": 1.0}}}


def test_versions_increment_and_latest_is_default(tmp_path: Path) -> None:
    pipe, X = make_pipeline()
    first = registry.save_model(pipe, METADATA, tmp_path)
    second = registry.save_model(pipe, METADATA, tmp_path)
    assert (first["version"], second["version"]) == (1, 2)
    assert registry.list_versions(tmp_path) == [1, 2]
    assert Path(second["model_path"]).name == "loan_offer_model_v2.pkl"

    loaded, metadata = registry.load_model(model_dir=tmp_path)
    assert metadata["version"] == 2
    assert registry.load_model(1, tmp_path)[1]["version"] == 1
    assert np.array_equal(loaded.predict(X), pipe.predict(X))


def test_metadata_fields_and_listing(tmp_path: Path) -> None:
    pipe, _ = make_pipeline()
    registry.save_model(pipe, METADATA, tmp_path)
    metadata = json.loads(registry.metadata_path(1, tmp_path).read_text(encoding="utf-8"))
    for key in ("model_name", "version", "created_at", "sklearn_version",
                "model_sha256", "signature", "metrics"):
        assert key in metadata
    assert metadata["model_sha256"] == registry.file_sha256(registry.model_path(1, tmp_path))
    rows = registry.list_models(tmp_path)
    assert rows[0]["version"] == 1 and rows[0]["signature_ok"] and rows[0]["size_kb"] > 0


def test_edited_metadata_is_refused(tmp_path: Path) -> None:
    pipe, _ = make_pipeline()
    registry.save_model(pipe, METADATA, tmp_path)
    path = registry.metadata_path(1, tmp_path)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["metrics"]["test"]["r2"] = 1.0  # someone "improves" the metrics
    path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="signature mismatch"):
        registry.load_model(1, tmp_path)


def test_edited_pickle_is_refused_before_unpickling(tmp_path: Path) -> None:
    pipe, _ = make_pipeline()
    registry.save_model(pipe, METADATA, tmp_path)
    with registry.model_path(1, tmp_path).open("ab") as file:
        file.write(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        registry.load_model(1, tmp_path)


def test_sklearn_version_mismatch_logs_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    pipe, _ = make_pipeline()
    registry.save_model(pipe, METADATA, tmp_path)
    path = registry.metadata_path(1, tmp_path)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["sklearn_version"] = "0.0.1"
    metadata["signature"] = registry.sign_metadata(metadata)  # validly re-signed
    path.write_text(json.dumps(metadata), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="northwind_loans.registry"):
        registry.load_model(1, tmp_path)
    assert "trained with scikit-learn 0.0.1" in caplog.text


def test_load_without_models_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        registry.load_model(model_dir=tmp_path)
