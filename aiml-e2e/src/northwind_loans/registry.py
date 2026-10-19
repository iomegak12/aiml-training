"""Versioned model registry: save / load pickled pipelines with signed metadata.

WARNING: pickle files EXECUTE CODE when they are loaded. ONLY LOAD FILES YOU
HAVE CREATED. load_model() verifies the metadata signature (HMAC-SHA256 with
MODEL_SIGNING_KEY) and the pickle's SHA-256 BEFORE unpickling, and refuses
files that do not match - but this only helps if the signing key is secret.

Files:  models/loan_offer_model_v1.pkl  + models/loan_offer_model_v1.json
        models/loan_offer_model_v2.pkl  + ...

Usage (list saved models):
    python -m northwind_loans.registry
"""

import hashlib
import hmac
import json
import logging
import pickle
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

import sklearn
from sklearn.pipeline import Pipeline

from northwind_loans.config import (
    DEFAULT_SIGNING_KEY,
    LOG_LEVEL,
    MODEL_DIR,
    MODEL_NAME,
    MODEL_SIGNING_KEY,
)

logger = logging.getLogger(__name__)

_VERSION_PATTERN = re.compile(rf"^{MODEL_NAME}_v(\d+)\.pkl$")


# --------------------------------------------------------------------------
# Versions and paths
# --------------------------------------------------------------------------
def list_versions(model_dir: Path = MODEL_DIR) -> list[int]:
    """Sorted version numbers of the saved models."""
    versions = []
    for path in model_dir.glob(f"{MODEL_NAME}_v*.pkl"):
        match = _VERSION_PATTERN.match(path.name)
        if match:
            versions.append(int(match.group(1)))
    return sorted(versions)


def model_path(version: int, model_dir: Path = MODEL_DIR) -> Path:
    """Path of the pickle file for a version."""
    return model_dir / f"{MODEL_NAME}_v{version}.pkl"


def metadata_path(version: int, model_dir: Path = MODEL_DIR) -> Path:
    """Path of the metadata JSON for a version."""
    return model_dir / f"{MODEL_NAME}_v{version}.json"


# --------------------------------------------------------------------------
# Hashing and signing
# --------------------------------------------------------------------------
def file_sha256(path: Path) -> str:
    """SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(metadata: dict) -> bytes:
    """Stable JSON bytes of the metadata without its signature."""
    unsigned = {key: value for key, value in metadata.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_metadata(metadata: dict) -> str:
    """HMAC-SHA256 signature of the metadata (excluding the signature field)."""
    if MODEL_SIGNING_KEY == DEFAULT_SIGNING_KEY:
        logger.warning("Using the default MODEL_SIGNING_KEY - set your own in .env")
    key = MODEL_SIGNING_KEY.encode("utf-8")
    return hmac.new(key, _canonical_json(metadata), hashlib.sha256).hexdigest()


def verify_metadata(metadata: dict) -> bool:
    """True if the metadata signature is valid."""
    return hmac.compare_digest(sign_metadata(metadata), str(metadata.get("signature", "")))


# --------------------------------------------------------------------------
# Save / load
# --------------------------------------------------------------------------
def save_model(pipeline: Pipeline, metadata: dict, model_dir: Path = MODEL_DIR) -> dict:
    """Pickle the pipeline as the next version and write its signed metadata.

    Returns {model_name, version, model_path, metadata_path, model_sha256}.
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    versions = list_versions(model_dir)
    version = versions[-1] + 1 if versions else 1

    pkl_path = model_path(version, model_dir)
    with pkl_path.open("wb") as file:
        pickle.dump(pipeline, file, protocol=pickle.HIGHEST_PROTOCOL)
    sha = file_sha256(pkl_path)

    full_metadata = {
        "model_name": MODEL_NAME,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "pickle_protocol": pickle.HIGHEST_PROTOCOL,
        "model_file": pkl_path.name,
        "model_sha256": sha,
        **metadata,
    }
    # Round-trip through JSON so we sign exactly what will be stored on disk.
    full_metadata = json.loads(json.dumps(full_metadata))
    full_metadata["signature"] = sign_metadata(full_metadata)

    json_path = metadata_path(version, model_dir)
    json_path.write_text(json.dumps(full_metadata, indent=2), encoding="utf-8")
    logger.info("Saved %s v%s to %s", MODEL_NAME, version, pkl_path)
    return {
        "model_name": MODEL_NAME,
        "version": version,
        "model_path": str(pkl_path),
        "metadata_path": str(json_path),
        "model_sha256": sha,
    }


