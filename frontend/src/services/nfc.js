/**
 * NFC API Server (Mock/Raspi) と通信するためのユーティリティ
 */

// NFCサーバーのベースURL (ローカル開発用)
// 本番環境（Raspi上）では 'http://localhost:8000' かもしれないが、
// Viteプロキシ経由ではない（Raspi上の別プロセス）ため、ここでは直接指定するか、設定可能にする必要がある
// 一旦ハードコード（モック用に合わせて）
const NFC_SERVER_URL = 'http://localhost:8000';

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
