# テストガイド

## テストファイル一覧

### 基本テスト

#### 1. `test_module_split.py` - モジュールインポートテスト
**目的:** モジュール分割後の動作確認
**内容:**
- `models.py`, `datastore.py`, `server.py`が正しくインポートできるかテスト
- 基本的な構文エラーチェック

**実行:**
```bash
python -m backend.test.test_module_split
```

---

#### 2. `test_basic_integration.py` - 基本統合テスト
**目的:** 認証不要エンドポイントのテスト
**内容:**
- ヘルスチェック（`GET /`）
- 基本的なAPIレスポンス確認

**実行:**
```bash
python -m backend.test.test_basic_integration
```

---

### API機能テスト

#### 3. `test_restful_api.py` - RESTful APIテスト
**目的:** RESTfulエンドポイントの存在確認
**内容:**
- 各エンドポイントが正しく定義されているか確認
- ルーティングのテスト

**実行:**
```bash
python -m backend.test.test_restful_api
```

---

#### 4. `test_nfc_auth.py` - NFC認証テスト
**目的:** NFC認証機能のテスト
**内容:**
- NFC登録
- NFC認証
- NFC登録解除

**実行:**
```bash
python -m backend.test.test_nfc_auth
```

---

### 統合テスト

#### 5. `test_integration.py` - 統合テスト
**目的:** 基本的な統合フロー
**内容:**
- ユーザー作成 → チャット → セッション確認 → クローズ → 再起動後の確認

**実行:**
```bash
python -m backend.test.test_integration
```

---

#### 6. `test_firebase_integration.py` - Firebase統合テスト
**目的:** Firebase Custom Tokenを使った統合テスト
**内容:**
- Firebase認証フロー
- Custom Token発行
- 認証済みAPIアクセス

**実行:**
```bash
python -m backend.test.test_firebase_integration
```

---

#### 7. `test_comprehensive_integration.py` - 包括的統合テスト
**目的:** サーバー再起動を含む全機能テスト（NFCを除く）
**内容:**
- ユーザー作成
- チャット機能
- セッション管理
- サーバー再起動後の永続化確認

**実行:**
```bash
python -m backend.test.test_comprehensive_integration
```

---

### セッション管理テスト

#### 8. `test_session_persistence.py` - セッション永続化テスト
**目的:** サーバー再起動前後でセッションが保持されることを確認
**内容:**
- セッション作成
- サーバー再起動
- セッション復元確認

**実行:**
```bash
python -m backend.test.test_session_persistence
```

---

#### 9. `test_session_timeout.py` - セッションタイムアウトテスト
**目的:** セッションタイムアウト機能のテスト
**内容:**
- ユーザータイムアウト（ユーザー単位）
- 非アクティブセッションの自動クローズ

**実行:**
```bash
python -m backend.test.test_session_timeout
```

---

## 推奨テスト順序

### 1. 基本チェック（開発中）
```bash
# モジュールインポート確認
python -m backend.test.test_module_split

# 基本API確認
python -m backend.test.test_basic_integration
```

### 2. 機能テスト（機能追加後）
```bash
# RESTful API確認
python -m backend.test.test_restful_api

# NFC認証確認
python -m backend.test.test_nfc_auth
```

### 3. 統合テスト（リリース前）
```bash
# 基本統合テスト
python -m backend.test.test_integration

# Firebase統合テスト
python -m backend.test.test_firebase_integration

# 包括的統合テスト（最も重要）
python -m backend.test.test_comprehensive_integration
```

### 4. セッション管理テスト（本番環境想定）
```bash
# セッション永続化
python -m backend.test.test_session_persistence

# タイムアウト機能
python -m backend.test.test_session_timeout
```

---

## 全テスト実行

```bash
# すべてのテストを順番に実行
for test in test_module_split test_basic_integration test_restful_api test_nfc_auth test_integration test_firebase_integration test_comprehensive_integration test_session_persistence test_session_timeout; do
    echo "========================================="
    echo "Running: $test"
    echo "========================================="
    python -m backend.test.$test
    echo
done
```

---

## テスト前の準備

### 1. サーバー起動
```bash
# 仮想環境をアクティベート
source .venv/bin/activate

# サーバー起動
python -m backend.run
```

### 2. 環境変数設定
`.env`ファイルに以下を設定：
```bash
# Firebase
FIREBASE_ACCOUNT_KEY_PATH=path/to/serviceAccountKey.json

# LLM Backend
LLM_BACKEND=gemini  # または ollama
GEMINI_API_KEY1=your_key

# MongoDB（オプション）
MONGODB_URI=mongodb://localhost:27017
```

---

## トラブルシューティング

### テストが失敗する場合

1. **サーバーが起動しているか確認**
   ```bash
   curl http://localhost:8000/
   ```

2. **環境変数が設定されているか確認**
   ```bash
   python -c "import os; print(os.getenv('GEMINI_API_KEY1'))"
   ```

3. **依存関係がインストールされているか確認**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **データファイルをクリア**
   ```bash
   rm -rf data/*.json
   ```
