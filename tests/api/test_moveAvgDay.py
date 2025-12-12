import os
import sys
import pytest
import requests_mock
import pandas as pd
from datetime import datetime, timedelta

# --- Setup for Relative Imports ---
# Assumes the test file is in src/tests/api and the target is src/api/moveAvgDay.py
# Add project root path (two levels up from src/tests/api)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import the module under test and required functions/constants
from src.api.moveAvgDay import (
    DAYS_TO_FETCH, MIN_PERIODS, DB_DIR, DB_FILE_PREFIX, 
    setup_database, load_db_data, save_db_data, get_50day_ma_data
)
# Note: get_target_currencies is imported from country_loader in the original file,
# but we mock its behavior directly in the test using the moveAvgDay import path.

# --- Test Constants and Setup ---
TEST_API_KEY = "mock_test_api_key_123"
TEST_CURRENCY = 'USD'

# Define a temporary path for the test database
TEST_DB_DIR = os.path.join(os.path.dirname(__file__), 'test_database')
TEST_FILE_PATH = os.path.join(TEST_DB_DIR, f"{DB_FILE_PREFIX}{TEST_CURRENCY}.csv")


# =============================================================================
# Fixtures and Helpers
# =============================================================================

@pytest.fixture(scope="module", autouse=True)
def setup_teardown_db(): 
    """
    Sets up a temporary database directory and ensures cleanup.
    (Only file system operations remain here, separated from monkeypatch to resolve ScopeMismatch)
    """
    
    # Create the test directory
    os.makedirs(TEST_DB_DIR, exist_ok=True)
    
    # CRITICAL FIX: Ensure the test file is deleted before the test runs (DB Cleanup)
    if os.path.exists(TEST_FILE_PATH):
        os.remove(TEST_FILE_PATH)
        
    yield 

    # --- TEARDOWN ---
    # Clean up the test environment after the test suite finishes
    if os.path.exists(TEST_FILE_PATH):
        os.remove(TEST_FILE_PATH)
    if os.path.exists(TEST_DB_DIR):
        os.rmdir(TEST_DB_DIR)

# FIX 2: New function-scoped fixture to handle DB_DIR patching (resolves ScopeMismatch)
@pytest.fixture(autouse=True) # Defaults to function scope
def patch_db_dir(monkeypatch):
    """Patches the DB_DIR constant in the module under test."""
    import src.api.moveAvgDay 
    monkeypatch.setattr(src.api.moveAvgDay, 'DB_DIR', TEST_DB_DIR)


@pytest.fixture
def mock_target_currencies(monkeypatch):
    """Mocks the currency list returned by country_loader.get_target_currencies."""
    # We use the path that the function under test (get_50day_ma_data) uses
    mock_currencies = [TEST_CURRENCY]
    monkeypatch.setattr('src.api.moveAvgDay.get_target_currencies', lambda: mock_currencies)
    return mock_currencies

def create_mock_api_response(currency_code, date, rate):
    """Helper function to create a structured API response."""
    # The API rate (deal_bas_r) must be a string with a comma if over 1000
    rate_str = f"{rate:,.2f}"
    return [{
        "result": 1,
        "cur_unit": currency_code,
        "deal_bas_r": rate_str,
        "yyyymmdd": date
    }]

# =============================================================================
# Test Cases
# =============================================================================

def test_load_db_data_empty_file_returns_empty_df(setup_teardown_db, patch_db_dir):
    """Verifies that loading a non-existent file returns an empty DataFrame."""
    # Note: setup_teardown_db ensures the file does not exist
    df = load_db_data(TEST_FILE_PATH)
    assert df.empty
    assert isinstance(df, pd.DataFrame)

