# LiVraria フロントエンド技術仕様書

> [!IMPORTANT]
> このドキュメントはAIによって生成されています。
> そのため、誤字脱字や不正確な情報が含まれている可能性があります。

## 1. はじめに

本技術仕様書は、AI司書アプリケーション「LiVraria」のフロントエンド開発を担当するエンジニアを対象とする。LiVrariaのフロントエンドは、ユーザーとAI司書との自然な対話を実現するためのインターフェースを提供し、直感的で応答性の高いユーザー体験を提供することを目的としている。

本仕様書では、フロントエンドの技術スタック、コンポーネント設計、状態管理、API通信、認証フロー、そしてスタイリングについて詳細に解説する。

## 2. 技術スタック

### 2.1. コア技術

| 技術 | バージョン | 用途 |
|------|-----------|------|
| **Vue 3** | ^3.5.18 | プログレッシブJavaScriptフレームワーク |
| **Vite** | ^7.3.0 | 高速ビルドツール・開発サーバー |
| **Node.js** | ^20.19.0 \|\| >=22.12.0 | JavaScript実行環境 |
| **pnpm** | 10.14.0 | パッケージマネージャー |

### 2.2. 主要ライブラリ

#### 認証・データベース
- **Firebase** (^12.7.0)
  - Firebase Authentication: ユーザー認証
  - Firebase Firestore: リアルタイムデータベース（オプション）

#### スタイリング
- **TailwindCSS** (^4.1.17): ユーティリティファーストCSS
- **@tailwindcss/postcss** (^4.1.17): PostCSSプラグイン
- **Autoprefixer** (^10.4.22): ベンダープレフィックス自動付与

#### 開発ツール
- **@vitejs/plugin-vue** (^6.0.3): ViteのVueプラグイン
- **vite-plugin-vue-devtools** (^8.0.5): Vue DevTools統合

### 2.3. ビルド設定

**pnpm設定:**
```json
{
  "onlyBuiltDependencies": [
    "@firebase/util",
    "esbuild",
    "protobufjs"
  ]
}
```

これにより、特定のパッケージのみビルド時に依存関係を解決し、ビルド時間を最適化している。

## 3. プロジェクト構造

```
frontend/
├── src/
│   ├── App.vue                 # ルートコンポーネント
│   ├── main.js                 # エントリーポイント
│   ├── style.css               # グローバルスタイル
│   ├── firebaseConfig.js       # Firebase設定
│   ├── components/             # Vueコンポーネント
│   │   ├── Login.vue           # ログインコンポーネント
│   │   ├── MainApp.vue         # メインアプリケーション
│   │   ├── HelloWorld.vue      # サンプルコンポーネント
│   │   ├── TheWelcome.vue      # ウェルカム画面
│   │   ├── WelcomeItem.vue     # ウェルカムアイテム
│   │   └── icons/              # アイコンコンポーネント
│   ├── services/               # APIサービス
│   │   └── api.js              # バックエンドAPI通信
│   └── assets/                 # 静的アセット
├── public/                     # 公開ディレクトリ
├── index.html                  # HTMLエントリーポイント
├── vite.config.js              # Vite設定
├── tailwind.config.js          # TailwindCSS設定
├── postcss.config.js           # PostCSS設定
├── package.json                # パッケージ定義
└── Dockerfile                  # Docker設定
```

## 4. コンポーネント設計

### 4.1. App.vue（ルートコンポーネント）

**役割:** アプリケーション全体のルートコンポーネント。認証状態に応じてLoginまたはMainAppを表示。

**主要機能:**
- Firebase認証状態の監視
- ログイン/ログアウト処理
- コンポーネントの切り替え

### 4.2. Login.vue（ログインコンポーネント）

**役割:** ユーザー認証インターフェース。

**認証方法:**
1. **メール/パスワード認証**
   - Firebase Authentication標準機能
   - `signInWithEmailAndPassword()`

