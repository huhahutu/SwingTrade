import pytest

from src.analyzer import SentimentAnalysisResult
from src.collector import StockData
from src.decision import DecisionResult, TradeDecisionMaker


@pytest.fixture
def base_stock_data():
    return StockData(
        ticker_symbol="7203.T",
        latest_close=2500.0,
        ma25_trend="UPWARD",
        ma25_value=2450.0,
    )


@pytest.fixture
def base_sentiment_result():
    return SentimentAnalysisResult(
        ticker_symbol="7203.T",
        sentiment_score=4.5,
        action="BUY",
        catalyst_summary="好決算",
        risk_factors="なし",
        confidence_level=0.9,
    )


def test_decision_buy_when_both_conditions_met(base_stock_data, base_sentiment_result):
    """条件A (UPWARD) かつ 条件B (score>=4.0) の場合に BUY となるテスト"""
    decision_maker = TradeDecisionMaker()
    result: DecisionResult = decision_maker.make_decision(base_stock_data, base_sentiment_result)

    assert result.final_action == "BUY"
    assert result.is_buy_triggered is True
    assert "判定成功" in result.reason or "BUY" in result.reason


def test_decision_hold_when_ma25_not_upward(base_stock_data, base_sentiment_result):
    """MA25がFLAT/DOWNWARDの場合、AI scoreが4.5でも HOLD になるテスト"""
    base_stock_data.ma25_trend = "FLAT"
    decision_maker = TradeDecisionMaker()
    result = decision_maker.make_decision(base_stock_data, base_sentiment_result)

    assert result.final_action == "HOLD"
    assert result.is_buy_triggered is False
    assert "25日移動平均線が上向きではありません" in result.reason


def test_decision_hold_when_score_low(base_stock_data, base_sentiment_result):
    """AI scoreが3.9以下の場合、MA25がUPWARDでも HOLD になるテスト"""
    base_sentiment_result.sentiment_score = 3.9
    decision_maker = TradeDecisionMaker()
    result = decision_maker.make_decision(base_stock_data, base_sentiment_result)

    assert result.final_action == "HOLD"
    assert result.is_buy_triggered is False
    assert "センチメントスコア" in result.reason
