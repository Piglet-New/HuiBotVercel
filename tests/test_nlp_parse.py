from app.telegram.parsing import parse_recommendation_query


def test_parse_recommendation_query():
    amount, category, merchant, location = parse_recommendation_query("ăn uống 1tr2 haidilao")
    assert amount == 1_200_000
    assert category == "an_uong"
    assert "haidilao" in (merchant or "")
    assert location is None
