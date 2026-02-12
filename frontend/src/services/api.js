const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export const api = {
    // ========================================
    // ユーザー関連API
    // ========================================

    /*
     * ユーザー作成
     */
    async createUser(userData, idToken) {
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

    /*
     * ユーザーログアウト
     */
    async logoutUser(userId, idToken) {
        const response = await fetch(`${API_BASE_URL}/users/${userId}/logout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            }
        })

        if (!response.ok) throw new Error('Failed to logout user')
        return response.json()
    },

    // ========================================
    // セッション・メッセージ関連API
    // ========================================

    /*
     * メッセージ送信
     */
    async sendMessage(sessionId, message, idToken, mode = 'default') {
        const url = sessionId
            ? `${API_BASE_URL}/sessions/${sessionId}/messages`
            : `${API_BASE_URL}/sessions/new/messages`

        // modeも念のためボディに含めます
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({ message, mode })
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
    async closeSession(sessionId, userId, idToken) {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/close`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({ user_id: userId })
        })

        if (!response.ok) throw new Error('Failed to close session')
        return response.json()
    },

    // ========================================
    // NFC認証関連API
    // ========================================

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

    // ========================================
    // 蔵書検索関連API
    // ========================================

    /*
     * 図書館検索
     */
    async searchLibraries(pref, limit = 5, idToken) {
        const params = new URLSearchParams({ pref, limit });
        const response = await fetch(`${API_BASE_URL}/search/libraries?${params}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                // ★追加: 認証トークンをヘッダーにセット
                'Authorization': `Bearer ${idToken}`
            }
        });

        if (!response.ok) {
            throw new Error('Library search failed');
        }
        return response.json();
    },

    /*
     * 貸出状況確認
     */
    async checkBookAvailability(isbn, systemid, idToken) {
        const params = new URLSearchParams({ isbn, systemid });
        const response = await fetch(`${API_BASE_URL}/search/books/availability?${params}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                // ★追加: 認証ヘッダー
                'Authorization': `Bearer ${idToken}`
            }
        });

        if (!response.ok) {
            throw new Error('Book availability check failed');
        }
        return response.json();
    },

    /*
     * 本検索
     */
    // semantic=true にするとAIがキーワードを考えてくれる
    async searchBooks(query, idToken, semantic = false) {
        // URLパラメータを生成（semanticもここに含める）
        const params = new URLSearchParams({
            q: query,
            semantic: semantic.toString()
        });

        const response = await fetch(`${API_BASE_URL}/books/search?${params.toString()}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            }
        })

        if (!response.ok) {
            throw new Error('Book search failed');
        }
        return response.json();
    },

    async getUserNfc(userId, idToken) {
        const response = await fetch(`${API_BASE_URL}/users/${userId}/nfc`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${idToken}`
            }
        })

        if (!response.ok) throw new Error('Failed to get user NFC')
        return response.json()
    },


}
