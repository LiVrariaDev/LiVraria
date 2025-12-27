#!/bin/sh
# chromiumで日本語入力ができない問題
# Waylandを無効化することで解決する

nohup chromium --ozone-platform=x11 >/dev/null 2>&1 &

# default-flagに追記する
sudo sh -c 'echo "export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --ozone-platform=x11"' >> /etc/chromium.d/default-flags'