def _resolve_version(version: int | None, model_dir: Path) -> int:
    """The given version, or the highest saved version if None."""
    if version is not None:
        return version
    versions = list_versions(model_dir)
    if not versions:
        raise FileNotFoundError(f"no saved models in {model_dir} - run `make train` first")
    return versions[-1]


def load_metadata(version: int | None = None, model_dir: Path = MODEL_DIR) -> dict:
    """Read and verify a version's metadata JSON only - the pickle is NOT loaded."""
    version = _resolve_version(version, model_dir)
    metadata = json.loads(metadata_path(version, model_dir).read_text(encoding="utf-8"))
    if not verify_metadata(metadata):
        raise ValueError(f"metadata signature mismatch for v{version} - file was altered")
    return metadata


def load_model(version: int | None = None, model_dir: Path = MODEL_DIR) -> tuple[Pipeline, dict]:
    """Load a pipeline and its metadata (default: the highest version).

    Raises ValueError if the metadata signature or the pickle hash do not match.
    """
    version = _resolve_version(version, model_dir)
    metadata = load_metadata(version, model_dir)

    pkl_path = model_path(version, model_dir)
    if file_sha256(pkl_path) != metadata["model_sha256"]:
        raise ValueError(f"model file hash mismatch for v{version} - refusing to unpickle")

    if metadata["sklearn_version"] != sklearn.__version__:
        logger.warning(
            "Model v%s was trained with scikit-learn %s but %s is installed",
            version, metadata["sklearn_version"], sklearn.__version__,
        )

    with pkl_path.open("rb") as file:
        pipeline = pickle.load(file)  # safe only because hash + signature were verified
    logger.info("Loaded %s v%s", MODEL_NAME, version)
    return pipeline, metadata


def list_models(model_dir: Path = MODEL_DIR) -> list[dict]:
    """Summary of every saved model: version, file, size and key metrics."""
    rows = []
    for version in list_versions(model_dir):
        metadata = json.loads(metadata_path(version, model_dir).read_text(encoding="utf-8"))
        test = metadata.get("metrics", {}).get("test", {})
        rows.append({
            "version": version,
            "file": metadata["model_file"],
            "size_kb": round(model_path(version, model_dir).stat().st_size / 1024, 1),
            "created_at": metadata["created_at"],
            "sklearn_version": metadata["sklearn_version"],
            "test_r2": test.get("r2"),
            "test_rmse": test.get("rmse"),
            "signature_ok": verify_metadata(metadata),
        })
    return rows


def main() -> None:
    """Print the saved models."""
    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    rows = list_models()
    if not rows:
        print(f"No models in {MODEL_DIR} - run `make train`.")
        return
    print(f"{'ver':<5}{'file':<28}{'size KB':>9}  {'created (UTC)':<27}"
          f"{'sklearn':<9}{'test R2':>8}{'test RMSE':>12}  signed")
    for r in rows:
        print(f"v{r['version']:<4}{r['file']:<28}{r['size_kb']:>9,.1f}  {r['created_at']:<27}"
              f"{r['sklearn_version']:<9}{r['test_r2']:>8.4f}{r['test_rmse']:>12,.0f}  "
              f"{'OK' if r['signature_ok'] else 'INVALID'}")


if __name__ == "__main__":
    main()
