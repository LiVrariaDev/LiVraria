/**
 * TTS (Text-to-Speech) サービス
 * Raspberry Piのnfc-api (/speak) とWeb Speech APIを自動切り替え
 */

class TextToSpeechService {
    constructor() {
        this.useRaspi = false;
        this.isInitialized = false;
        this.selectedVoice = null;
        this.raspiHost = 'localhost';
    }

    /**
     * Raspberry Piのヘルスチェック
     */
    async detectRaspiAndCheckHealth() {
        try {
            const response = await fetch(`http://${this.raspiHost}:8000/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(3000)  // 3秒タイムアウト
            });

            if (response.ok) {
                const data = await response.json();
                console.log('[TTS] Raspberry Pi health:', data);
                return data.status === 'ok';
            }
            return false;
        } catch (error) {
            console.log('[TTS] Raspberry Pi not available, using Web Speech API');
            return false;
        }
    }

    /**
     * 初期化
     */
    async initialize() {
        if (this.isInitialized) return;

        this.useRaspi = await this.detectRaspiAndCheckHealth();

        if (this.useRaspi) {
            console.log('[TTS] Using Raspberry Pi nfc-api');
        } else {
            console.log('[TTS] Using Web Speech API');
            this.setupWebSpeechAPI();
        }

        this.isInitialized = true;
    }

    /**
     * Web Speech APIのセットアップ
     */
    setupWebSpeechAPI() {
        if (!window.speechSynthesis) {
            console.error('[TTS] Web Speech API not supported');
            return;
        }

        // 音声リストをロード
        const loadVoices = () => {
            const voices = window.speechSynthesis.getVoices();
            if (voices.length > 0) {
                const jaVoices = voices.filter(voice => voice.lang.includes('ja'));
                if (jaVoices.length > 0) {
                    const priorityNames = ['Google 日本語', 'Microsoft Nanami', 'Kyoko', 'O-Ren', 'Microsoft Haruka'];
                    let bestVoice = null;
                    for (const name of priorityNames) {
                        bestVoice = jaVoices.find(v => v.name.includes(name));
                        if (bestVoice) break;
                    }
                    this.selectedVoice = bestVoice || jaVoices[0];
                    console.log('[TTS] Selected voice:', this.selectedVoice?.name);
                }
            }
        };

        loadVoices();
        window.speechSynthesis.onvoiceschanged = loadVoices;
    }

    /**
     * テキストを音声合成
     */
    async speak(text) {
        if (!text || !text.trim()) return;

        // HTMLタグと絵文字を除去
        const plainText = typeof text === 'string'
            ? text.replace(/<[^>]+>/g, '') // HTMLタグ除去
                .replace(/([\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF])/g, '') // 絵文字除去
            : '';

        if (!plainText.trim()) return;

        if (this.useRaspi) {
            await this.speakWithRaspi(plainText);
        } else {
            this.speakWithWebAPI(plainText);
        }
    }

    /**
     * Raspberry Pi nfc-apiで音声合成
     */
    async speakWithRaspi(text) {
        try {
            const response = await fetch(`http://${this.raspiHost}:8000/speak`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text })
            });

            if (!response.ok) throw new Error('Failed to speak');
            const result = await response.json();

            if (result.status === 'ok') {
                console.log('[TTS] Raspberry Pi speech started:', result.message);
            } else {
                console.error('[TTS] Raspberry Pi error:', result.message);
            }
        } catch (error) {
            console.error('[TTS] Raspberry Pi failed:', error);
            // フォールバック: Web Speech APIを使用
            console.log('[TTS] Falling back to Web Speech API');
            this.speakWithWebAPI(text);
        }
    }

    /**
     * Web Speech APIで音声合成
     */
    speakWithWebAPI(text) {
        if (!window.speechSynthesis) {
            console.error('[TTS] Web Speech API not supported');
            return;
        }

        // 現在再生中の音声をキャンセル
        window.speechSynthesis.cancel();

        if (!this.selectedVoice) this.setupWebSpeechAPI();

        const utterance = new SpeechSynthesisUtterance(text);
        if (this.selectedVoice) utterance.voice = this.selectedVoice;
        utterance.lang = 'ja-JP';
        utterance.rate = 1.0;

        utterance.onend = () => {
            console.log('[TTS] Web Speech API finished');
        };

        utterance.onerror = (event) => {
            console.error('[TTS] Web Speech API error:', event.error);
        };

        window.speechSynthesis.speak(utterance);
        console.log('[TTS] Web Speech API speaking:', text.substring(0, 50) + '...');
    }

    /**
     * 音声合成を停止
     */
    cancel() {
        if (!this.useRaspi && window.speechSynthesis) {
            window.speechSynthesis.cancel();
        }
    }

    /**
     * 現在使用中のエンジンを取得
     */
    getCurrentEngine() {
        return this.useRaspi ? 'Raspberry Pi (nfc-api)' : 'Web Speech API';
    }
}

export const textToSpeech = new TextToSpeechService();
