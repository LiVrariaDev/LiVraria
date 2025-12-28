# 本番環境デプロイガイド

このガイドでは、LiVrariaをVPSに本番環境としてデプロイする手順を説明します。

> [!IMPORTANT]
> このドキュメントはAIによって生成されています
> そのため、誤字脱字や不正確な情報が含まれている可能性があります

## デプロイ方法の選択

### 方法1: Docker Compose（推奨）

Dockerを使用した最も簡単なデプロイ方法です。

### 方法2: 手動デプロイ + Nginx

より細かい制御が必要な場合の手動デプロイ方法です。

---

## 方法1: Docker Composeでデプロイ

### 前提条件

- Docker & Docker Compose がインストールされたVPS
- ドメイン名（オプション）
- SSL証明書

### 1. リポジトリをクローン

```bash
# VPS上で
cd /var/www
git clone https://github.com/LiVrariaDev/LiVraria.git
cd LiVraria
```

### 2. 環境変数を設定

```bash
# .envファイルを作成
cp .env.template .env
nano .env
```

**必須設定:**
```bash
# Firebase
FIREBASE_ACCOUNT_KEY_PATH=path/to/serviceAccountKey.json
FIREBASE_API_KEY=your_firebase_api_key

# Gemini API
GEMINI_API_KEY1=your_gemini_api_key

# Rakuten Books API
RAKUTEN_APP_ID=your_rakuten_app_id

# 本番環境CORS
PRODUCTION_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

### 3. Dockerでビルド・起動

```bash
# ビルド
docker compose build

# 起動
docker compose up -d

# ログ確認
docker compose logs -f
```

### 4. Nginxリバースプロキシ設定（オプション）

Dockerコンテナの前にNginxを配置してHTTPS化します。

```bash
sudo nano /etc/nginx/sites-available/livraria
```

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # フロントエンド
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # バックエンドAPI
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTPからHTTPSへリダイレクト
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/livraria /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. SSL証明書の取得

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

---

## 方法2: 手動デプロイ + Nginx

### 1. 依存関係のインストール

```bash
# Node.js & pnpm
curl -fsSL https://get.pnpm.io/install.sh | sh -

# Python
sudo apt install python3 python3-venv python3-pip

# Nginx
sudo apt install nginx
```

### 2. リポジトリをクローン

```bash
cd /var/www
git clone https://github.com/LiVrariaDev/LiVraria.git
cd LiVraria
```

### 3. フロントエンドのビルド

```bash
cd frontend
pnpm install
pnpm run build
# dist/ ディレクトリが生成される
```

### 4. バックエンドのセットアップ

```bash
cd ../backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. 環境変数を設定

```bash
# プロジェクトルートで
cp .env.template .env
nano .env
```

**本番環境用設定:**
```bash
# フロントエンド
VITE_API_BASE_URL=https://your-domain.com/api

# バックエンド
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
PRODUCTION_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Firebase
FIREBASE_ACCOUNT_KEY_PATH=/var/www/LiVraria/serviceAccountKey.json
FIREBASE_API_KEY=your_firebase_api_key

# Gemini API
GEMINI_API_KEY1=your_gemini_api_key

# Rakuten Books API
RAKUTEN_APP_ID=your_rakuten_app_id
```

### 6. systemdサービスの設定

```bash
sudo nano /etc/systemd/system/livraria-backend.service
```

```ini
[Unit]
Description=LiVraria Backend API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/LiVraria
Environment="PATH=/var/www/LiVraria/backend/.venv/bin"
ExecStart=/var/www/LiVraria/backend/.venv/bin/python -m backend.run
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable livraria-backend
sudo systemctl start livraria-backend
sudo systemctl status livraria-backend
```

### 7. Nginxの設定

```bash
sudo nano /etc/nginx/sites-available/livraria
```

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # フロントエンド（Viteビルド済み）
    location / {
        root /var/www/LiVraria/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
    
    # バックエンドAPI
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTPからHTTPSへリダイレクト
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/livraria /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 8. SSL証明書の取得

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

---

## GitHub Actions自動デプロイ

### 1. GitHub Secretsを設定

リポジトリの Settings → Secrets and variables → Actions で以下を設定：

- `HOST`: VPSのIPアドレスまたはドメイン
- `USERNAME`: SSHユーザー名
- `PRIVATE_KEY`: SSH秘密鍵（`~/.ssh/id_rsa`の内容）

### 2. CDワークフローを有効化

```bash
# ローカルで
mv .github/workflows/cd.yaml.disabled .github/workflows/cd.yaml
git add .github/workflows/cd.yaml
git commit -m "feat: enable CD"
git push
```

### 3. 自動デプロイ

mainブランチにpushすると自動的にVPSにデプロイされます。

---

## 動作確認

```bash
# バックエンドAPI
curl https://your-domain.com/api/health

# フロントエンド
curl https://your-domain.com
```

ブラウザで `https://your-domain.com` にアクセスして動作確認してください。

---

## トラブルシューティング

### バックエンドが起動しない

```bash
# ログ確認
sudo journalctl -u livraria-backend -f

# 手動起動でエラー確認
cd /var/www/LiVraria
source backend/.venv/bin/activate
python -m backend.run
```

### Nginxエラー

```bash
# 設定ファイルのテスト
sudo nginx -t

# エラーログ確認
sudo tail -f /var/log/nginx/error.log
```

### Dockerコンテナが起動しない

```bash
# ログ確認
docker compose logs backend
docker compose logs frontend

# コンテナ再起動
docker compose restart
```

### CORS エラー

`.env`の`PRODUCTION_ORIGINS`が正しく設定されているか確認してください。

```bash
PRODUCTION_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

---

## セキュリティ推奨事項

1. **ファイアウォール設定**
   ```bash
   sudo ufw allow 22/tcp   # SSH
   sudo ufw allow 80/tcp   # HTTP
   sudo ufw allow 443/tcp  # HTTPS
   sudo ufw enable
   ```

2. **定期的なアップデート**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **SSL証明書の自動更新**
   ```bash
   # Let's Encryptは自動更新されますが、確認
   sudo certbot renew --dry-run
   ```

4. **`.env`ファイルの権限**
   ```bash
   chmod 600 .env
   ```

---

## 更新手順

### Docker Composeの場合

```bash
cd /var/www/LiVraria
git pull
docker compose down
docker compose build
docker compose up -d
```

### 手動デプロイの場合

```bash
cd /var/www/LiVraria
git pull

# フロントエンド
cd frontend
pnpm install
pnpm run build

# バックエンド
sudo systemctl restart livraria-backend
```
