from dataclasses import dataclass
from typing import Literal

from src.analyzer import SentimentAnalysisResult
from src.collector import StockData


@dataclass
class DecisionResult:
    """取引判定結果を保持するクラス"""

    final_action: Literal["BUY", "HOLD"]
    is_buy_triggered: bool
    reason: str


class TradeDecisionMaker:
    """テクニカル指標とAIセンチメントスコアによる複合取引判定を行うクラス"""

    def make_decision(
        self, stock_data: StockData, sentiment_result: SentimentAnalysisResult
    ) -> DecisionResult:
        """
        テクニカル指標(MA25トレンド)およびAIセンチメント分析に基づき最終的な売買判断を行う
        """
        reasons = []

        is_ma25_upward = stock_data.ma25_trend == "UPWARD"
        if not is_ma25_upward:
            reasons.append(
                f"25日移動平均線が上向きではありません (ma25_trend={stock_data.ma25_trend})"
            )

        is_score_high = sentiment_result.sentiment_score >= 4.0
        if not is_score_high:
            reasons.append(
                f"AIセンチメントスコアが基準値(4.0)未満です "
                f"(score={sentiment_result.sentiment_score})"
            )

        if is_ma25_upward and is_score_high:
            return DecisionResult(
                final_action="BUY",
                is_buy_triggered=True,
                reason="判定成功: 25日移動平均線がUPWARDかつAIセンチメントスコアが4.0以上です。",
            )

        return DecisionResult(
            final_action="HOLD",
            is_buy_triggered=False,
            reason=" / ".join(reasons),
        )
