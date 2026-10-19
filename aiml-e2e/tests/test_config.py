"""Smoke tests for the project configuration."""

from northwind_loans import config


def test_input_data_files_exist() -> None:
    assert config.RAW_DATA.is_file()
    assert config.SAMPLE_DATA.is_file()


def test_output_folders_exist() -> None:
    for folder in (config.PROCESSED_DATA, config.REPORTS_DIR, config.MODEL_DIR, config.LOG_DIR):
        assert folder.is_dir(), folder


def test_core_settings() -> None:
    assert config.TARGET == "max_loan_offered"
    assert config.RANDOM_STATE == 51
    assert config.INCOME_PAISE_THRESHOLD == 20_000_000


def test_credit_policy_covers_all_purposes_and_bands() -> None:
    purposes = {"Home", "Personal", "Auto", "Education", "Business"}
    bands = {"<600", "600-649", "650-699", "700-749", "750+"}
    policy = config.CREDIT_POLICY
    assert set(policy["rate_card_pct"]) == purposes
    assert set(policy["income_multiple_cap"]) == purposes
    assert set(policy["foir_by_credit_band"]) == bands
    assert set(policy["credit_haircut"]) == bands
