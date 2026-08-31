"""
tests/test_dataset_generator.py

DatasetGenerator のユニットテスト

TDDサイクル（Red → Green → Refactor）の Red フェーズとして作成。
正常系・フィルタリング（LOSS/DRAW除外）・重複排除・ファイル追記保存を検証する。
"""

import json
from pathlib import Path
from typing import Any

import pytest

from src.dataset_generator import DatasetGenerator, FinetuneRecord

# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


def _make_trade_record(
    trade_id: str,
    trade_outcome: str | None,
    profit_loss_rate: float | None,
    *,
    ticker_symbol: str = "7203.T",
    ai_score: float = 4.5,
    news_content: str = "トヨタ、好決算を発表",
    catalyst_summary: str = "好決算",
    risk_factors: str = "なし",
    ma25_trend: str = "UPWARD",
    entry_price: float = 3000.0,
    bought_price: float | None = 3000.0,
) -> dict[str, Any]:
    """テスト用取引ログレコードを生成するヘルパー"""
    return {
        "trade_id": trade_id,
        "date": "2026-08-01",
        "ticker_symbol": ticker_symbol,
        "news_content": news_content,
        "ai_score": ai_score,
        "ai_action_reason": f"AI Action=BUY: {catalyst_summary}",
        "catalyst_summary": catalyst_summary,
        "risk_factors": risk_factors,
        "technical_indicators": {
            "ma25_trend": ma25_trend,
            "entry_price": entry_price,
        },
        "execution_result": {
            "bought_price": bought_price,
            "sold_price": 3100.0 if profit_loss_rate and profit_loss_rate > 0 else 2900.0,
            "profit_loss_rate": profit_loss_rate,
            "stop_loss_triggered": None,
            "holding_period_days": 5,
        },
        "trade_outcome": trade_outcome,
        "post_analysis_notes": "Final Decision: BUY",
    }


@pytest.fixture
def win_record() -> dict[str, Any]:
    """WIN かつ profit_loss_rate >= 0.02 のレコード（抽出対象）"""
    return _make_trade_record(
        trade_id="win-001",
        trade_outcome="WIN",
        profit_loss_rate=0.033,
    )


@pytest.fixture
def win_record_low_rate() -> dict[str, Any]:
    """WIN だが profit_loss_rate < 0.02 のレコード（抽出対象外）"""
    return _make_trade_record(
        trade_id="win-low-002",
        trade_outcome="WIN",
        profit_loss_rate=0.01,
    )


@pytest.fixture
def loss_record() -> dict[str, Any]:
    """LOSS レコード（抽出対象外）"""
    return _make_trade_record(
        trade_id="loss-003",
        trade_outcome="LOSS",
        profit_loss_rate=-0.025,
    )


@pytest.fixture
def draw_record() -> dict[str, Any]:
    """DRAW レコード（抽出対象外）"""
    return _make_trade_record(
        trade_id="draw-004",
        trade_outcome="DRAW",
        profit_loss_rate=0.002,
    )


@pytest.fixture
def win_record_exact_threshold() -> dict[str, Any]:
    """WIN かつ profit_loss_rate が閾値ちょうど(0.02)のレコード（境界値・抽出対象）"""
    return _make_trade_record(
        trade_id="win-threshold-005",
        trade_outcome="WIN",
        profit_loss_rate=0.02,
    )


# ---------------------------------------------------------------------------
# FinetuneRecord のユニットテスト
# ---------------------------------------------------------------------------


