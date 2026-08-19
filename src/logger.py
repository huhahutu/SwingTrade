from datetime import datetime
import json
from pathlib import Path
import uuid
from src.collector import StockData
from src.analyzer import SentimentAnalysisResult
from src.decision import DecisionResult


class KnowledgeLogger:
    """判定結果を JSON Lines 形式でナレッジログとして保存するクラス"""

    def __init__(self, file_path: str = "data/trade_logs.jsonl") -> None:
        self.file_path = Path(file_path)

    def log_trade_decision(
        self,
        stock_data: StockData,
        sentiment_result: SentimentAnalysisResult,
        decision_result: DecisionResult,
    ) -> dict:
        """
        取引判定結果をDocs/design.mdおよびknowledge_rag.mdの仕様に沿ってJSONLファイルへ保存する
        """
        record = {
            "trade_id": str(uuid.uuid4()),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ticker_symbol": stock_data.ticker_symbol,
            "ai_score": sentiment_result.sentiment_score,
            "ai_action_reason": f"AI Action={sentiment_result.action}: {sentiment_result.catalyst_summary}",
            "technical_indicators": {
                "ma25_trend": stock_data.ma25_trend,
                "entry_price": stock_data.latest_close,
            },
            "execution_result": {
                "bought_price": stock_data.latest_close if decision_result.final_action == "BUY" else None,
                "sold_price": None,
                "profit_loss_rate": None,
                "stop_loss_triggered": None,
                "holding_period_days": None,
            },
            "trade_outcome": None,
            "post_analysis_notes": f"Final Decision: {decision_result.final_action}. Reason: {decision_result.reason}",
        }

        # 保存先ディレクトリが存在しない場合は作成
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # JSONLines形式で追記保存
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # Dapr State Store への保存 (Dapr稼働時のみ)
        import os
        if os.getenv("DAPR_GRPC_PORT") or os.getenv("DAPR_HTTP_PORT"):
            from dapr.clients import DaprClient # type: ignore
            try:
                with DaprClient() as client:
                    client.save_state(
                        store_name="statestore",
                        key=f"trade_{record['trade_id']}",
                        value=json.dumps(record, ensure_ascii=False)
                    )
            except Exception as e:
                print(f"[Warning] Dapr State Store への保存に失敗しました: {e}")

        return record
