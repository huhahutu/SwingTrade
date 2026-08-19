from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class SentimentAnalysisResult(BaseModel):
    """Gemini 2.5 Flash によるセンチメント解析結果のJSON Schemaモデル"""

    ticker_symbol: str = Field(..., description="銘柄コード (例: 7203.T)")
    sentiment_score: float = Field(
        ..., ge=1.0, le=5.0, description="センチメントスコア (1.0 - 5.0)"
    )
    action: Literal["BUY", "SELL", "HOLD"] = Field(
        ..., description="推薦アクション (BUY, SELL, HOLD)"
    )
    catalyst_summary: str = Field(..., description="判定の根拠となった重要ニュースの要約")
    risk_factors: str = Field(..., description="材料出尽くしや一時的要因などの懸念点")
    confidence_level: float = Field(..., ge=0.0, le=1.0, description="AIの確信度 (0.0 - 1.0)")


class SentimentAnalyzer:
    """Gemini 2.5 Flash API を利用してニューステキストのセンチメント解析を行うアナライザー"""

    def __init__(self, api_key: str | None = None) -> None:
        if api_key:
            self.api_key = api_key
        else:
            from src.secrets import get_secret

            try:
                self.api_key = get_secret("GEMINI_API_KEY")
            except Exception as e:
                raise ValueError(f"GEMINI_API_KEY の取得に失敗しました: {e}")

        self.client = genai.Client(api_key=self.api_key)

    def analyze_news(self, ticker_symbol: str, news_text: str) -> SentimentAnalysisResult:
        """
        指定銘柄のニューステキストを分析し、構造化されたセンチメント評価結果を返す
        """
        prompt = f"""
以下の株式ニューステキストを分析し、指定されたJSONフォーマットに従って評価結果を出力してください。

対象銘柄コード: {ticker_symbol}
ニュース本文:
{news_text}
"""

        response = self.client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SentimentAnalysisResult,
            ),
        )

        # レスポンス文字列をPydanticモデルにバリデーションパース
        response_text = response.text
        if not response_text:
            raise ValueError("Gemini APIからのレスポンスが空です。")

        return SentimentAnalysisResult.model_validate_json(response_text)
