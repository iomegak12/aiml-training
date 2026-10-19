# Contributing

Thanks for helping improve this training project.

## Ground rules
- Python 3.12; use only the pinned dependencies in `pyproject.toml`.
  Discuss before adding a new one.
- Keep code simple and readable: small functions, type hints, short docstrings.
- Use the `logging` module inside the library; CLI scripts may print a short summary.
- Use `RANDOM_STATE` (51) from `config.py` wherever randomness is involved.
- Never modify files in `data/raw` or `data/sample`.

## Workflow
1. Create a branch: `git checkout -b feature/<short-name>`.
2. `make setup` once, then make your change.
3. Add or update tests in `tests/`, run `make test`.
4. Update `CHANGELOG.md` under *Unreleased*.
5. Open a pull request with a short description of what and why.

By contributing you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
