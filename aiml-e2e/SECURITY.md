# Security Policy

This is an **educational project with synthetic data**. It is not intended for
production use or real credit decisions.

## Reporting a vulnerability
Please do **not** open a public issue. Contact the maintainer privately
(via the repository owner's profile) with:
- a description of the issue and its impact,
- steps to reproduce.

You can expect an acknowledgement within a few working days.

## Model files (pickle)
- **Pickle files execute code when loaded. Only load model files you created yourself.**
- Each `models/loan_offer_model_vN.pkl` has a `vN.json` with the pickle's SHA-256 and an
  HMAC-SHA256 signature of the metadata. `registry.load_model()` verifies both **before**
  unpickling and refuses mismatches.
- The signature is only as safe as `MODEL_SIGNING_KEY` (set in `.env`, never committed).
  If the default key is used, a warning is logged.

## Good practices in this repo
- Secrets and local settings go in `.env`, which is git-ignored. Only `.env.example`
  (no secrets) is committed.
- Dependencies are pinned to exact versions in `pyproject.toml`.
- Never commit real personal or financial data.
