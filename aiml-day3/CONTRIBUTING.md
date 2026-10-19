# Contributing

Thanks for helping improve the Corvana Day 3 Kit. This repository is used in live training sessions, so the main rule is: **don't change the numbers participants see unless that is the point of the change.**

By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a problem**: a broken setup step, a library incompatibility, a typo, or a dataset value that contradicts the documentation.
- **Improve the docs**: clearer setup instructions, troubleshooting entries, or explanations.
- **Propose a data change**: new columns, fixes, or extra datasets. Open an issue first so we can discuss the effect on the labs.

Security problems should be reported privately. See [SECURITY.md](SECURITY.md).

## Ground rules for the data

1. **Keep it synthetic.** Never add real customer, company or personal data.
2. **Leave planted defects alone.** The Day 1–2 raw files (`renewal_pipeline_extract.txt`, `renewals_raw_extract.csv`, `usage_raw_monthly.csv`) contain deliberate errors for the data-cleaning exercises. They are not bugs.
3. **Preserve reproducibility.** The datasets are generated with a fixed seed and the labs use `random_state=42`. If your change alters any expected result (row counts, metrics, coefficients, forecasts), say so explicitly in the pull request and list the new values.
4. **Keep files consistent.** `renewals_day3.csv` and `open_renewals.csv` must share the same feature columns, and IDs must still join across files (`account_id`, `subscription_id`).
5. **Update the docs.** Row counts and column descriptions in the README must match the data.

## Development setup

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Before opening a pull request, check that the data still loads and the row counts still match the README:

```bash
python -c "import pandas as pd; r = pd.read_csv('data/renewals_day3.csv'); o = pd.read_csv('data/open_renewals.csv'); print(len(r), (r.renewal_status == 'Renewed').sum(), len(o))"
# expected: 795 615 412
```

## Local working files

Use the `.temp/` folder for drafts, scratch notebooks and anything else you don't want committed. It is listed in `.gitignore`. Don't force-add files from it.

## Pull request process

1. Fork the repository and create a branch from `main` (for example `docs/fix-setup-windows` or `data/add-region-column`).
2. Make focused changes; one topic per pull request.
3. Add an entry under **[Unreleased]** in [CHANGELOG.md](CHANGELOG.md).
4. Write a clear description: what changed, why, and whether any lab results change.
5. A maintainer will review. Data changes need explicit maintainer approval before merging.

## Commit messages

Use short, imperative subjects, for example:

```
Add Windows activation step to README
Fix nps_score type in open_renewals.csv
```

## Questions

Open an issue with the **question** label.
