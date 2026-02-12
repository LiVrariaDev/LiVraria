#!/bin/bash

# Stop on error
set -e

# sudoでの実行を防ぐ
if [ "$EUID" -eq 0 ]; then
    echo "エラー: このスクリプトをsudoで実行しないでください"
    echo "スクリプト内で必要な箇所のみsudoを使用します"
    echo ""
    echo "正しい実行方法:"
    echo "  ./setup.sh"
    echo "  ./setup.sh --systemd"
    exit 1
fi

echo "=== Raspberry Pi API Server Setup ==="
echo "このスクリプトはRaspberry Pi上でAPI Server (NFC, TTS, VOSK)をセットアップします"
echo ""

echo "=== Update & library install ==="
sudo apt update
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
libffi-dev liblzma-dev git swig libpcsclite-dev pcscd pcsc-tools

echo "=== Install OpenJTalk for TTS ==="
sudo apt install -y open-jtalk open-jtalk-mecab-naist-jdic \
hts-voice-nitech-jp-atr503-m001 alsa-utils
echo "OpenJTalkのインストールが完了しました"

echo "=== Start pcscd service ==="
sudo systemctl start pcscd
sudo systemctl enable pcscd
echo "pcscdサービスを起動しました"

echo "=== Install Pyenv ==="
if [ ! -d "$HOME/.pyenv" ]; then
    echo "pyenvをインストールします..."
    curl https://pyenv.run | bash

    if ! grep -q 'export PYENV_ROOT="$HOME/.pyenv"' ~/.bashrc; then
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
        echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
        echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
        echo "~/.bashrcにpyenv設定を追加しました"
    fi
else
    echo "pyenvは既にインストールされています"
fi

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

echo "=== Install Python3.11 ==="
pyenv install 3.11.13 --skip-existing
pyenv local 3.11.13
echo "$(python --version) を使用します"

echo "=== Virtual environment ==="
if [ ! -d ".venv" ]; then
    python -m venv .venv
    echo "仮想環境を作成しました"
else
    echo "仮想環境は既に存在します"
fi

source .venv/bin/activate
pip install -r requirements.txt
echo "依存関係のインストールが完了しました"

echo "=== VOSK日本語モデルのセットアップ ==="
VOSK_MODEL_DIR="/opt/vosk-model-ja"
VOSK_MODEL_ZIP="vosk-model-small-ja-0.22.zip"
VOSK_MODEL_URL="https://alphacephei.com/vosk/models/${VOSK_MODEL_ZIP}"

if [ -d "$VOSK_MODEL_DIR" ]; then
    echo "VOSKモデルは既にインストールされています: $VOSK_MODEL_DIR"
else
    echo "VOSKモデルをダウンロードしています..."
    
    # 一時ディレクトリにダウンロード
    cd /tmp
    wget -q --show-progress "$VOSK_MODEL_URL"
    
    if [ $? -eq 0 ]; then
        echo "VOSKモデルを展開しています..."
        unzip -q "$VOSK_MODEL_ZIP"
        
        # 展開されたディレクトリ名を取得
        EXTRACTED_DIR=$(unzip -l "$VOSK_MODEL_ZIP" | grep -m1 "/$" | awk '{print $4}' | sed 's/\/$//')
        
        # /optに移動（sudo必要）
        echo "VOSKモデルを /opt に配置しています..."
        sudo mv "$EXTRACTED_DIR" "$VOSK_MODEL_DIR"
        
        # クリーンアップ
        rm "$VOSK_MODEL_ZIP"
        
        echo "✅ VOSKモデルのインストールが完了しました: $VOSK_MODEL_DIR"
    else
        echo "⚠️  VOSKモデルのダウンロードに失敗しました"
        echo "手動でインストールしてください:"
        echo "  wget $VOSK_MODEL_URL"
        echo "  unzip $VOSK_MODEL_ZIP"
        echo "  sudo mv vosk-model-small-ja-0.22 $VOSK_MODEL_DIR"
    fi
    
    # 元のディレクトリに戻る
    cd - > /dev/null
fi


echo "=== Systemd service ==="
if [ "$1" == "--systemd" ]; then
    echo "systemdサービスをセットアップします..."
    sudo cp raspi-api.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable raspi-api.service
    sudo systemctl start raspi-api.service
    echo "systemdサービスを起動しました"
    echo ""
    echo "サービスの状態を確認:"
    sudo systemctl status raspi-api.service --no-pager
else
    echo "systemdサービスのセットアップをスキップしました"
    echo "自動起動を有効にする場合は --systemd オプションを付けて実行してください"
fi

echo ""
echo "=== Setup Finished ==="
echo ""
echo "次のステップ:"
echo "1. NFCカードリーダーがUSB接続されていることを確認"
echo "2. カードリーダーの確認: pcsc_scan"
echo "3. APIサーバーの手動起動テスト: python raspi_api_server.py"
echo "4. ヘルスチェック: curl http://localhost:8000/health"
echo ""
if [ "$1" != "--systemd" ]; then
    echo "自動起動を有効にする場合:"
    echo "  ./setup.sh --systemd"
    echo ""
fi



