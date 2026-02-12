/**
 * NFC API Server (Mock/Raspi) と通信するためのユーティリティ
 */

// NFCサーバーのベースURL
// 環境変数から取得、デフォルトは http://localhost:8000
const NFC_SERVER_URL = import.meta.env.VITE_NFC_API_URL || 'http://localhost:5001';

/**
 * 音声合成（Raspberry Pi NFC APIサーバー）
 * @param {string} text - 合成するテキスト
 * @returns {Promise<Object>} - { status: 'ok', message: '...' }
 */
export const speak = async (text) => {
    const response = await fetch(`${NFC_SERVER_URL}/speak`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text })
    });

    if (!response.ok) throw new Error('Failed to speak');
    return response.json();
};

/**
 * NFCカードの読み取りを開始し、検出されたらコールバックを実行する
 * @param {Function} onSuccess - 成功時のコールバック (idm) => void
 * @param {Object} options - オプション { timeout: number }
 * @returns {Promise<void>}
 */
export const readNfcCard = async (onSuccess, options = {}) => {
    const timeout = options.timeout || 30;

    try {
        // 読み取り開始リクエスト
        const response = await fetch(`${NFC_SERVER_URL}/start-nfc`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timeout })
        });

        if (!response.ok) throw new Error('NFC読み取りの開始に失敗しました');

        // ポーリング開始
        await pollNfcStatus(onSuccess);

    } catch (error) {
        console.error('NFC読み取りエラー:', error);
        throw error;
    }
};

/**
 * NFC読み取り状態をポーリングする
 * @param {Function} onSuccess 
 * @returns {Promise<void>}
 */
const pollNfcStatus = (onSuccess) => {
    return new Promise((resolve, reject) => {
        const pollInterval = 500; // 0.5秒ごとに確認
        const maxRetries = 60; // 最大30秒 (0.5 * 60)
        let retries = 0;

        const checkStatus = async () => {
            try {
                const response = await fetch(`${NFC_SERVER_URL}/check-nfc`);
                if (!response.ok) {
                    console.warn("NFC status check failed, retrying...");
                } else {
                    const data = await response.json();

                    if (data.status === 'success' && data.idm) {
                        onSuccess(data.idm);
                        resolve();
                        return;
                    } else if (data.status === 'timeout') {
                        reject(new Error('NFC読み取りがタイムアウトしました'));
                        return;
                    }
                    // 'waiting' or 'idle' -> continue polling
                }

                retries++;
                if (retries >= maxRetries) {
                    reject(new Error('応答がありません（タイムアウト）'));
                    return;
                }

                setTimeout(checkStatus, pollInterval);

            } catch (error) {
                reject(error);
            }
        };

        setTimeout(checkStatus, pollInterval);
    });
};
