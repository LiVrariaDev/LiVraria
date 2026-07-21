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
