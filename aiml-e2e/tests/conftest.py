"""Shared fixtures: one synthetic model, trained and saved once per test session."""

from pathlib import Path

import pytest

from northwind_loans import registry, train
from tests.test_train import make_processed


@pytest.fixture(scope="session")
def trained_model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Train on synthetic data and save one model into a temporary folder."""
    data_dir = tmp_path_factory.mktemp("processed")
    model_dir = tmp_path_factory.mktemp("models")
    make_processed().to_parquet(data_dir / "part.parquet", index=False)
    pipeline, report = train.train_and_evaluate(data_dir)
    registry.save_model(pipeline, train.build_metadata(report, pipeline), model_dir)
    return model_dir
