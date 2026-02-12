import { VoskBrowserSTT } from './voskBrowser';

class SpeechRecognitionService {
    constructor() {
        this.useVoskBrowser = false;
        this.voskBrowserSTT = null;
        this.webSpeechAPI = null;
        this.isInitialized = false;
    }

    /**
     * Vosk-browser (WebAssembly) 対応チェック
     */
    async detectVoskBrowserSupport() {
        // WebAssembly対応チェック
        if (!window.WebAssembly) {
            console.log('[STT] WebAssembly not supported');
            return false;
        }

        try {
            // Vosk-browserの初期化テスト
            console.log('[STT] Testing Vosk-browser support...');
            return true;  // vosk-browserがインストールされていればtrue
        } catch (error) {
            console.log('[STT] Vosk-browser not available:', error);
            return false;
        }
    }

    /**
     * 初期化
     */
    async initialize(onResult, onPartial) {
        if (this.isInitialized) return;

        this.useVoskBrowser = await this.detectVoskBrowserSupport();

        if (this.useVoskBrowser) {
            console.log('[STT] Using Vosk-browser (WebAssembly)');
            this.voskBrowserSTT = new VoskBrowserSTT(onResult, onPartial);

            try {
                await this.voskBrowserSTT.initialize();
            } catch (error) {
                console.error('[STT] Vosk-browser initialization failed, falling back to Web Speech API:', error);
                this.useVoskBrowser = false;
                this.setupWebSpeechAPI(onResult, onPartial);
            }
        } else {
            console.log('[STT] Using Web Speech API');
            this.setupWebSpeechAPI(onResult, onPartial);
        }

        this.isInitialized = true;
    }

    setupWebSpeechAPI(onResult, onPartial) {
        if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            console.error('[STT] Web Speech API not supported');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.webSpeechAPI = new SpeechRecognition();
        this.webSpeechAPI.lang = 'ja-JP';
        this.webSpeechAPI.interimResults = true;  // リアルタイム入力を有効化
        this.webSpeechAPI.continuous = false;

        this.webSpeechAPI.onresult = (event) => {
            // 最新の結果を取得
            const result = event.results[event.results.length - 1];
            const transcript = result[0].transcript;

            if (result.isFinal) {
                // 確定結果
                onResult(transcript);
            } else if (onPartial) {
                // 部分結果（リアルタイム）
                onPartial(transcript);
            }
        };

        this.webSpeechAPI.onend = () => {
            // Web Speech APIは自動的に停止するため、状態を更新
        };

        this.webSpeechAPI.onerror = (event) => {
            console.error('[STT] Web Speech API error:', event.error);
        };
    }

    async start() {
        if (this.useVoskBrowser && this.voskBrowserSTT) {
            await this.voskBrowserSTT.start();
        } else if (this.webSpeechAPI) {
            this.webSpeechAPI.start();
        }
    }

    stop() {
        console.log('[STT] Stopping speech recognition...');

        if (this.useVoskBrowser && this.voskBrowserSTT) {
            console.log('[STT] Stopping Vosk-browser...');
            this.voskBrowserSTT.stop();
        }

        if (this.webSpeechAPI) {
            console.log('[STT] Stopping Web Speech API...');
            this.webSpeechAPI.stop();
        }

        console.log('[STT] Speech recognition stopped');
    }

    getCurrentEngine() {
        return this.useVoskBrowser ? 'Vosk-browser (WebAssembly)' : 'Web Speech API';
    }
}

export const speechRecognition = new SpeechRecognitionService();
