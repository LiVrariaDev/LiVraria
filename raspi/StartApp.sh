#!/bin/bash

# ==========================================
# Livraria 起動スクリプト (Dual Display Kiosk)
# ==========================================

# log file (1回ごと上書き, シンボリックリンク元で)
LOG_FILE="$(dirname "$0")/livraria_start.log"
exec > >(tee "$LOG_FILE") 2>&1

# ファイル実体へ移動
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# .envファイルを読み込む
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found."
    exit 1
fi

echo "Starting Livraria..."

# マウスカーソルを消す (unclutterがインストールされていれば)
# unclutter -idle 0.1 -root &

# 1. メイン画面 (操作用) のみを起動
# ログイン後、JavaScriptでSecondaryディスプレイが自動的に開かれる
chromium \
  --app="$SERVER_URL" \
  --window-position=0,0 \
  --force-device-scale-factor=0.8 \
  --autoplay-policy=no-user-gesture-required \
  --ozone-platform=x11 \
  --user-data-dir="/tmp/chrome_main_profile" \
  --touch-events=enabled \
  --disable-touch-drag-drop \
  --unsafely-treat-insecure-origin-as-secure="$SERVER_URL" \
  --overscroll-history-navigation=0 &

echo "Main display launched. Waiting for login and secondary window..."

# 2. Mainもフルスクリーン化
sleep 5
MAIN_ID=$(wmctrl -l | grep "LiVraria Main" | awk '{print $1}')
if [ -n "$MAIN_ID" ]; then
    wmctrl -i -r "$MAIN_ID" -e 0,0,0,-1,-1
    wmctrl -i -r "$MAIN_ID" -b add,fullscreen
    echo "Main display set to fullscreen."
else
    echo "Warning: Main display window not found."
fi

# 3. Secondaryウィンドウが開くまで待機（busy wait）
MAX_WAIT=300  # 最大5分待機
COUNTER=0

while [ $COUNTER -lt $MAX_WAIT ]; do
    # "Secondary Display" というタイトルのウィンドウを検索
    SEC_ID=$(wmctrl -l | grep "Secondary Display" | awk '{print $1}')
    
    if [ -n "$SEC_ID" ]; then
        echo "Secondary display detected: $SEC_ID"
        
        # 4. Secondaryを右ディスプレイに移動してフルスクリーン化
        sleep 0.5  # ウィンドウが完全に表示されるまで少し待つ
        wmctrl -i -r "$SEC_ID" -e 0,$PRIMARY_WIDTH,0,-1,-1
        wmctrl -i -r "$SEC_ID" -b add,fullscreen
        
        echo "Secondary display moved to right screen and set to fullscreen."
        break
    fi
    
    sleep 1
    COUNTER=$((COUNTER + 1))
done

if [ $COUNTER -eq $MAX_WAIT ]; then
    echo "Warning: Secondary display not detected within timeout."
fi

echo "Livraria system is running."