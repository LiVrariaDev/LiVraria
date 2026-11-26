# バックエンドテスト

このディレクトリには、モジュール、REST API、NFC 認証、セッション永続化・タイムアウト、Firebase を対象とするテストスクリプトがある。

## 実行前の注意

多くのテストは、起動済みのバックエンド、Firebase 設定、Gemini を含む `.env` 設定、または既存データを前提にしている。テストが完全に自己完結していることは確認できていない。

データファイルを削除する手順はここには載せない。`backend/api/data/` は実行時データであるため、必要ならバックアップと対象を確認してから個別に扱う。

## 実行方法

リポジトリルートでバックエンドをセットアップし、別ターミナルで起動する。

```bash
pnpm run install:back
pnpm run dev:back
```

テストスクリプトは `if __name__ == "__main__"` を持つため、対象を指定して実行する。

```bash
backend/.venv/bin/python backend/test/test_module_split.py
backend/.venv/bin/python backend/test/test_restful_api.py
```

利用する外部サービス、作成・変更するデータ、必要な認証情報は各テストファイルを確認してから実行する。すべてのテストを安全に一括実行できることは未確認である。

## 会話シナリオ（v1 と v2 の比較）

`backend/test/scenarios/` に会話シナリオ（1ファイル1シナリオの JSON）がある。`run_scenarios.py` は、各シナリオを会話グラフ v1 / v2 で流し、応答・推薦書籍・所要時間・LLM の呼び出し回数・通ったノードを `backend/test/scenarios/results/<日時>/` に保存する（`summary.md` が比較表）。**実際の Gemini と楽天を呼ぶ**ため、実行は人が行う。

```bash
backend/.venv/bin/python backend/test/scenarios/run_scenarios.py
backend/.venv/bin/python backend/test/scenarios/run_scenarios.py --graph v2 --only 01_tired_at_work --sleep 5
```
