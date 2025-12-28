# 本番環境デプロイガイド

## 環境変数の設定

### 開発環境 (.env)
```bash
# フロントエンド
VITE_API_BASE_URL=http://localhost:8000

# バックエンド
# PRODUCTION_ORIGINS は設定不要（開発環境のみ）
```

### 本番環境 (.env)
```bash
# フロントエンド
VITE_API_BASE_URL=https://your-domain.com/api

# バックエンド
PRODUCTION_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

## CORS設定の仕組み

バックエンドのCORS設定は以下のように動作します：

**デフォルト（常に許可）:**
- `http://localhost:5173`
- `http://localhost:3000`
- `http://127.0.0.1:5173`
- `http://127.0.0.1:3000`
- `http://172.x.x.x:*` (プライベートIP)

**本番環境（環境変数から追加）:**
- `PRODUCTION_ORIGINS` に設定したドメイン

これにより、開発環境では`.env`に何も書かなくても動作し、本番環境では`PRODUCTION_ORIGINS`を追加するだけで対応できます。

## Nginx設定例

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # API（バックエンド）
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # フロントエンド（Viteビルド済み）
    location / {
        root /var/www/livraria/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}

# HTTPからHTTPSへリダイレクト
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

## デプロイ手順

### 1. フロントエンドのビルド
```bash
cd frontend
npm run build
# dist/ ディレクトリが生成される
```

### 2. ファイルをVPSに転送
```bash
# フロントエンド
scp -r frontend/dist/* user@vps:/var/www/livraria/frontend/dist/

# バックエンド
scp -r backend/ user@vps:/var/www/livraria/backend/
scp .env user@vps:/var/www/livraria/backend/
```

### 3. バックエンドのセットアップ
```bash
# VPS上で
cd /var/www/livraria/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. systemdサービスの設定
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
WorkingDirectory=/var/www/livraria/backend
Environment="PATH=/var/www/livraria/backend/.venv/bin"
ExecStart=/var/www/livraria/backend/.venv/bin/uvicorn backend.api.server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable livraria-backend
sudo systemctl start livraria-backend
```

### 5. Nginxの設定
```bash
sudo nano /etc/nginx/sites-available/livraria
sudo ln -s /etc/nginx/sites-available/livraria /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. SSL証明書の取得（Let's Encrypt）
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## 確認

```bash
# バックエンドAPI
curl https://your-domain.com/api/health

# フロントエンド
curl https://your-domain.com
```
