from app.services.recommend import format_recommendations


def test_format_recommendations_empty():
    message = format_recommendations([])
    assert "Chưa có thẻ" in message