2. **NFC認証**
   - Raspberry Pi上のNFC APIサーバーと連携
   - ポーリング方式でNFC ID取得
   - Custom Token経由でFirebase認証

**NFC認証フロー:**
```javascript
1. ユーザーが「カードで認証」ボタンをクリック
2. バックエンドに /start-nfc リクエスト送信
3. 定期的に /check-nfc をポーリング
4. NFC IDを取得
5. /nfc/auth でCustom Token取得
6. signInWithCustomToken() でFirebase認証
```

### 4.3. MainApp.vue（メインアプリケーション）

**役割:** AI司書との対話インターフェース。

**主要機能:**
1. **チャット機能**
   - メッセージ送受信
   - 会話履歴表示
   - リアルタイム更新

2. **セッション管理**
   - 新規セッション作成
   - セッション継続
   - セッション終了

3. **ユーザー情報表示**
   - プロフィール表示
   - 推薦履歴表示

**状態管理:**
- `messages`: 会話履歴
- `sessionId`: 現在のセッションID
- `isLoading`: ローディング状態
- `user`: ユーザー情報

## 5. API通信（services/api.js）

### 5.1. 設計方針

**ベースURL:**
```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
```

環境変数`VITE_API_BASE_URL`で本番環境のURLを設定可能。

### 5.2. APIエンドポイント

#### ユーザー関連API

**createUser(userData, idToken)**
- **メソッド:** POST
- **エンドポイント:** `/users`
- **用途:** 新規ユーザー作成
- **パラメータ:**
  - `userData`: `{ name, gender, age, live_pref, live_city }`
  - `idToken`: Firebase ID Token

**getUser(userId, idToken)**
- **メソッド:** GET
- **エンドポイント:** `/users/{userId}`
- **用途:** ユーザー情報取得

**updateUser(userId, updates, idToken)**
- **メソッド:** PUT
- **エンドポイント:** `/users/{userId}`
- **用途:** ユーザー情報更新

#### セッション・メッセージ関連API

**sendMessage(sessionId, message, idToken, mode)**
- **メソッド:** POST
- **エンドポイント:** `/sessions/{sessionId}/messages?mode={mode}`
- **用途:** メッセージ送信
- **パラメータ:**
  - `sessionId`: セッションID（新規の場合は`"new"`）
  - `message`: メッセージ内容
  - `mode`: チャットモード（`default`または`librarian`）

**getSession(sessionId, userId, idToken)**
- **メソッド:** GET
- **エンドポイント:** `/sessions/{sessionId}?user_id={userId}`
- **用途:** セッション情報取得

**closeSession(sessionId, idToken)**
- **メソッド:** POST
- **エンドポイント:** `/sessions/{sessionId}/close`
- **用途:** セッション終了

#### NFC認証関連API

**registerNfc(nfcId, userId, idToken)**
- **メソッド:** POST
- **エンドポイント:** `/nfc/register`
- **用途:** NFC登録

**authenticateNfc(nfcId)**
- **メソッド:** POST
- **エンドポイント:** `/nfc/auth`
- **用途:** NFC認証（Custom Token取得）

**unregisterNfc(nfcId, idToken)**
- **メソッド:** POST
- **エンドポイント:** `/nfc/unregister`
- **用途:** NFC登録解除

### 5.3. 認証ヘッダー

すべてのAPI呼び出しに`Authorization`ヘッダーを付与：

```javascript
headers: {
    'Authorization': `Bearer ${idToken}`
}
```

## 6. Firebase認証フロー

### 6.1. 標準認証（メール/パスワード）

```javascript
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth'

const auth = getAuth()
const userCredential = await signInWithEmailAndPassword(auth, email, password)
const idToken = await userCredential.user.getIdToken()
```

### 6.2. NFC認証（Custom Token）

```javascript
import { getAuth, signInWithCustomToken } from 'firebase/auth'

// 1. NFC IDを取得
const nfcId = await pollNfcId()

// 2. Custom Token取得
const { custom_token } = await api.authenticateNfc(nfcId)

// 3. Firebase認証
const auth = getAuth()
const userCredential = await signInWithCustomToken(auth, custom_token)
const idToken = await userCredential.user.getIdToken()
```

