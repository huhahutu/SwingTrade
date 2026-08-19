import json
from datetime import date, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.evaluator import EvaluationResult, TradeEvaluator

# --- テスト用フィクスチャ ---


@pytest.fixture
def sample_buy_record():
    """BUYで決済待ちの取引ログサンプル"""
    return {
        "trade_id": "test-uuid-001",
        "date": "2026-08-01",
        "ticker_symbol": "7203.T",
        "ai_score": 4.5,
        "ai_action_reason": "テスト用",
        "technical_indicators": {"ma25_trend": "UPWARD", "entry_price": 2980.0},
        "execution_result": {
            "bought_price": 2980.0,
            "sold_price": None,
            "profit_loss_rate": None,
            "stop_loss_triggered": None,
            "holding_period_days": None,
        },
        "trade_outcome": None,
        "post_analysis_notes": "Final Decision: BUY",
    }


@pytest.fixture
def sample_hold_record():
    """HOLDで bought_price がない取引ログサンプル（評価スキップ対象）"""
    return {
        "trade_id": "test-uuid-002",
        "date": "2026-08-01",
        "ticker_symbol": "7203.T",
        "ai_score": 3.5,
        "ai_action_reason": "テスト用",
        "technical_indicators": {"ma25_trend": "FLAT", "entry_price": 2980.0},
        "execution_result": {
            "bought_price": None,
            "sold_price": None,
            "profit_loss_rate": None,
            "stop_loss_triggered": None,
            "holding_period_days": None,
        },
        "trade_outcome": None,
        "post_analysis_notes": "Final Decision: HOLD",
    }


def _make_price_df(price: float, trade_date: str, holding_days: int) -> pd.DataFrame:
    """指定値段のモック株価DataFrameを生成するヘルパー"""
    buy_date = date.fromisoformat(trade_date)
    eval_date = buy_date + timedelta(days=holding_days)
    dates = pd.date_range(start=buy_date, end=eval_date, freq="D")
    prices = [price] * len(dates)
    return pd.DataFrame({"Close": prices}, index=dates)


# --- 正常系テスト ---


def test_evaluate_win(mocker, sample_buy_record):
    """5日後の株価が買値より +2% 上昇 → WIN になること"""
    sold_price = 3039.6  # 2980 * 1.02
    mock_df = _make_price_df(sold_price, sample_buy_record["date"], 5)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    evaluator = TradeEvaluator(holding_days=5)
    result: EvaluationResult = evaluator.evaluate(sample_buy_record)

    assert result.trade_outcome == "WIN"
    assert abs(result.profit_loss_rate - 0.02) < 0.001
    assert result.sold_price == pytest.approx(sold_price, rel=1e-3)
    assert result.holding_period_days == 5


def test_evaluate_loss(mocker, sample_buy_record):
    """5日後の株価が買値より -2% 下落 → LOSS になること"""
    sold_price = 2921.6  # 2980 * 0.98
    mock_df = _make_price_df(sold_price, sample_buy_record["date"], 5)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    evaluator = TradeEvaluator(holding_days=5)
    result: EvaluationResult = evaluator.evaluate(sample_buy_record)

    assert result.trade_outcome == "LOSS"
    assert result.profit_loss_rate < 0


def test_evaluate_draw_near_zero(mocker, sample_buy_record):
    """5日後の株価が買値とほぼ同じ（0.3%以内） → DRAW になること"""
    sold_price = 2988.0  # 2980 * 約1.0027
    mock_df = _make_price_df(sold_price, sample_buy_record["date"], 5)

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    evaluator = TradeEvaluator(holding_days=5)
    result: EvaluationResult = evaluator.evaluate(sample_buy_record)

    assert result.trade_outcome == "DRAW"


def test_skip_hold_record(sample_hold_record):
    """bought_price が None のレコードは評価をスキップすること"""
    evaluator = TradeEvaluator(holding_days=5)
    result = evaluator.evaluate(sample_hold_record)

    assert result is None


def test_skip_evaluated_record(sample_buy_record):
    """すでに trade_outcome が設定されているレコードは評価をスキップすること"""
    sample_buy_record["trade_outcome"] = "WIN"
    evaluator = TradeEvaluator(holding_days=5)
    result = evaluator.evaluate(sample_buy_record)

    assert result is None


def test_update_jsonl(mocker, sample_buy_record, tmp_path):
    """trade_logs.jsonl を読み込み、評価結果を上書き保存すること"""
    log_file = tmp_path / "trade_logs.jsonl"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(sample_buy_record, ensure_ascii=False) + "\n")

    sold_price = 3100.0
    mock_df = _make_price_df(sold_price, sample_buy_record["date"], 5)
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    evaluator = TradeEvaluator(holding_days=5)
    evaluator.update_log_file(str(log_file))

    with open(log_file, encoding="utf-8") as f:
        updated = json.loads(f.readline())

    assert updated["trade_outcome"] == "WIN"
    assert updated["execution_result"]["sold_price"] == pytest.approx(sold_price, rel=1e-3)
    assert updated["execution_result"]["profit_loss_rate"] is not None
    assert updated["execution_result"]["holding_period_days"] == 5
