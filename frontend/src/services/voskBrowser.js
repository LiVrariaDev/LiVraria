import { createModel } from 'vosk-browser';

/**
 * Vosk-browser (WebAssembly) 音声認識クラス
 * ブラウザ内で完結するオフライン音声認識
 */
export class VoskBrowserSTT {
    constructor(onResult, onPartial) {
        this.model = null;
        this.recognizer = null;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.onResult = onResult;
        this.onPartial = onPartial;
        this.isRecording = false;
        this.isInitialized = false;
    }

    /**
     * モデルの初期化
     */
    async initialize() {
        if (this.isInitialized) return;

        console.log('[VOSK-Browser] Initializing model...');

        try {
            // ローカルモデルをロード
            const MODEL_PATH = '/models/vosk-model-small-ja-0.22.zip';

            this.model = await createModel(MODEL_PATH);
            this.isInitialized = true;

            console.log('[VOSK-Browser] Model loaded successfully');
        } catch (error) {
            console.error('[VOSK-Browser] Failed to load model:', error);
            throw error;
        }
    }

    /**
     * 音声認識を開始
     */
    async start() {
        if (this.isRecording) {
            console.warn('[VOSK-Browser] Already recording');
            return;
        }

        if (!this.isInitialized) {
            await this.initialize();
        }

        console.log('[VOSK-Browser] Starting recognition...');

        try {
            // 音声キャプチャ
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            this.audioContext = new AudioContext({ sampleRate: 16000 });
            const source = this.audioContext.createMediaStreamSource(stream);

            // Recognizerを作成
            this.recognizer = new this.model.KaldiRecognizer(16000);
            this.recognizer.setWords(true);

            // イベントリスナーを設定
            this.recognizer.on("result", (message) => {
                if (message.result && message.result.text && this.onResult) {
                    console.log('[VOSK-Browser] Result:', message.result.text);
                    this.onResult(message.result.text);
                }
            });

            this.recognizer.on("partialresult", (message) => {
                if (message.result && message.result.partial && this.onPartial) {
                    // console.log('[VOSK-Browser] Partial:', message.result.partial);
                    this.onPartial(message.result.partial);
                }
            });

            // 音声処理
            const processor = this.audioContext.createScriptProcessor(4096, 1, 1);

            processor.onaudioprocess = (e) => {
                if (this.recognizer && this.isRecording) {
                    try {
                        // vosk-browserはAudioBufferを直接受け取れる
                        this.recognizer.acceptWaveform(e.inputBuffer);
                    } catch (error) {
                        console.error('[VOSK-Browser] acceptWaveform failed:', error);
                    }
                }
            };

            source.connect(processor);
            processor.connect(this.audioContext.destination);

            this.mediaRecorder = { stream, processor, source };
            this.isRecording = true;

            console.log('[VOSK-Browser] Recognition started');
        } catch (error) {
            console.error('[VOSK-Browser] Failed to start recognition:', error);
            this.stop();
            throw error;
        }
    }

    /**
     * 音声認識を停止
     */
    stop() {
        console.log('[VOSK-Browser] Stopping...');

        // リソース解放
        if (this.mediaRecorder) {
            try {
                this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
                this.mediaRecorder.processor.disconnect();
                this.mediaRecorder.source.disconnect();
                this.mediaRecorder = null;
                console.log('[VOSK-Browser] Audio capture stopped');
            } catch (error) {
                console.error('[VOSK-Browser] Error stopping audio capture:', error);
            }
        }

        if (this.audioContext) {
            try {
                this.audioContext.close();
                this.audioContext = null;
                console.log('[VOSK-Browser] AudioContext closed');
            } catch (error) {
                console.error('[VOSK-Browser] Error closing AudioContext:', error);
            }
        }

        if (this.recognizer) {
            try {
                // Recognizerの解放
                // イベントリスナーは自動的に解除されるため、明示的なremoveは不要
                // free()メソッドがない場合はnull代入のみでGCに任せる
                // this.recognizer.free(); 
                this.recognizer = null;
            } catch (error) {
                console.error('[VOSK-Browser] Error freeing recognizer:', error);
            }
        }

        this.isRecording = false;
        console.log('[VOSK-Browser] Stopped successfully');
    }
}
