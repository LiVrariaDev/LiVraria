const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = {
    // ========================================
    // ユーザー関連API
    // ========================================

    /*
     * ユーザー作成
     * @param {Object} userData - { name, gender, age, live_pref, live_city }
     * @param {string} idToken - Firebase ID Token
     */
    async createUser(userData, idToken) {
        // 修正：URLパラメータではなく、JSONボディとして送信する
        const response = await fetch(`${API_BASE_URL}/users`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify(userData)
        })

        if (!response.ok) throw new Error('Failed to create user')
        return response.json()
    },

    /*
     * ユーザー情報取得
     * @param {string} userId - ユーザーID
     * @param {string} idToken - Firebase ID Token
     */
    async getUser(userId, idToken) {
        const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${idToken}`
            }
        })

        if (!response.ok) throw new Error('Failed to get user')
        return response.json()
    },

    /*
     * ユーザー情報更新
     * @param {string} userId - ユーザーID
     * @param {Object} updates - 更新するフィールド
     * @param {string} idToken - Firebase ID Token
     */
    async updateUser(userId, updates, idToken) {
        const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify(updates)
        })

        if (!response.ok) throw new Error('Failed to update user')
        return response.json()
    },

    // ========================================
    // セッション・メッセージ関連API
    // ========================================

    /*
     * メッセージ送信
     * @param {string|null} sessionId - セッションID
     * @param {string} message - メッセージ内容
     * @param {string} idToken - Firebase ID Token
     * @param {string} mode - チャットモード
     */
    async sendMessage(sessionId, message, idToken, mode = 'default') {
        // 新規セッションの場合はsession_id="new"を使用
        const effectiveSessionId = sessionId || 'new'
        const url = `${API_BASE_URL}/sessions/${effectiveSessionId}/messages?mode=${mode}`

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({ message })
        })

        if (!response.ok) throw new Error('Failed to send message')
        return response.json()
    },

    /*
     * セッション情報取得
     */
    async getSession(sessionId, userId, idToken) {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}?user_id=${userId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${idToken}`
            }
        })

        if (!response.ok) throw new Error('Failed to get session')
        return response.json()
    },

    /*
     * セッションクローズ
     */
    async closeSession(sessionId, idToken) {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/close`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            }
        })

        if (!response.ok) throw new Error('Failed to close session')
        return response.json()
    },

    // ========================================
    // NFC認証関連API
    // ========================================

    /*
     * NFC登録
     */
    async registerNfc(nfcId, userId, idToken) {
        const response = await fetch(`${API_BASE_URL}/nfc/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({ nfc_id: nfcId, user_id: userId })
        })

        if (!response.ok) throw new Error('Failed to register NFC')
        return response.json()
    },

    /*
     * NFC認証
     */
    async authenticateNfc(nfcId) {
        const response = await fetch(`${API_BASE_URL}/nfc/auth`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nfc_id: nfcId })
        })

        if (!response.ok) throw new Error('Failed to authenticate NFC')
        return response.json()
    },

    /*
     * NFC登録解除
     */
    async unregisterNfc(nfcId, idToken) {
        const response = await fetch(`${API_BASE_URL}/nfc/unregister`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({ nfc_id: nfcId })
        })

        if (!response.ok) throw new Error('Failed to unregister NFC')
        return response.json()
    }
}

// NFC読み取りトリガー（ボタン押下時に呼ぶ）
api.startNfc = async function(timeout = 20) {
    const response = await fetch(`${API_BASE_URL}/start-nfc`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timeout })
    })

    if (!response.ok) {
        const text = await response.text()
        throw new Error(`start-nfc failed: ${text}`)
    }
    return response.json()
}

export default api