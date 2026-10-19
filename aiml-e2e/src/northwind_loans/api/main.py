"""FastAPI service for Northwind loan offers.

At import, ONLY the latest metadata JSON is read (for the app title/version).
The pickle is loaded once, in the lifespan handler, into app.state.predictor.
Observability (JSON logs, request ids, Prometheus metrics, audit log) is wired
in from northwind_loans.api.observability.

Run:     python -m northwind_loans.api      (or: make serve)
Docs:    http://127.0.0.1:8000/docs
Metrics: http://127.0.0.1:8000/metrics
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import get_args

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from northwind_loans import registry
from northwind_loans.api import observability as obs
from northwind_loans.api.schemas import ApplicantIn, BatchIn, BatchOut, OfferOut
from northwind_loans.config import MODEL_DIR, PREDICTION_LOG
from northwind_loans.predict import LoanOfferPredictor

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Predicts the maximum loan amount (INR) Northwind Finance can offer an applicant.\n\n"
    "**Educational demonstration on synthetic data. Northwind Finance is fictional. "
    "NEVER use this API for real credit decisions.**"
)

REQUEST_ID_HEADER = "X-Request-ID"
UNTRACKED_PATHS = {"/metrics"}  # Prometheus scrapes are not counted or logged

# Keys of the metadata shown by GET /model-info (no reference profile, no signature)
MODEL_INFO_KEYS: list[str] = [
    "model_name", "version", "created_at", "sklearn_version", "model_sha256", "metrics",
    "raw_input_columns", "model_feature_columns", "excluded_features", "credit_policy",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create ONE predictor at startup; keep the app alive (not ready) if loading fails."""
    try:
        app.state.predictor = LoanOfferPredictor(model_dir=app.state.model_dir)
        app.state.load_error = None
        obs.set_model_gauges(app.state.predictor.metadata)
    except (FileNotFoundError, ValueError) as error:
        logger.error("Model not loaded: %s", error)
        app.state.predictor = None
        app.state.load_error = str(error)
    yield


def get_predictor(request: Request) -> LoanOfferPredictor:
    """The loaded predictor, or HTTP 503 if the model is not available."""
    predictor = request.app.state.predictor
    if predictor is None:
        raise HTTPException(status_code=503, detail=f"model not ready: {request.app.state.load_error}")
    return predictor


def _endpoint_label(request: Request) -> str:
    """Route template (e.g. '/predict') - keeps metric label values few."""
    route = request.scope.get("route")
    return getattr(route, "path", "unmatched")


def _model_version(request: Request) -> int | None:
    predictor = request.app.state.predictor
    return predictor.model_version if predictor else None


def create_app(model_dir: Path = MODEL_DIR, prediction_log: Path = PREDICTION_LOG) -> FastAPI:
    """Build the FastAPI app for the models in model_dir."""
    try:
        metadata = registry.load_metadata(model_dir=model_dir)  # JSON only, no unpickling
        title = f"Northwind Loan Offer API - {metadata['model_name']}"
        version = str(metadata["version"])
    except (FileNotFoundError, ValueError):
        title, version = "Northwind Loan Offer API - no model", "0"

    app = FastAPI(title=title, version=version, description=DESCRIPTION, lifespan=lifespan)
    obs.init_label_series(
        loan_purposes=list(get_args(ApplicantIn.model_fields["loan_purpose"].annotation)),
        fields=list(ApplicantIn.model_fields),
    )
    app.state.model_dir = model_dir
    app.state.prediction_log = prediction_log
    app.state.predictor = None
    app.state.load_error = "not started"

    @app.middleware("http")
    async def observe_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Request id, timing, request metrics and one JSON log line per request."""
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        if request.url.path in UNTRACKED_PATHS:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response

        obs.REQUESTS_IN_PROGRESS.inc()
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration = time.perf_counter() - start
            obs.REQUESTS_IN_PROGRESS.dec()
            endpoint = _endpoint_label(request)
            obs.record_request(request.method, endpoint, status_code, duration)
            obs.log_request(request_id, request.method, request.url.path, endpoint,
                            status_code, duration * 1000, _model_version(request))

    @app.exception_handler(RequestValidationError)
    async def count_validation_errors(request: Request, exc: RequestValidationError) -> Response:
        """Count 422s by field, then return FastAPI's normal 422 body."""
        obs.record_validation_errors(exc.errors())
        return await request_validation_exception_handler(request, exc)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        """Liveness: the process is up."""
        return {"status": "ok"}

    @app.get("/ready", tags=["ops"])
    def ready(request: Request) -> JSONResponse:
        """Readiness: the model is loaded and can serve predictions."""
        predictor = request.app.state.predictor
        if predictor is None:
            return JSONResponse(
                status_code=503,
                content={"status": "not ready", "reason": request.app.state.load_error},
            )
        return JSONResponse({"status": "ready", "model_version": predictor.model_version})

    @app.get("/model-info", tags=["ops"])
    def model_info(request: Request) -> dict:
        """Summary of the loaded model's metadata."""
        metadata = get_predictor(request).metadata
        return {key: metadata[key] for key in MODEL_INFO_KEYS if key in metadata}

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        """Prometheus metrics."""
        return obs.metrics_response()

    def score(request: Request, records: list[dict], endpoint: str) -> list[dict]:
        """Predict, update model metrics and write the audit log."""
        predictor = get_predictor(request)
        results = predictor.predict_records(records)
        obs.record_predictions(records, results)
        obs.log_predictions(request.app.state.prediction_log, request.state.request_id,
                            endpoint, predictor.model_version, records, results)
        return results

    @app.post("/predict", response_model=OfferOut, tags=["predict"])
    def predict(applicant: ApplicantIn, request: Request) -> dict:
        """Loan offer for one applicant."""
        return score(request, [applicant.model_dump()], "/predict")[0]

    @app.post("/predict/batch", response_model=BatchOut, tags=["predict"])
    def predict_batch(batch: BatchIn, request: Request) -> dict:
        """Loan offers for 1..1000 applicants, in request order."""
        records = [applicant.model_dump() for applicant in batch.applicants]
        return {"results": score(request, records, "/predict/batch")}

    return app


app = create_app()