def test_save_and_load_db_data_integrity(setup_teardown_db, patch_db_dir):
    """Tests the integrity of the save/load cycle."""
    test_data = {
        'Date': ['20251201', '20251202'], 
        'Currency Code': [TEST_CURRENCY, TEST_CURRENCY], 
        'Currency': [1300.0, 1301.0]
    }
    df_save = pd.DataFrame(test_data)
    
    # Save the data
    save_db_data(df_save, TEST_FILE_PATH)
    
    # Load the data and verify
    df_load = load_db_data(TEST_FILE_PATH)
    
    assert len(df_load) == 2
    # Load function sorts descending, so the newest data should be first
    assert df_load.iloc[0]['Date'] == '20251202'
    assert df_load.iloc[1]['Currency'] == 1300.0
    # Verify the 'Currency' column type is correct (float/numeric)
    assert pd.api.types.is_numeric_dtype(df_load['Currency'])

def test_get_50day_ma_data_full_process(requests_mock, mock_target_currencies, patch_db_dir):
    """
    Tests the full data lifecycle: loading (45 days), fetching (5 days), 
    calculating MA, and returning the result.
    """
    
    # 1. Initial DB State: Assume 45 days of data exist (Need 5 more days)
    existing_days = 45
    needed_new_days = DAYS_TO_FETCH - existing_days # Should be 5

    # Generate 45 days of historical data (Date in YYYYMMDD string format)
    base_rate = 1400.0
    base_date = datetime.now() - timedelta(days=70) # Set a baseline far enough in the past
    existing_data = []

    for i in range(1, existing_days + 1):
        # We need realistic date strings for comparison
        date_str = (base_date + timedelta(days=i)).strftime('%Y%m%d')
        existing_data.append({
            'Date': date_str,
            'Currency Code': TEST_CURRENCY,
            'Currency': base_rate + i * 0.1,
        })

    df_existing = pd.DataFrame(existing_data)
    save_db_data(df_existing, TEST_FILE_PATH) # Saves 45 days

    # 2. API Mocking: Generate the 5 required days (latest data)
    latest_rate_base = 1500.0
    api_base_url = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"

    mock_dates = []
    fetched_count = 0
    # Search backwards for a reasonable amount of time (e.g., 10 days) to find the 5 business days
    MAX_SEARCH_DAYS = 10 

    for i in range(1, MAX_SEARCH_DAYS + 1):
        # FIX: The search date must follow the logic in fetch_optimized_data (1, 2, 3... days back)
        search_date_str = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        
        # Only mock a response if the date is not already in the DB AND we still need data
        if search_date_str not in df_existing['Date'].values and fetched_count < needed_new_days:
            rate = latest_rate_base + fetched_count + 1 

            # Mock the specific API URL call
            requests_mock.get(
                f"{api_base_url}?authkey={TEST_API_KEY}&searchdate={search_date_str}&data=AP01",
                json=create_mock_api_response(TEST_CURRENCY, search_date_str, rate),
                status_code=200
            )
            mock_dates.append((search_date_str, rate))
            fetched_count += 1
        
        if fetched_count >= needed_new_days:
            break

    # The newest data (which should be the one returned) is the first date mocked (index 0)
    newest_mocked_date, newest_mocked_rate = mock_dates[0]

    # 3. Execute the test function
    result_df = get_50day_ma_data(TEST_API_KEY)

    # 4. Verify the final returned DataFrame (result_df)
    assert not result_df.empty
    assert len(result_df) == 1 

    result_row = result_df.iloc[0]

    # - Verify Current Rate ('Currency') is the newest rate fetched
    assert result_row['Currency Code'] == TEST_CURRENCY
    
    # Assert the latest row's currency is the newest mocked rate
    assert result_row['Currency'] == newest_mocked_rate
    
    # - Verify MA calculation (check if it's a valid number)
    assert not pd.isna(result_row['50-day_MA'])

    # 5. Verify the DB file now has 50 days
    final_df = load_db_data(TEST_FILE_PATH)
    assert len(final_df) == DAYS_TO_FETCH
    
    # Verify the newest date in the saved DB is the newest mocked date
    # (load_db_data sorts by date descending)
    assert final_df.iloc[0]['Date'] == newest_mocked_date