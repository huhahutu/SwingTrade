import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

import yfinance as yf

# 損益がこの閾値内（絶対値）なら DRAW と判定する
_DRAW_THRESHOLD = 0.005  # ±0.5%


@dataclass
class EvaluationResult:
    """取引評価結果を保持するデータクラス"""

    trade_id: str
    ticker_symbol: str
    sold_price: float
    profit_loss_rate: float
    holding_period_days: int
    trade_outcome: Literal["WIN", "LOSS", "DRAW"]


class TradeEvaluator:
    """
    trade_logs.jsonl の BUY レコードを対象に、
    yfinance から N日後の株価を取得して損益率と trade_outcome を計算・更新するクラス
    """

    def __init__(self, holding_days: int = 5) -> None:
        self.holding_days = holding_days

    def evaluate(self, record: dict[str, Any]) -> EvaluationResult | None:
        """
        1件の取引ログを評価する。

        bought_price が None のレコード（HOLD判定など）、
        またはすでに trade_outcome が確定済み (None, "DRAW", "" 以外) のレコードは
        スキップして None を返す。
        """
        bought_price: float | None = record["execution_result"]["bought_price"]
        outcome = record.get("trade_outcome")
        if bought_price is None or outcome not in [None, "DRAW", ""]:
            return None

        ticker_symbol: str = record["ticker_symbol"]
        trade_date: str = record["date"]

        # 評価日（買付日 + holding_days 営業日後の近似）
        buy_date = date.fromisoformat(trade_date)
        eval_date = buy_date + timedelta(days=self.holding_days)
        # yfinance の history は end 日付を含まないため +1日
        fetch_end = eval_date + timedelta(days=1)

        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(
            start=buy_date.isoformat(),
            end=fetch_end.isoformat(),
        )

        if df.empty:
            return None

        # 取得できた最後の営業日終値を売却価格として使用
        sold_price = float(df["Close"].iloc[-1])
        actual_holding_days = len(df) - 1  # 買付日を含まない取引日数

        # 損益率の計算: (売却価格 - 買付価格) / 買付価格
        profit_loss_rate = (sold_price - bought_price) / bought_price

        # 勝敗判定
        if abs(profit_loss_rate) <= _DRAW_THRESHOLD:
            outcome_str: Literal["WIN", "LOSS", "DRAW"] = "DRAW"
        elif profit_loss_rate > 0:
            outcome_str = "WIN"
        else:
            outcome_str = "LOSS"

        return EvaluationResult(
            trade_id=record["trade_id"],
            ticker_symbol=ticker_symbol,
            sold_price=sold_price,
            profit_loss_rate=round(profit_loss_rate, 6),
            holding_period_days=actual_holding_days,
            trade_outcome=outcome_str,
        )

    def update_log_file(
        self,
        file_path: str,
        sync_rag: bool = True,
        chroma_dir: str | None = "data/chroma_db",
    ) -> None:
        """
        trade_logs.jsonl を読み込み、評価結果（損益率・trade_outcome）を上書き保存する。
        sync_rag が True の場合は Chroma DB にも同期する。
        """
        with open(file_path, encoding="utf-8") as f:
            records: list[dict[str, Any]] = [json.loads(line) for line in f if line.strip()]

        updated_records: list[dict[str, Any]] = []
        for record in records:
            result = self.evaluate(record)
            if result is not None:
                # execution_result を更新
                record["execution_result"]["sold_price"] = result.sold_price
                record["execution_result"]["profit_loss_rate"] = result.profit_loss_rate
                record["execution_result"]["holding_period_days"] = result.holding_period_days
                record["trade_outcome"] = result.trade_outcome
            updated_records.append(record)

        with open(file_path, "w", encoding="utf-8") as f:
            for record in updated_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"[evaluator] {len(updated_records)} 件のレコードを更新しました: {file_path}")

        if sync_rag:
            try:
                from src.rag_store import RagStore

                store = RagStore(persist_directory=chroma_dir)
                synced_count = store.sync_from_trade_logs(jsonl_path=file_path)
                print(f"[evaluator] {synced_count} 件のレコードを Chroma DB に同期しました。")
            except Exception as e:
                print(f"[evaluator] Chroma DB 同期中に警告が発生しました: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="trade_logs.jsonl の損益率および trade_outcome を自動計算・上書き保存する"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="data/trade_logs.jsonl",
        help="評価対象のログファイルパス",
    )
    parser.add_argument(
        "--holding-days",
        type=int,
        default=5,
        help="評価する保有日数（デフォルト: 5日）",
    )
    args = parser.parse_args()

    evaluator = TradeEvaluator(holding_days=args.holding_days)
    evaluator.update_log_file(args.log_file)
