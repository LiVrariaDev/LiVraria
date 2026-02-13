#!/bin/bash

# 環境変数の設定
export DISPLAY=:0
export XAUTHORITY=/home/livraria/.Xauthority

echo "[$(date)] Display Logout Script Started" >> /tmp/display_control.log
echo "User: $(whoami), Display: $DISPLAY" >> /tmp/display_control.log
wmctrl -l >> /tmp/display_control.log

MAX_WAIT=20 # 20秒待機
COUNTER=0

while [ $COUNTER -lt $MAX_WAIT ]; do
    # 1. "Secondary Display" というタイトルのウィンドウIDを取得
    # Chromeの場合、複数のIDが返ることがあるので head -n 1 で絞る
    WID=$(xdotool search --name "Secondary Display" | head -n 1)

    if [ -z "$WID" ]; then
        echo "Secondary Display is closed (Window not found)." >> /tmp/display_control.log
        exit 0
    fi

    echo "Target window found: $WID. Sending close signal... ($COUNTER)" >> /tmp/display_control.log
    
    # ウィンドウを最前面に持ってくる
    xdotool windowactivate --sync "$WID"
    # Alt+F4 (ウィンドウを閉じる) を送信
    xdotool key --window "$WID" Alt+F4
    
    sleep 0.5
    COUNTER=$((COUNTER + 1))
done

echo "Timeout: Failed to close Secondary Display." >> /tmp/display_control.log
wmctrl -l >> /tmp/display_control.log
exit 1
