// メイン画面とセカンダリディスプレイ間の BroadcastChannel ラッパー。
// BroadcastChannel は送信元自身には届かないため、同じタブで送受信を混ぜないこと。

export const CHANNEL_NAME = 'livraria_channel';
export const EMOTIONS = ['neutral', 'happy', 'thinking', 'sorry'];

// 送信側(メイン画面)
export function createDisplaySender() {
  const channel = new BroadcastChannel(CHANNEL_NAME);
  let loggedIn = false;
  let lastSpeak = null;
  let syncHandler = null;

  const send = (message) => channel.postMessage(message);

  const syncState = (state) => {
    send({
      type: 'sync_state',
      loggedIn: !!state?.loggedIn,
      lastSpeak: state?.lastSpeak ?? null,
    });
  };

  channel.onmessage = (event) => {
    if (event.data?.type !== 'sync_request') return;
    if (syncHandler) {
      syncHandler();
    } else {
      syncState({ loggedIn, lastSpeak });
    }
  };

  return {
    sessionLoggedIn() {
      loggedIn = true;
      send({ type: 'session', state: 'logged_in' });
    },
    sessionLoggedOut() {
      loggedIn = false;
      lastSpeak = null;
      send({ type: 'session', state: 'logged_out' });
    },
    thinking() {
      send({ type: 'thinking' });
    },
    speak(text, emotion) {
      const safeText = typeof text === 'string' ? text : '';
      const safeEmotion = EMOTIONS.includes(emotion) ? emotion : 'neutral';
      lastSpeak = { text: safeText, emotion: safeEmotion };
      send({ type: 'speak', text: safeText, emotion: safeEmotion });
    },
    idle() {
      send({ type: 'idle' });
    },
    onSyncRequest(handler) {
      syncHandler = handler;
    },
    syncState,
    // 最後に送った状態(sync_request への応答用)
    getState() {
      return { loggedIn, lastSpeak };
    },
    close() {
      channel.close();
    },
  };
}

let senderInstance = null;

// タブ内で共有する送信側(遅延生成)
export function getDisplaySender() {
  if (!senderInstance) senderInstance = createDisplaySender();
  return senderInstance;
}

// 受信側(サブ画面)
export function createDisplayReceiver(handlers = {}) {
  const channel = new BroadcastChannel(CHANNEL_NAME);

  channel.onmessage = (event) => {
    const data = event.data;
    if (!data || typeof data !== 'object' || typeof data.type !== 'string') {
      console.warn('[displayChannel] Invalid message ignored:', data);
      return;
    }

    switch (data.type) {
      case 'session':
        if (data.state === 'logged_in' || data.state === 'logged_out') {
          handlers.onSession?.(data.state);
        } else {
          console.warn('[displayChannel] Unknown session state:', data.state);
        }
        break;
      case 'thinking':
        handlers.onThinking?.();
        break;
      case 'speak':
        if (typeof data.text !== 'string') {
          console.warn('[displayChannel] Invalid speak message ignored:', data);
          break;
        }
        handlers.onSpeak?.(data.text, EMOTIONS.includes(data.emotion) ? data.emotion : 'neutral');
        break;
      case 'idle':
        handlers.onIdle?.();
        break;
      case 'sync_state':
        if (typeof data.loggedIn !== 'boolean') {
          console.warn('[displayChannel] Invalid sync_state ignored:', data);
          break;
        }
        handlers.onSyncState?.(data);
        break;
      case 'sync_request':
        // 他のサブ画面からの要求。受信側では無視する
        break;
      default:
        console.warn('[displayChannel] Unknown message type ignored:', data.type);
    }
  };

  return {
    requestSync() {
      channel.postMessage({ type: 'sync_request' });
    },
    close() {
      channel.close();
    },
  };
}
