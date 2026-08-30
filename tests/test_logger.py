import json

from src.analyzer import SentimentAnalysisResult
from src.collector import StockData
from src.decision import DecisionResult
from src.logger import KnowledgeLogger


def test_log_trade_decision(tmp_path):
    """ログファイルにJSON lines形式で正しく出力されるかのテスト"""
    log_file = tmp_path / "trade_logs.jsonl"
    logger = KnowledgeLogger(file_path=str(log_file))

    stock_data = StockData(
        ticker_symbol="7203.T",
        latest_close=2500.0,
        ma25_trend="UPWARD",
        ma25_value=2450.0,
    )
    sentiment_result = SentimentAnalysisResult(
        ticker_symbol="7203.T",
        sentiment_score=4.5,
        action="BUY",
        catalyst_summary="決算好調",
        risk_factors="なし",
        confidence_level=0.9,
    )
    decision_result = DecisionResult(
        final_action="BUY",
        is_buy_triggered=True,
        reason="判定成功",
    )

    logger.log_trade_decision(stock_data, sentiment_result, decision_result)

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert "trade_id" in record
    assert record["ticker_symbol"] == "7203.T"
    assert record["ai_score"] == 4.5
    assert record["catalyst_summary"] == "決算好調"
    assert record["risk_factors"] == "なし"
    assert record["technical_indicators"]["ma25_trend"] == "UPWARD"
    assert record["technical_indicators"]["entry_price"] == 2500.0
    assert record["trade_outcome"] is None
