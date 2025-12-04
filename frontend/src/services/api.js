// src/services/api.js
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
        const params = new URLSearchParams(userData)
        const response = await fetch(`${API_BASE_URL}/users?${params}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${idToken}`
            }
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
     * メッセージ送信（新規セッションまたは既存セッション）
     * @param {string|null} sessionId - セッションID（初回はnull）
     * @param {string} message - メッセージ内容
     * @param {string} idToken - Firebase ID Token
     * @param {string} mode - チャットモード（"default" or "librarian"）
     */
    async sendMessage(sessionId, message, idToken, mode = 'default') {
        const url = sessionId
            ? `${API_BASE_URL}/sessions/${sessionId}/messages`
            : `${API_BASE_URL}/sessions/new/messages`

        const params = new URLSearchParams({ message, mode })

        const response = await fetch(`${url}?${params}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${idToken}`
            }
        })

        if (!response.ok) throw new Error('Failed to send message')
        return response.json()
    },

    /*
     * セッション情報取得
     * @param {string} sessionId - セッションID
     * @param {string} userId - ユーザーID
     * @param {string} idToken - Firebase ID Token
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
     * @param {string} sessionId - セッションID
     * @param {string} userId - ユーザーID
     * @param {string} idToken - Firebase ID Token
     */
    async closeSession(sessionId, userId, idToken) {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/close?user_id=${userId}`, {
            method: 'POST',
            headers: {
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
     * @param {string} nfcId - NFC ID
     * @param {string} userId - ユーザーID
     * @param {string} idToken - Firebase ID Token
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
     * @param {string} nfcId - NFC ID
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
     * @param {string} nfcId - NFC ID
     * @param {string} idToken - Firebase ID Token
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
    },

    /*
     * サーバーヘルスチェック
     */
    async healthCheck() {
        const response = await fetch(`${API_BASE_URL}/`)
        if (!response.ok) throw new Error('Server is not healthy')
        return response.json()
    }
}