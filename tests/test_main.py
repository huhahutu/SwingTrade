from pathlib import Path

import pytest

from main import run_batch_pipeline, run_pipeline
from src.analyzer import SentimentAnalysisResult
from src.collector import StockData


def test_run_pipeline_success(mocker: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """メインパイプラインが一貫して正常終了するかの統合テスト"""
    mock_stock_data = StockData(
        ticker_symbol="7203.T",
        latest_close=2600.0,
        ma25_trend="UPWARD",
        ma25_value=2550.0,
    )
    mock_sentiment = SentimentAnalysisResult(
        ticker_symbol="7203.T",
        sentiment_score=4.3,
        action="BUY",
        catalyst_summary="業績拡大",
        risk_factors="なし",
        confidence_level=0.88,
    )

    # collector, analyzer, logger のモック設定
    mocker.patch(  # type: ignore[attr-defined]
        "src.collector.StockDataCollector.get_stock_data",
        return_value=mock_stock_data,
    )
    mocker.patch(  # type: ignore[attr-defined]
        "main.fetch_latest_news",
        return_value=[
            {
                "title": "【7203】業績予想の上方修正",
                "summary": "営業利益の上方修正を発表",
                "url": "https://example.com/7203",
                "published": "2026-08-30 15:00:00",
            }
        ],
    )
    mocker.patch(  # type: ignore[attr-defined]
        "src.analyzer.SentimentAnalyzer.analyze_news",
        return_value=mock_sentiment,
    )

    log_file = tmp_path / "trade_logs.jsonl"
    result_record = run_pipeline(
        ticker_symbol="7203.T",
        api_key="mock_api_key",
        log_file_path=str(log_file),
    )

    assert result_record["ticker_symbol"] == "7203.T"
    assert result_record["ai_score"] == 4.3
    assert result_record["technical_indicators"]["ma25_trend"] == "UPWARD"
    assert log_file.exists()


def test_run_batch_pipeline_success(mocker: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """複数銘柄に対するバッチパイプライン実行テスト"""
    mock_stock_data = StockData(
        ticker_symbol="7203.T",
        latest_close=2600.0,
        ma25_trend="UPWARD",
        ma25_value=2550.0,
    )
    mock_sentiment = SentimentAnalysisResult(
        ticker_symbol="7203.T",
        sentiment_score=4.3,
        action="BUY",
        catalyst_summary="業績拡大",
        risk_factors="なし",
        confidence_level=0.88,
    )

    mocker.patch(  # type: ignore[attr-defined]
        "src.collector.StockDataCollector.get_stock_data",
        return_value=mock_stock_data,
    )
    mocker.patch(  # type: ignore[attr-defined]
        "main.fetch_latest_news",
        return_value=[],
    )
    mocker.patch(  # type: ignore[attr-defined]
        "src.analyzer.SentimentAnalyzer.analyze_news",
        return_value=mock_sentiment,
    )

    log_file = tmp_path / "trade_logs.jsonl"
    results = run_batch_pipeline(
        tickers=["7203.T", "8306.T"],
        api_key="mock_api_key",
        log_file_path=str(log_file),
    )

    assert len(results) == 2
    assert log_file.exists()
