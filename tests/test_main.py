from main import run_pipeline
from src.analyzer import SentimentAnalysisResult
from src.collector import StockData


def test_run_pipeline_success(mocker, tmp_path):
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
    mocker.patch(
        "src.collector.StockDataCollector.get_stock_data",
        return_value=mock_stock_data,
    )
    mocker.patch(
        "src.collector.StockDataCollector.get_mock_news",
        return_value="テストニュース本文",
    )
    mocker.patch(
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
