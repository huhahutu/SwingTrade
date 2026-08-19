from unittest.mock import MagicMock

import pytest

from src.analyzer import SentimentAnalysisResult, SentimentAnalyzer


def test_sentiment_analysis_result_schema():
    """Pydanticモデルのスキーマバリデーション確認"""
    result = SentimentAnalysisResult(
        ticker_symbol="7203.T",
        sentiment_score=4.5,
        action="BUY",
        catalyst_summary="業績上方修正と需要拡大",
        risk_factors="為替変動リスク",
        confidence_level=0.85,
    )
    assert result.ticker_symbol == "7203.T"
    assert result.sentiment_score == 4.5
    assert result.action == "BUY"
    assert result.confidence_level == 0.85


def test_analyze_news_success(mocker):
    """Gemini API呼び出しが成功した場合のテスト"""
    mock_json_response = """{
        "ticker_symbol": "7203.T",
        "sentiment_score": 4.2,
        "action": "BUY",
        "catalyst_summary": "営業利益+25%の大幅上方修正発表",
        "risk_factors": "一時的な材料出尽くし感による売りの可能性",
        "confidence_level": 0.90
    }"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_json_response
    mock_client.models.generate_content.return_value = mock_response

    mocker.patch("google.genai.Client", return_value=mock_client)

    analyzer = SentimentAnalyzer(api_key="fake_key")
    res = analyzer.analyze_news("7203.T", "上方修正のニュース")

    assert isinstance(res, SentimentAnalysisResult)
    assert res.ticker_symbol == "7203.T"
    assert res.sentiment_score == 4.2
    assert res.action == "BUY"


def test_analyze_news_fallback_when_no_api_key(mocker):
    """APIキーがない場合に適切に警告またはフォールバックが働くことのテスト"""
    mocker.patch("os.getenv", return_value=None)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        SentimentAnalyzer(api_key=None)
