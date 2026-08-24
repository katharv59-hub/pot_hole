import pytest
from app.services.event_service import encode_geohash

def test_geohash_known_values():
    # Test known geohash coordinates
    # Mumbai coordinates (19.0760, 72.8777) -> geohash precision 6 = "te7ud2"
    gh1 = encode_geohash(19.0760, 72.8777, precision=6)
    assert gh1 == "te7ud2"

    # London coordinates (51.5074, -0.1278) -> geohash precision 6 = "gcpvj0"
    gh2 = encode_geohash(51.5074, -0.1278, precision=6)
    assert gh2 == "gcpvj0"

    # New York coordinates (40.7128, -74.0060) -> geohash precision 6 = "dr5reg"
    gh3 = encode_geohash(40.7128, -74.0060, precision=6)
    assert gh3 == "dr5reg"
