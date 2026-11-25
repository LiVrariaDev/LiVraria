const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/**
 * /debug/* を管理者キー付きで呼ぶ。401/403/503 は detail 付きの Error にする。
 */
async function request(path, adminKey) {
    const response = await fetch(`${API_BASE_URL}/debug${path}`, {
        headers: { 'X-Admin-Key': adminKey || '' }
    })
    if (!response.ok) {
        let detail = ''
        try {
            detail = (await response.json()).detail || ''
        } catch {
            // JSON でないレスポンスは無視
        }
        const error = new Error(`${response.status}${detail ? `: ${detail}` : ''}`)
        error.status = response.status
        throw error
    }
    return response.json()
}

export const debugApi = {
    getGraph: (adminKey) => request('/graph', adminKey),
    getUsage: (adminKey) => request('/usage', adminKey),
    getSessions: (adminKey) => request('/sessions', adminKey),
    getTurns: (adminKey, sessionId) => request(`/sessions/${encodeURIComponent(sessionId)}/turns`, adminKey),
    getTurn: (adminKey, traceId) => request(`/turns/${encodeURIComponent(traceId)}`, adminKey),
}