class TestFinetuneRecord:
    """FinetuneRecord Pydantic モデルのテスト"""

    def test_build_from_record(self, win_record: dict[str, Any]) -> None:
        """WIN レコードから FinetuneRecord を正しく構築できること"""
        ft_record = FinetuneRecord.from_trade_record(win_record)

        assert len(ft_record.messages) == 3
        assert ft_record.messages[0].role == "system"
        assert ft_record.messages[1].role == "user"
        assert ft_record.messages[2].role == "model"

    def test_user_message_contains_ticker(self, win_record: dict[str, Any]) -> None:
        """user メッセージに銘柄コードが含まれること"""
        ft_record = FinetuneRecord.from_trade_record(win_record)
        user_content = ft_record.messages[1].content
        assert "7203.T" in user_content

    def test_user_message_contains_ma25_trend(self, win_record: dict[str, Any]) -> None:
        """user メッセージに移動平均トレンドが含まれること"""
        ft_record = FinetuneRecord.from_trade_record(win_record)
        user_content = ft_record.messages[1].content
        assert "UPWARD" in user_content

    def test_user_message_contains_news(self, win_record: dict[str, Any]) -> None:
        """user メッセージにニュース本文が含まれること"""
        ft_record = FinetuneRecord.from_trade_record(win_record)
        user_content = ft_record.messages[1].content
        assert "好決算" in user_content

    def test_model_message_is_valid_json(self, win_record: dict[str, Any]) -> None:
        """model メッセージが有効な JSON 文字列であること"""
        ft_record = FinetuneRecord.from_trade_record(win_record)
        model_content = ft_record.messages[2].content
        parsed = json.loads(model_content)
        assert "ticker_symbol" in parsed
        assert "sentiment_score" in parsed
        assert "action" in parsed

    def test_to_jsonl_line(self, win_record: dict[str, Any]) -> None:
        """to_jsonl_line() が messages キーを持つ JSON 文字列を返すこと"""
        ft_record = FinetuneRecord.from_trade_record(win_record)
        line = ft_record.to_jsonl_line()
        parsed = json.loads(line)
        assert "messages" in parsed
        assert len(parsed["messages"]) == 3


# ---------------------------------------------------------------------------
# DatasetGenerator.is_eligible のユニットテスト
# ---------------------------------------------------------------------------


class TestIsEligible:
    """抽出条件フィルタリングのテスト"""

    def test_win_with_sufficient_rate_is_eligible(self, win_record: dict[str, Any]) -> None:
        """WIN かつ profit_loss_rate >= 0.02 → 抽出対象"""
        assert DatasetGenerator.is_eligible(win_record) is True

    def test_win_at_exact_threshold_is_eligible(
        self, win_record_exact_threshold: dict[str, Any]
    ) -> None:
        """WIN かつ profit_loss_rate == 0.02（境界値）→ 抽出対象"""
        assert DatasetGenerator.is_eligible(win_record_exact_threshold) is True

    def test_win_below_threshold_not_eligible(
        self, win_record_low_rate: dict[str, Any]
    ) -> None:
        """WIN だが profit_loss_rate < 0.02 → 抽出対象外"""
        assert DatasetGenerator.is_eligible(win_record_low_rate) is False

    def test_loss_not_eligible(self, loss_record: dict[str, Any]) -> None:
        """LOSS → 抽出対象外"""
        assert DatasetGenerator.is_eligible(loss_record) is False

    def test_draw_not_eligible(self, draw_record: dict[str, Any]) -> None:
        """DRAW → 抽出対象外"""
        assert DatasetGenerator.is_eligible(draw_record) is False

    def test_none_outcome_not_eligible(self) -> None:
        """trade_outcome が None（未評価）→ 抽出対象外"""
        record = _make_trade_record(
            trade_id="none-006",
            trade_outcome=None,
            profit_loss_rate=None,
        )
        assert DatasetGenerator.is_eligible(record) is False

    def test_none_profit_loss_rate_not_eligible(self) -> None:
        """trade_outcome は WIN だが profit_loss_rate が None → 抽出対象外"""
        record = _make_trade_record(
            trade_id="none-rate-007",
            trade_outcome="WIN",
            profit_loss_rate=None,
        )
        assert DatasetGenerator.is_eligible(record) is False


# ---------------------------------------------------------------------------
# DatasetGenerator.save のユニットテスト
# ---------------------------------------------------------------------------


