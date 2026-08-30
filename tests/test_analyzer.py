from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from src.analyzer import SentimentAnalysisResult, SentimentAnalyzer


def test_sentiment_analysis_result_schema() -> None:
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


def test_analyze_news_success(mocker: MockerFixture) -> None:
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


def test_analyze_news_with_rag_context(mocker: MockerFixture) -> None:
    """RAGコンテキストが指定された場合にプロンプトに含まれることのテスト"""
    mock_json_response = """{
        "ticker_symbol": "7203.T",
        "sentiment_score": 3.8,
        "action": "HOLD",
        "catalyst_summary": "好決算だが過去類似事例と同様に材料出尽くしの懸念あり",
        "risk_factors": "過去事例でのLOSSパターンと類似",
        "confidence_level": 0.88
    }"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_json_response
    mock_client.models.generate_content.return_value = mock_response

    mocker.patch("google.genai.Client", return_value=mock_client)

    analyzer = SentimentAnalyzer(api_key="fake_key")
    rag_context = "【過去の類似事例（参考ナレッジ）】\n事例1: [銘柄: 7203.T / 結果: LOSS]"

    res = analyzer.analyze_news("7203.T", "好決算ニュース", rag_context=rag_context)

    # 送信されたプロンプトに RAG コンテキストが含まれているか確認
    call_args = mock_client.models.generate_content.call_args
    prompt_content = call_args.kwargs["contents"]
    assert "【過去の類似事例（参考ナレッジ）】" in prompt_content
    assert "事例1: [銘柄: 7203.T / 結果: LOSS]" in prompt_content
    assert res.action == "HOLD"


def test_analyze_news_fallback_when_no_api_key(mocker: MockerFixture) -> None:
    """APIキーがない場合に適切に警告またはフォールバックが働くことのテスト"""
    mocker.patch("os.getenv", return_value=None)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        SentimentAnalyzer(api_key=None)
