"""Tests for sentiment analysis."""

from app.engine.sentiment import analyze_reviews, analyze_sentiment


class TestSentimentAnalysis:
    def test_positive_text(self):
        result = analyze_sentiment("This class is great and the professor is amazing!")
        assert result.polarity > 0.3
        assert len(result.positive_phrases) > 0

    def test_negative_text(self):
        result = analyze_sentiment("This class is terrible and boring. Avoid it!")
        assert result.polarity < -0.3
        assert len(result.negative_phrases) > 0

    def test_negation_handling(self):
        result = analyze_sentiment("This class is not easy")
        # "not easy" should flip the positive sentiment
        assert result.polarity < 0.3  # Should be neutral or negative

    def test_empty_text(self):
        result = analyze_sentiment("")
        assert result.polarity == 0.0
        assert result.confidence == 0.0

    def test_neutral_text(self):
        result = analyze_sentiment("The class meets on Monday and Wednesday.")
        assert abs(result.polarity) < 0.3
        assert result.confidence < 0.5


class TestAggregateReviews:
    def test_multiple_positive_reviews(self):
        reviews = [
            {"text": "Great class, really fun and interesting!"},
            {"text": "Amazing professor, very helpful and clear."},
            {"text": "Easy course with fair grading."},
        ]
        result = analyze_reviews(reviews)
        assert result.polarity > 0.3
        assert "Positive" in result.summary

    def test_mixed_reviews(self):
        reviews = [
            {"text": "Great class, really enjoyable!"},
            {"text": "Terrible course, worst experience ever."},
        ]
        result = analyze_reviews(reviews)
        # Mixed should average out close to neutral
        assert abs(result.polarity) < 0.5

    def test_empty_reviews(self):
        result = analyze_reviews([])
        assert result.polarity == 0.0
        assert "No reviews" in result.summary
