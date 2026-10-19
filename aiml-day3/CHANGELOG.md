# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For this kit, a **major** version changes the data in a way that alters expected lab results, a **minor** version adds datasets or materials, and a **patch** fixes documentation or tooling without touching the numbers.

## [Unreleased]

## [1.0.0] - 2026-10-14

### Added

- Day 3 datasets: `renewals_day3.csv` (795 closed FY26 renewals, 615 renewed, missing values retained for in-pipeline imputation) and `open_renewals.csv` (412 open renewals).
- Day 1 datasets for reference: `accounts.csv`, `subscriptions.csv`, `monthly_usage.csv`, `renewal_pipeline_extract.txt`, `pricing_rules.json`.
- Day 2 datasets for reference: `renewals_raw_extract.csv`, `usage_raw_monthly.csv`.
- `requirements.txt` for local setup (numpy, pandas, matplotlib, seaborn, scipy, scikit-learn, jupyterlab).
- Project documentation: README, MIT license, contributing guide, code of conduct, security policy and this changelog.
- `.gitignore` excluding the local `.temp/` working folder, virtual environments, notebook checkpoints and generated model files.

[Unreleased]: https://github.com/OWNER/REPO/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/OWNER/REPO/releases/tag/v1.0.0
