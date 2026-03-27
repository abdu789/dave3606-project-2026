# tests/test_endpoints.py
from unittest.mock import MagicMock
import json
import pytest
from server import fetch_set_data  # <-- import from your server.py

def test_fetch_set_data_found():
    # Arrange
    mock_db = MagicMock()
    # Side effects: first call returns set info, second call returns inventory
    mock_db.execute_and_fetch_all.side_effect = [
        [("1234", "Millennium Falcon")],          # set info
        [("BT-001", "Red", 10), ("BT-002", "Blue", 5)]  # inventory
    ]

    # Act
    data_json, status = fetch_set_data(mock_db, "1234")
    data = json.loads(data_json)

    # Assert
    assert status == 200
    assert data["id"] == "1234"
    assert data["name"] == "Millennium Falcon"
    assert len(data["inventory"]) == 2
    assert data["inventory"][0]["brick_type_id"] == "BT-001"
    assert mock_db.execute_and_fetch_all.call_count == 2

def test_fetch_set_data_not_found():
    # Arrange
    mock_db = MagicMock()
    mock_db.execute_and_fetch_all.return_value = []  # Simulate set not found

    # Act
    data_json, status = fetch_set_data(mock_db, "9999")
    data = json.loads(data_json)

    # Assert
    assert status == 404
    assert "error" in data
    assert data["error"] == "Set not found"
    assert mock_db.execute_and_fetch_all.call_count == 1