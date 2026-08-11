# SwingTrade
AI駆動型スイングトレード自動売買システム

## 概要
AI（Gemini 2.5 Flash）によるニュース分析、テクニカル指標との融合、そして取引結果の継続的な学習を通じて、スイングトレードの勝率向上を目指す自動売買システムです。

## 特徴
- **AIセンチメント分析**: ニュースや適時開示から銘柄のセンチメントを定量化（1.0〜5.0）。
- **テクニカル指標との融合**: 移動平均線（25日線）の上昇トレンドを必須条件として加点方式で判定。
- **RAGによる自己学習**: 過去の取引事例（特に失敗事例）をAIに参照させ、リアルタイムの判定精度を向上。
- **継続的なモデル改善**: 取引結果を自動で蓄積し、ファインチューニング用データセットを生成。

## ディレクトリ構成
```
SwingTrade/
├── .env                 # 環境変数 (APIキー等)
├── requirements.txt     # 依存ライブラリ
├── main.py              # メイン実行スクリプト
├── src/
│   ├── collector.py     # データ収集 (yfinance,ニュース)
│   ├── analyzer.py      # AI分析ロジック
│   ├── decision.py      # 複合売買判定ロジック
│   ├── logger.py        # ナレッジログ保存
│   └── knowledge/       # RAG・ファインチューニング関連
├── tests/               # pytest テストコード一覧
│   ├── test_collector.py
│   ├── test_analyzer.py
│   ├── test_decision.py
│   ├── test_logger.py
│   └── test_main.py
├── docs/
│   ├── design.md        # システム設計書
│   ├── ai_logic.md      # AI判定ロジック
│   └── knowledge_rag.md # RAG・ナレッジ蓄積仕様書
└── data/
    ├── trade_logs.jsonl # 取引ログ
    └── ft_dataset.jsonl # ファインチューニング用データ
```

## 環境構築
1. **仮想環境の作成と有効化**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Mac/Linux
   ```

2. **依存ライブラリのインストール**
   ```bash
   pip install -r requirements.txt
   ```

3. **APIキーの設定**
   `.env` ファイルに以下の変数を設定してください。
   ```
   GEMINI_API_KEY="your_api_key_here"
   ```

## 実行方法

### 基本的な実行（データ収集からAI判定まで）
```bash
pip install -r requirements.txt
python main.py --ticker 7203.T
```

### RAGを活用した高度な分析
```bash
python main.py --ticker 7203.T --use-rag
```

### 取引ログの勝敗判定・結果更新
蓄積された `trade_logs.jsonl` を読み込み、指定日数後（デフォルト5日）の株価に基づいて損益率と勝敗（WIN/LOSS/DRAW）を自動計算し、ログファイルを更新します。

```bash
# デフォルト（5日後で評価）
python -m src.evaluator --log-file data/trade_logs.jsonl

# 保有期間を変える場合（例: 10日後）
python -m src.evaluator --log-file data/trade_logs.jsonl --holding-days 10
```

## テストの実行方法
本プロジェクトでは `pytest` を使用したテスト駆動開発（TDD）を採用しています。外部API (`yfinance`, Gemini API) 通信はすべてモック化されているため、APIキーなしで安全かつ高速に実行可能です。

### 全テストの実行
```bash
pytest
# または
python -m pytest
```

### モジュール別の個別テスト実行
```bash
# データ収集モジュールのテスト
pytest tests/test_collector.py

# AIセンチメント分析モジュールのテスト
pytest tests/test_analyzer.py

# 取引判定モジュールのテスト
pytest tests/test_decision.py

# ナレッジログ保存モジュールのテスト
pytest tests/test_logger.py

# メインパイプラインの統合テスト
pytest tests/test_main.py
```

### 詳細ログ付きで実行
```bash
pytest -v
```

## ライブラリ構成
| カテゴリ | ライブラリ | 用途 |
| :--- | :--- | :--- |
| **データ分析** | `pandas` | データ処理、テクニカル指標計算 |
| **AI/機械学習** | `google-genai` | Gemini APIとの連携 |
| **数値計算** | `numpy` | 科学技術計算 |
| **データ保存** | `pydantic` | データバリデーション、型安全 |
| **テスト** | `pytest`, `pytest-mock` | テストフレームワーク、モック |
| **環境変数** | `python-dotenv` | 環境変数の管理 |

## ライセンス
MIT License

