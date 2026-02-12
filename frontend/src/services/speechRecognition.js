import { VoskSTT } from './vosk';

class SpeechRecognitionService {
    constructor() {
        this.useVosk = false;
        this.voskSTT = null;
        this.webSpeechAPI = null;
        this.isInitialized = false;
        this.raspiHost = null;  // Raspberry PiのIPアドレス
    }

    /**
     * Raspberry Piのヘルスチェック
     * nfc-apiはRaspberry Pi内で動作するため、localhostで固定
     */
    async detectRaspiAndCheckHealth() {
        // Raspberry Pi内で動作するため、localhostを使用
        this.raspiHost = 'localhost';

        try {
            const response = await fetch(`http://${this.raspiHost}:8000/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(3000)  // 3秒タイムアウト
            });

            if (response.ok) {
                const data = await response.json();
                console.log('[STT] Raspberry Pi health:', data);
                return data.vosk_available === true;
            }
            return false;
        } catch (error) {
            console.log('[STT] Raspberry Pi not available, using Web Speech API');
            return false;
        }
    }

    /**
     * 初期化
     */
    async initialize(onResult, onPartial) {
        if (this.isInitialized) return;

        this.useVosk = await this.detectRaspiAndCheckHealth();

        if (this.useVosk) {
            console.log('[STT] Using VOSK on Raspberry Pi');
            this.voskSTT = new VoskSTT(this.raspiHost, onResult, onPartial);
        } else {
            console.log('[STT] Using Web Speech API');
            this.setupWebSpeechAPI(onResult);
        }

        this.isInitialized = true;
    }

    setupWebSpeechAPI(onResult) {
        if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            console.error('[STT] Web Speech API not supported');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.webSpeechAPI = new SpeechRecognition();
        this.webSpeechAPI.lang = 'ja-JP';
        this.webSpeechAPI.interimResults = false;
        this.webSpeechAPI.continuous = false;

        this.webSpeechAPI.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            onResult(transcript);
        };

        this.webSpeechAPI.onend = () => {
            // Web Speech APIは自動的に停止するため、状態を更新
        };

        this.webSpeechAPI.onerror = (event) => {
            console.error('[STT] Web Speech API error:', event.error);
        };
    }

    async start() {
        if (this.useVosk && this.voskSTT) {
            await this.voskSTT.start();
        } else if (this.webSpeechAPI) {
            this.webSpeechAPI.start();
        }
    }

    stop() {
        if (this.useVosk && this.voskSTT) {
            this.voskSTT.stop();
        } else if (this.webSpeechAPI) {
            this.webSpeechAPI.stop();
        }
    }

    getCurrentEngine() {
        return this.useVosk ? 'VOSK (Raspberry Pi)' : 'Web Speech API';
    }
}

export const speechRecognition = new SpeechRecognitionService();
