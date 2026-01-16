<template>
  <div class="relative w-screen h-screen overflow-hidden bg-black text-white font-sans">
    
    <!-- 背景動画レイヤー -->
    <div class="absolute inset-0 z-0 flex items-center justify-center">
      <video 
        ref="videoPlayer"
        :src="videoSrc" 
        autoplay 
        loop 
        muted 
        playsinline
        class="w-full h-full object-cover"
        @error="handleVideoError"
      ></video>
      
      <div v-if="videoError" class="absolute inset-0 flex items-center justify-center bg-gray-900/80">
        <p class="text-red-400 font-bold">動画が見つかりません: {{ currentVideoState }}</p>
      </div>
    </div>

    <!-- フルスクリーン化ボタン（右下に配置） -->
    <button @click="toggleFullscreen" class="absolute bottom-4 right-4 z-50 p-2 bg-gray-800/50 rounded-full hover:bg-gray-800 text-white opacity-0 hover:opacity-100 transition-opacity">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
      </svg>
    </button>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const currentVideoState = ref('idle'); 
const videoSrc = ref('/videos/idle.mp4'); 
const videoError = ref(false);
const videoPlayer = ref(null);

const VIDEO_PATHS = {
  idle: '/videos/idle.mp4',      
  talking: '/videos/talking.mp4', 
  thinking: '/videos/idle.mp4',   
};

const channel = new BroadcastChannel('livraria_channel');

channel.onmessage = (event) => {
  const { type, state } = event.data;

  if (type === 'chat') {
    if (state && VIDEO_PATHS[state]) {
      changeVideoState(state);
    }
  }
};

const changeVideoState = (newState) => {
  if (currentVideoState.value === newState) return;

  currentVideoState.value = newState;
  videoSrc.value = VIDEO_PATHS[newState];
  videoError.value = false;
  
  if (videoPlayer.value) {
    videoPlayer.value.load();
    videoPlayer.value.play().catch(e => console.error("再生エラー:", e));
  }
};

const handleVideoError = () => {
  console.error(`動画読み込みエラー: ${videoSrc.value}`);
  videoError.value = true;
};

// ユーザー操作によるフルスクリーン化
const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(e => {
      console.log(`自動フルスクリーン化はブロックされました（ユーザー操作が必要です）: ${e.message}`);
    });
  } else {
    document.exitFullscreen();
  }
};

onMounted(() => {
  // マウント時に自動でフルスクリーン化を試みる
  // ※ブラウザの設定によってはブロックされますが、キオスクモードなら動作します
  setTimeout(() => {
    toggleFullscreen();
  }, 1000);
});

onUnmounted(() => {
  channel.close();
});
</script>

<style scoped>
/* スタイルなし */
</style>
```

### 2. Raspberry Pi 側での解決策（コマンドライン）

「ウィンドウが一次ディスプレイに出てしまう」「フルスクリーンにならない」問題を確実に解決するには、ラズベリーパイのターミナルで以下のコマンドを使ってブラウザを起動するのが最適です。

Vueアプリ（`MainApp.vue`）からボタンで開くのではなく、**最初から別プロセスとしてセカンダリ画面を立ち上げておく**方法です。

以下のコマンドをラズベリーパイのターミナルで実行してみてください。

```bash
# Chromiumブラウザをキオスクモード（全画面）で、指定した位置に起動するコマンド
chromium-browser --app="http://localhost:5173/?view=secondary" \
  --window-position=1920,0 \
  --start-fullscreen \
  --kiosk \
  --user-data-dir="/tmp/secondary_display_profile"