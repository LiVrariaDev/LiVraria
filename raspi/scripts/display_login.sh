#!/bin/bash

# 実行ディレクトリをスクリプトの場所に設定
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
# raspiディレクトリ（親ディレクトリ）に移動
cd "$SCRIPT_DIR/.."

# .envファイルを読み込む (PRIMARY_WIDTHなどを取得するため)
if [ -f .env ]; then
    source .env
else
    echo "Warning: .env file not found."
fi

# デフォルト値 (もし.envにない場合)
PRIMARY_WIDTH=${PRIMARY_WIDTH:-1920}

# 環境変数の設定 (サービスから実行される場合などに必要)
export DISPLAY=:0
# ユーザーに合わせて変更 (pi -> dryophytes)
export XAUTHORITY=/home/livraria/.Xauthority

echo "[$(date)] Display Login Script Started" >> /tmp/display_control.log
echo "User: $(whoami), Display: $DISPLAY, XAUTHORITY: $XAUTHORITY" >> /tmp/display_control.log
echo "Visible windows:" >> /tmp/display_control.log
wmctrl -l >> /tmp/display_control.log

# "Secondary Display" というタイトルのウィンドウを検索して移動・フルスクリーン化
# StartApp.sh のロジックを参考

MAX_WAIT=20 # 20秒待機（短めに設定、必要なら調整）
COUNTER=0

while [ $COUNTER -lt $MAX_WAIT ]; do
    SEC_ID=$(wmctrl -l | grep "Secondary Display" | awk '{print $1}')
    
    if [ -n "$SEC_ID" ]; then
        echo "Secondary display found: $SEC_ID" >> /tmp/display_control.log
        
        # 移動とフルスクリーン化
        # -e gravity,x,y,w,h
        wmctrl -i -r "$SEC_ID" -e 0,$PRIMARY_WIDTH,0,-1,-1
        wmctrl -i -r "$SEC_ID" -b add,fullscreen
        
        echo "Secondary display moved and fullscreened." >> /tmp/display_control.log
        exit 0
    fi
    
    sleep 0.5
    COUNTER=$((COUNTER + 1))
done

echo "Timeout: Secondary Display window not found." >> /tmp/display_control.log
exit 1
