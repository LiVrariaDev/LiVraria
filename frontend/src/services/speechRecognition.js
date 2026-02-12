import { VoskBrowserSTT } from './voskBrowser';

class SpeechRecognitionService {
    constructor() {
        this.useVoskBrowser = false;
        this.voskBrowserSTT = null;
        this.webSpeechAPI = null;
        this.isInitialized = false;
    }

    /**
     * 初期化
     */
    async initialize(onResult, onPartial) {
        // コールバックは常に更新（HMRや再マウント対応）
        if (this.voskBrowserSTT) {
            this.voskBrowserSTT.onResult = onResult;
            this.voskBrowserSTT.onPartial = onPartial;
        }

        if (this.isInitialized) return;

        // エンジン選択ロジック
        // 1. APIサーバー(Raspi)が稼働しているか確認
        // 2. 稼働している場合 -> Web Speech APIが使えない可能性が高い(Raspi Chromium)ため、Vosk-browserを優先
        // 3. 稼働していない場合 -> PC環境とみなし、Web Speech APIを優先

        const isApiAvailable = await this.checkApiHealth();
        const isWebSpeechSupported = ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window);

        console.log(`[STT] API Server: ${isApiAvailable ? 'Available' : 'Unavailable'}`);
        console.log(`[STT] Web Speech API: ${isWebSpeechSupported ? 'Supported' : 'Not Supported'}`);

        if (isApiAvailable) {
            console.log('[STT] Raspberry Pi environment detected (API Available). Using Vosk-browser.');
            this.useVoskBrowser = true;
        } else if (isWebSpeechSupported) {
            console.log('[STT] PC environment detected. Using Web Speech API.');
            this.useVoskBrowser = false;
        } else {
            console.warn('[STT] Web Speech API not supported. Fallback to Vosk-browser.');
            this.useVoskBrowser = true;
        }

        // Vosk-browserを使用する場合の初期化
        if (this.useVoskBrowser) {
            console.log('[STT] Initializing Vosk-browser (WebAssembly)...');
            this.voskBrowserSTT = new VoskBrowserSTT(onResult, onPartial);

            try {
                await this.voskBrowserSTT.initialize();
                console.log('[STT] Vosk-browser initialized successfully');
            } catch (error) {
                console.error('[STT] Vosk-browser initialization failed:', error);

                // Vosk初期化失敗時のフォールバック
                if (isWebSpeechSupported) {
                    console.log('[STT] Falling back to Web Speech API');
                    this.useVoskBrowser = false;
                    this.setupWebSpeechAPI(onResult, onPartial);
                }
            }
        }

        // Web Speech APIを使用する場合
        if (!this.useVoskBrowser) {
            this.setupWebSpeechAPI(onResult, onPartial);
        }

        this.isInitialized = true;
    }

    /**
     * APIサーバーの稼働確認
     */
    async checkApiHealth() {
        try {
            // タイムアウトを短めに設定
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1000);

            const response = await fetch('http://localhost:8000/health', {
                method: 'GET',
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return response.ok;
        } catch (error) {
            return false;
        }
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