class TestDatasetGeneratorSave:
    """ファイル保存・重複排除のテスト"""

    def test_save_creates_file(self, tmp_path: Path, win_record: dict[str, Any]) -> None:
        """保存先ファイルが存在しない場合に新規作成されること"""
        output_file = tmp_path / "finetune_dataset.jsonl"
        generator = DatasetGenerator(output_path=str(output_file))

        saved = generator.save(win_record)

        assert saved is True
        assert output_file.exists()

    def test_save_appends_jsonl_line(self, tmp_path: Path, win_record: dict[str, Any]) -> None:
        """保存後のファイルが有効な JSONL 形式であること"""
        output_file = tmp_path / "finetune_dataset.jsonl"
        generator = DatasetGenerator(output_path=str(output_file))

        generator.save(win_record)

        lines = output_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert "messages" in parsed

    def test_save_filters_loss(self, tmp_path: Path, loss_record: dict[str, Any]) -> None:
        """LOSS レコードは保存されないこと"""
        output_file = tmp_path / "finetune_dataset.jsonl"
        generator = DatasetGenerator(output_path=str(output_file))

        saved = generator.save(loss_record)

        assert saved is False
        assert not output_file.exists()

    def test_save_filters_draw(self, tmp_path: Path, draw_record: dict[str, Any]) -> None:
        """DRAW レコードは保存されないこと"""
        output_file = tmp_path / "finetune_dataset.jsonl"
        generator = DatasetGenerator(output_path=str(output_file))

        saved = generator.save(draw_record)

        assert saved is False

    def test_save_filters_win_below_threshold(
        self, tmp_path: Path, win_record_low_rate: dict[str, Any]
    ) -> None:
        """WIN だが profit_loss_rate < 0.02 のレコードは保存されないこと"""
        output_file = tmp_path / "finetune_dataset.jsonl"
        generator = DatasetGenerator(output_path=str(output_file))

        saved = generator.save(win_record_low_rate)

        assert saved is False

    def test_save_deduplication(self, tmp_path: Path, win_record: dict[str, Any]) -> None:
        """同一 trade_id のレコードは2回目以降保存されないこと（重複排除）"""
        output_file = tmp_path / "finetune_dataset.jsonl"
        generator = DatasetGenerator(output_path=str(output_file))

        first = generator.save(win_record)
        second = generator.save(win_record)

        assert first is True
        assert second is False

        lines = output_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1

    def test_save_multiple_records(
        self, tmp_path: Path, win_record: dict[str, Any]
    ) -> None:
        """複数の WIN レコードが正しく追記されること"""
        output_file = tmp_path / "finetune_dataset.jsonl"
        generator = DatasetGenerator(output_path=str(output_file))

        win_record2 = _make_trade_record(
            trade_id="win-002",
            trade_outcome="WIN",
            profit_loss_rate=0.05,
            ticker_symbol="9432.T",
        )

        generator.save(win_record)
        generator.save(win_record2)

        lines = output_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_dedup_across_instances(
        self, tmp_path: Path, win_record: dict[str, Any]
    ) -> None:
        """既存ファイルに保存済みの trade_id は、新しいインスタンスでも重複保存されないこと"""
        output_file = tmp_path / "finetune_dataset.jsonl"

        gen1 = DatasetGenerator(output_path=str(output_file))
        gen1.save(win_record)

        # 新しいインスタンスで同じレコードを保存しようとする
        gen2 = DatasetGenerator(output_path=str(output_file))
        second = gen2.save(win_record)

        assert second is False
        lines = output_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# DatasetGenerator.process_log_file のユニットテスト
# ---------------------------------------------------------------------------


class TestProcessLogFile:
    """ログファイル一括処理のテスト"""

    def test_process_log_file_extracts_eligible_records(self, tmp_path: Path) -> None:
        """ログファイルから条件を満たすレコードのみ抽出・保存されること"""
        log_file = tmp_path / "trade_logs.jsonl"
        output_file = tmp_path / "finetune_dataset.jsonl"

        records = [
            _make_trade_record("win-a", "WIN", 0.03),
            _make_trade_record("loss-b", "LOSS", -0.02),
            _make_trade_record("win-c", "WIN", 0.025),
            _make_trade_record("draw-d", "DRAW", 0.001),
            _make_trade_record("win-low-e", "WIN", 0.005),
        ]
        with open(log_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        generator = DatasetGenerator(output_path=str(output_file))
        count = generator.process_log_file(str(log_file))

        assert count == 2  # win-a と win-c のみ
        lines = output_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_process_log_file_skips_duplicates(self, tmp_path: Path) -> None:
        """同じログファイルを2回処理しても重複が発生しないこと"""
        log_file = tmp_path / "trade_logs.jsonl"
        output_file = tmp_path / "finetune_dataset.jsonl"

        record = _make_trade_record("win-001", "WIN", 0.03)
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        generator = DatasetGenerator(output_path=str(output_file))
        generator.process_log_file(str(log_file))
        second_count = generator.process_log_file(str(log_file))

        assert second_count == 0
        lines = output_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
