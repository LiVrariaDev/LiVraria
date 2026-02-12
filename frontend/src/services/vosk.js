export class VoskSTT {
    constructor(raspiHost, onResult, onPartial) {
        this.raspiHost = raspiHost;
        this.ws = null;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.onResult = onResult;
        this.onPartial = onPartial;
        this.isRecording = false;
    }

    async start() {
        if (this.isRecording) return;

        // Raspberry PiのWebSocketに接続
        const wsUrl = `ws://${this.raspiHost}:8000/stt/stream`;
        console.log(`[VOSK] Connecting to ${wsUrl}`);

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = async () => {
            console.log('[VOSK] WebSocket connected');
            await this.startAudioCapture();
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.error) {
                console.error('[VOSK] Error:', data.error);
                this.stop();
                return;
            }

            if (data.type === 'final' && data.text) {
                this.onResult(data.text);
            } else if (data.type === 'partial' && data.text) {
                this.onPartial && this.onPartial(data.text);
            }
        };

        this.ws.onerror = (error) => {
            console.error('[VOSK] WebSocket error:', error);
            this.stop();
        };

        this.ws.onclose = () => {
            console.log('[VOSK] WebSocket closed');
            this.stop();
        };
    }

    async startAudioCapture() {
        try {
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
            const processor = this.audioContext.createScriptProcessor(4096, 1, 1);

            processor.onaudioprocess = (e) => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0);
                    const pcmData = this.float32ToPCM16(inputData);
                    this.ws.send(pcmData);
                }
            };

            source.connect(processor);
            processor.connect(this.audioContext.destination);

            this.mediaRecorder = { stream, processor, source };
            this.isRecording = true;

        } catch (error) {
            console.error('[VOSK] Failed to capture audio:', error);
            this.stop();
        }
    }

    float32ToPCM16(float32Array) {
        const pcm16 = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const s = Math.max(-1, Math.min(1, float32Array[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return pcm16.buffer;
    }

    stop() {
        if (this.mediaRecorder) {
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            this.mediaRecorder.processor.disconnect();
            this.mediaRecorder.source.disconnect();
        }

        if (this.audioContext) {
            this.audioContext.close();
        }

        if (this.ws) {
            this.ws.close();
        }

        this.isRecording = false;
    }
}
