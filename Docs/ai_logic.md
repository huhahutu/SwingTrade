# AI判定ロジック仕様書

## 概要
Gemini 2.5 Flash を使用し、ニュース・適時開示からポジティブ度（1.0〜5.0）を算出する。

## JSON出力フォーマット要件
AIからのレスポンスは必ず以下のスキーマに従うこと。
```json
{
  "ticker_symbol": "STRING",
  "sentiment_score": "FLOAT (1.0 - 5.0)",
  "action": "BUY | SELL | HOLD",
  "catalyst_summary": "STRING",
  "risk_factors": "STRING",
  "confidence_level": "FLOAT (0.0 - 1.0)"
}