### AIコーディングツール用 要件定義・仕様ドキュメント

以下のMarkdownテキストをコピーして、AntiGravityやCursorなどのAIエージェントに最初の指示として読み込ませてください。

```markdown
# スイングトレード自動売買システム - プロトタイプ (Phase 1) 開発要件

## 1. プロジェクト概要
特定の日本株銘柄を対象に、移動平均線によるトレンド判定と、Gemini 2.5 Flashによるニュースのセンチメント分析を組み合わせたスイングトレードの自動判定プログラムを構築する。
本フェーズではPythonを用いたMVP（Minimum Viable Product）を作成し、AIの判定精度と売買ルールの検証を行うことを目的とする。実際の発注処理は行わず、コンソールへの出力とログファイルへの保存のみを行う。

## 2. 技術スタック
* 言語: Python 3.10以上
* 主要ライブラリ: yfinance, google-generativeai, pydantic (JSONスキーマ定義用), python-dotenv

## 3. 実装機能要件

### 3.1 収集機能 (Data Collection)
* `yfinance` を使用し、指定した銘柄（例: "7203.T"）の前日終値および25日移動平均線を取得する。
* 移動平均線のトレンド（UPWARD / FLAT / DOWNWARD）を判定する。
* ニュースデータ取得は今回はモックとし、テスト用のニューステキスト（文字列）を受け取る関数として実装する。

### 3.2 分析機能 (AI Sentiment Analysis)
* Gemini 2.5 Flash API を使用する。
* ニュース原文をGeminiにインプットし、以下のJSON Schemaに厳密に従って結果を出力させる。
```json
{
  "ticker_symbol": "STRING",
  "sentiment_score": "FLOAT (1.0 - 5.0)",
  "action": "BUY | SELL | HOLD",
  "catalyst_summary": "STRING (判定の根拠となった重要ニュースの要約)",
  "risk_factors": "STRING (材料出尽くしや一時的要因などの懸念点)",
  "confidence_level": "FLOAT (0.0 - 1.0)"
}

```

### 3.3 取引判定機能 (Trade Decision)

* 以下の2つの条件を両方満たした場合のみ、最終的な取引アクションを「BUY」とする。
* 条件A: 25日移動平均線が上向き（UPWARD）であること。
* 条件B: AIの `sentiment_score` が 4.0 以上であること。
* それ以外の場合は、AIの `action` が BUY であっても見送る（HOLD等として扱う）。

### 3.4 ログ出力機能 (Knowledge Logging)

* 判定完了後、将来のRAGおよびファインチューニング用に、以下のフォーマットで結果を `trade_logs.jsonl` (JSON Lines形式) に追記保存する。

```json
{
  "trade_id": "STRING (UUID)",
  "date": "YYYY-MM-DD",
  "ticker_symbol": "STRING",
  "ai_score": "FLOAT",
  "ai_action_reason": "STRING",
  "catalyst_summary": "STRING",
  "risk_factors": "STRING",
  "technical_indicators": {
    "ma25_trend": "UPWARD | FLAT | DOWNWARD",
    "entry_price": "NUMBER (現在値・前日終値)"
  },
  "execution_result": {
    "bought_price": null,
    "sold_price": null,
    "profit_loss_rate": null,
    "stop_loss_triggered": null,
    "holding_period_days": null
  },
  "trade_outcome": null,
  "post_analysis_notes": ""
}

```

※ `execution_result` と `trade_outcome` は初期段階では未決済のため null を設定しておく。

## 4. 成果物

上記の一連のフロー（データ取得 -> AI判定 -> ロジック判定 -> ログ保存）を実行できるPythonスクリプト（`main.py` および必要に応じたモジュール分割）を作成してください。
