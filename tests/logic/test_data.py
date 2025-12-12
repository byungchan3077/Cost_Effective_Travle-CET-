import sys
import os
import json
import pandas as pd
import pytest

# ---------- Path Configuration ----------
# Based on the current file location: tests/logic/test_data.py
# This setup ensures Python can find the 'src/data' directory where export_json.py lives.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(ROOT_DIR, "src", "data")
sys.path.insert(0, DATA_DIR)
# ----------------------------------------

import export_json  # ✔ Make sure this matches your actual filename!

def test_clean_number():
    """
    Tests the 'clean_number' helper function to ensure it handles 
    commas, spaces, and non-numeric strings correctly.
    """
    assert export_json.clean_number("1,000") == 1000.0
    assert export_json.clean_number(" 123 ") == 123.0
    assert export_json.clean_number("abc") == 0
    assert export_json.clean_number(3.14) == 3.14


def test_main_creates_correct_result_json(tmp_path, monkeypatch):
    """
    Integration test for the main logic.
    Uses 'tmp_path' to create temporary CSV files and checks if
    the final 'result.json' is generated with correct calculations.
    """
    
    # 1. Create Dummy Hotel Data
    # Note: Japan has two entries to test the averaging logic.
    hotel_df = pd.DataFrame({
        "Country": ["Japan", "Japan ", "France"],
        "Avg_price": ["10,000", "20,000", "80,000"]
    })
    hotel_path = tmp_path / "hotel_price_index.csv"
    hotel_df.to_csv(hotel_path, index=False)

    # 2. Create Dummy Starbucks Data
    starbucks_df = pd.DataFrame({
        "Country": ["Japan", "France"],
        "Avg_price": ["5", "45"]
    })
    starbucks_path = tmp_path / "starbucks_drink_index.csv"
    starbucks_df.to_csv(starbucks_path, index=False)

    # 3. Create Dummy Big Mac Data
    # Note: Uses 'Euro area' to test if it correctly copies data to France.
    bigmac_df = pd.DataFrame({
        "Country": ["Japan", "Euro area"],
        "local_price": ["4.2", "4.0"]
    })
    bigmac_path = tmp_path / "big_mac_index.csv"
    bigmac_df.to_csv(bigmac_path, index=False)

    # 4. Monkeypatching
    # Override the 'script_dir' variable inside export_json to point to our temporary test path
    # instead of the actual real-world directory.
    monkeypatch.setattr(export_json, "script_dir", str(tmp_path))

    # 5. Run the Main Function
    export_json.main()

    # 6. Verify Output
    output_path = tmp_path / "result.json"
    assert output_path.exists()

    with output_path.open(encoding="utf-8") as f:
        result = json.load(f)

    # Check if countries exist
    assert "Japan" in result
    assert "France" in result

    # Validate Japan Data
    # Avg Hotel: (10000 + 20000) / 2 = 15000
    jp = result["Japan"]
    assert jp["currency"] == "JPY(100)"
    assert jp["avg_hotel_krw"] == 15000
    assert jp["starbucks"] == 5.0
    assert jp["big_mac"] == 4.2

    # Validate France Data
    # Big Mac: Should be copied from 'Euro area' (4.0)
    fr = result["France"]
    assert fr["currency"] == "EUR"
    assert fr["avg_hotel_krw"] == 80000
    assert fr["starbucks"] == 45.0
    assert fr["big_mac"] == 4.0