### 6.3. 認証状態の監視

```javascript
import { getAuth, onAuthStateChanged } from 'firebase/auth'

const auth = getAuth()
onAuthStateChanged(auth, (user) => {
    if (user) {
        // ログイン済み
        this.user = user
    } else {
        // 未ログイン
        this.user = null
    }
})
```

## 7. スタイリング（TailwindCSS v4）

### 7.1. 設定

**PostCSS設定（postcss.config.js）:**
```javascript
export default {
  plugins: {
    '@tailwindcss/postcss': {}
  }
}
```

> [!IMPORTANT]
> TailwindCSS v4を使用しています。`tailwindcss: {}`ではなく`'@tailwindcss/postcss': {}`を指定してください。

### 7.2. グローバルスタイル（style.css）

```css
@import "tailwindcss";
```

TailwindCSSのユーティリティクラスをインポート。

### 7.3. デザインシステム

**推奨されるデザイン原則:**
- モダンで洗練されたUI
- ダークモード対応（オプション）
- レスポンシブデザイン
- アクセシビリティ対応

## 8. 環境変数

### 8.1. 必須環境変数

```bash
# Firebase設定
VITE_FIREBASE_API_KEY=your_firebase_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id

# バックエンドAPI
VITE_API_BASE_URL=http://localhost:8000  # 開発環境
# VITE_API_BASE_URL=https://your-domain.com/api  # 本番環境
```

### 8.2. 環境変数の使用

Viteでは`import.meta.env`を使用：

```javascript
const apiUrl = import.meta.env.VITE_API_BASE_URL
```

## 9. ビルドとデプロイ

### 9.1. 開発サーバー

```bash
pnpm run dev
```

- **URL:** http://localhost:5173
- **ホットリロード:** 有効

### 9.2. プロダクションビルド

```bash
pnpm run build
```

- **出力ディレクトリ:** `dist/`
- **最適化:** 自動的にコード分割、ミニファイ、Tree Shaking

### 9.3. プレビュー

```bash
pnpm run preview
```

ビルド後のアプリケーションをローカルでプレビュー。

### 9.4. Dockerデプロイ

**Dockerfile:**
```dockerfile
# ビルドステージ
FROM node:22 AS build
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable pnpm && pnpm install
COPY . .
RUN pnpm run build

# プロダクションステージ
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## 10. セキュリティ

### 10.1. Firebase ID Tokenの管理

- ID Tokenは短時間で失効するため、定期的に更新
- `user.getIdToken(true)`で強制的に新しいトークンを取得

### 10.2. CORS設定

バックエンドのCORS設定により、許可されたオリジンからのみアクセス可能。

### 10.3. 環境変数の保護

- `.env`ファイルは`.gitignore`に追加
- 本番環境ではビルド時に環境変数を注入

## 11. 今後の拡張

### 11.1. 状態管理ライブラリ

現在は各コンポーネントで状態を管理しているが、アプリケーションが複雑化した場合、以下の導入を検討：

- **Pinia**: Vue 3公式推奨の状態管理ライブラリ
- **Vuex**: Vue 2/3対応の状態管理ライブラリ

### 11.2. ルーティング

複数ページが必要になった場合：

- **Vue Router**: Vue公式ルーティングライブラリ

### 11.3. テスト

品質保証のため、以下のテストフレームワークの導入を検討：

- **Vitest**: Vite対応の高速テストフレームワーク
- **Vue Test Utils**: Vueコンポーネントのテストユーティリティ

---

本仕様書で概説したフロントエンドアーキテクチャは、AI司書「LiVraria」がユーザーに直感的で応答性の高い対話体験を提供するための技術的な基盤である。この設計に基づき、モダンで保守性の高いフロントエンドシステムを構築できることを確信している。
