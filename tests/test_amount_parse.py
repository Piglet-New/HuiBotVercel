from app.telegram.parsing import parse_amount_vnd


def test_parse_amount_basic():
    assert parse_amount_vnd("1200000") == 1_200_000
    assert parse_amount_vnd("1200k") == 1_200_000
    assert parse_amount_vnd("1tr2") == 1_200_000
    assert parse_amount_vnd("2tr5") == 2_500_000
    assert parse_amount_vnd("850k") == 850_000
    assert parse_amount_vnd("1tr") == 1_000_000
