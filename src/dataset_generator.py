"""
src/dataset_generator.py

フェーズ3: ファインチューニング用データ自動生成パイプライン

WIN トレード（trade_outcome == "WIN" かつ profit_loss_rate >= 0.02）を
自動抽出し、Gemini API ファインチューニング用 JSONL 形式に変換・保存する。
"""

import json
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel

# ファインチューニング対象とする最低損益率（+2.0%）
_MIN_PROFIT_LOSS_RATE: Final[float] = 0.02

# Gemini ファインチューニング用のシステムプロンプト
_SYSTEM_PROMPT: Final[str] = (
    "あなたは株価センチメントアナリストです。"
    "ニュース本文とテクニカル指標に基づき、短期的な株価カタリストを評価して"
    "JSONで出力してください。"
)


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """Gemini ファインチューニング用の1メッセージを表すモデル"""

    role: str
    content: str


class FinetuneRecord(BaseModel):
    """Gemini ファインチューニング用の1サンプルレコードを表すモデル"""

    messages: list[Message]

    @classmethod
    def from_trade_record(cls, record: dict[str, Any]) -> "FinetuneRecord":
        """
        取引ログレコードから FinetuneRecord を構築する。

        Args:
            record: trade_logs.jsonl の1レコード（dict）

        Returns:
            FinetuneRecord: system / user / model メッセージを持つレコード
        """
        ticker_symbol: str = record.get("ticker_symbol", "")
        news_content: str = record.get("news_content", "")
        catalyst_summary: str = record.get("catalyst_summary", "")
        risk_factors: str = record.get("risk_factors", "")
        ai_score: float = float(record.get("ai_score", 0.0))
        technical: dict[str, Any] = record.get("technical_indicators", {})
        ma25_trend: str = str(technical.get("ma25_trend", ""))

        # --- user メッセージ: 入力特徴量 ---
        user_content = (
            f"【銘柄】: {ticker_symbol}\n"
            f"【移動平均線】: {ma25_trend}\n"
            f"【ニュース本文】: {news_content}"
        )

        # --- model メッセージ: 正解ラベル（AI の理想的な出力） ---
        model_output: dict[str, Any] = {
            "ticker_symbol": ticker_symbol,
            "sentiment_score": ai_score,
            "action": "BUY",
            "catalyst_summary": catalyst_summary,
            "risk_factors": risk_factors,
            "confidence_level": round(min(ai_score / 5.0, 1.0), 2),
        }

        return cls(
            messages=[
                Message(role="system", content=_SYSTEM_PROMPT),
                Message(role="user", content=user_content),
                Message(role="model", content=json.dumps(model_output, ensure_ascii=False)),
            ]
        )

    def to_jsonl_line(self, trade_id: str = "") -> str:
        """
        Gemini ファインチューニング形式の JSON 文字列（1行）を返す。

        重複排除のため trade_id をトップレベルフィールドとして含める。
        Gemini API への投入時は messages フィールドのみ利用する。

        Args:
            trade_id: 重複排除用の取引識別子

        Returns:
            str: {"trade_id": "...", "messages": [...]} 形式の JSON 文字列
        """
        payload: dict[str, Any] = {
            "trade_id": trade_id,
            "messages": [
                {"role": msg.role, "content": msg.content} for msg in self.messages
            ],
        }
        return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# DatasetGenerator
# ---------------------------------------------------------------------------


class DatasetGenerator:
    """
    WIN トレードを自動抽出し、ファインチューニング用 JSONL へ保存するクラス。

    副作用（ファイル読み書き）は save() および process_log_file() に集約し、
    フィルタリングロジック（is_eligible）は純粋な静的メソッドとして実装する。
    """

    def __init__(self, output_path: str = "data/finetune_dataset.jsonl") -> None:
        """
        Args:
            output_path: 保存先の JSONL ファイルパス
        """
        self._output_path = Path(output_path)
        # 起動時に既存ファイルから保存済み trade_id をメモリへロード（重複排除用）
        self._saved_ids: set[str] = self._load_existing_ids()

    # ------------------------------------------------------------------
    # 純粋関数（副作用なし）
    # ------------------------------------------------------------------

    @staticmethod
    def is_eligible(record: dict[str, Any]) -> bool:
        """
        レコードがファインチューニング対象かどうかを判定する。

        抽出基準:
            - trade_outcome == "WIN"
            - profit_loss_rate >= 0.02（+2.0%以上）

        Args:
            record: trade_logs.jsonl の1レコード

        Returns:
            bool: 抽出対象であれば True
        """
        if record.get("trade_outcome") != "WIN":
            return False

        profit_loss_rate: float | None = record.get("execution_result", {}).get(
            "profit_loss_rate"
        )
        if profit_loss_rate is None:
            return False

        return float(profit_loss_rate) >= _MIN_PROFIT_LOSS_RATE

    # ------------------------------------------------------------------
    # 副作用を持つメソッド
    # ------------------------------------------------------------------

    def save(self, record: dict[str, Any]) -> bool:
        """
        1件の取引ログを評価し、条件を満たす場合のみ JSONL へ追記保存する。

        重複排除: 同一 trade_id は保存しない。

        Args:
            record: trade_logs.jsonl の1レコード

        Returns:
            bool: 保存が実行された場合 True、スキップした場合 False
        """
        if not self.is_eligible(record):
            return False

        trade_id: str = str(record.get("trade_id", ""))
        if trade_id in self._saved_ids:
            return False

        ft_record = FinetuneRecord.from_trade_record(record)
        line = ft_record.to_jsonl_line(trade_id=trade_id)

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._output_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        self._saved_ids.add(trade_id)
        return True

    def process_log_file(self, log_file_path: str) -> int:
        """
        trade_logs.jsonl を読み込み、条件を満たすレコードを一括処理して保存する。

        Args:
            log_file_path: 読み込む trade_logs.jsonl のパス

        Returns:
            int: 今回新たに保存したレコード数
        """
        saved_count = 0
        with open(log_file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record: dict[str, Any] = json.loads(line)
                if self.save(record):
                    saved_count += 1
        return saved_count

    # ------------------------------------------------------------------
    # プライベートヘルパー
    # ------------------------------------------------------------------

    def _load_existing_ids(self) -> set[str]:
        """
        既存の JSONL ファイルから保存済み trade_id を読み取る。

        ファイルが存在しない場合は空集合を返す。

        Returns:
            set[str]: 保存済み trade_id の集合
        """
        if not self._output_path.exists():
            return set()

        saved_ids: set[str] = set()
        with open(self._output_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload: dict[str, Any] = json.loads(line)
                    # messages[1] (user) のコンテンツから trade_id を復元するのは
                    # 複雑すぎるため、保存時に trade_id をメタとして埋め込む
                    # ただし後方互換のため KeyError は無視する
                    tid = payload.get("trade_id")
                    if tid is not None:
                        saved_ids.add(str(tid))
                except json.JSONDecodeError:
                    continue
        return saved_ids
