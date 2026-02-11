<template>
  <div class="relative w-screen h-screen overflow-hidden bg-black text-white font-sans">
    
    <!-- Video A (Buffer 1) -->
    <!-- 修正: :loop="isLooping" を追加し、アクティブな時だけループ属性を有効化 -->
    <video 
      ref="videoA"
      class="absolute inset-0 w-full h-full object-cover transition-opacity duration-500"
      :class="{ 'opacity-100 z-10': activeVideo === 'A', 'opacity-0 z-0': activeVideo !== 'A' }"
      :src="srcA"
      :loop="activeVideo === 'A' && isLooping"
      muted playsinline
      @ended="handleVideoEnded('A')"
      @error="handleVideoError"
    ></video>

    <!-- Video B (Buffer 2) -->
    <video 
      ref="videoB"
      class="absolute inset-0 w-full h-full object-cover transition-opacity duration-500"
      :class="{ 'opacity-100 z-10': activeVideo === 'B', 'opacity-0 z-0': activeVideo !== 'B' }"
      :src="srcB"
      :loop="activeVideo === 'B' && isLooping"
      muted playsinline
      @ended="handleVideoEnded('B')"
      @error="handleVideoError"
    ></video>

    <!-- 吹き出しレイヤー -->
    <div class="absolute inset-0 z-20 flex flex-col items-center justify-end pb-16 pointer-events-none">
      <transition name="fade">
        <div v-if="currentMessage" class="max-w-5xl w-full mx-10">
          <div class="bg-white/95 backdrop-blur-md text-gray-800 p-8 rounded-3xl shadow-2xl border-4 border-blue-100 relative">
            <div class="absolute -bottom-4 left-1/2 transform -translate-x-1/2 w-8 h-8 bg-white/95 rotate-45 border-b-4 border-r-4 border-blue-100"></div>
            <p class="text-4xl font-bold leading-relaxed text-center font-serif" v-html="currentMessage"></p>
          </div>
        </div>
      </transition>
    </div>
    
    <!-- フルスクリーン化ボタン -->
    <button @click="toggleFullscreen" class="absolute bottom-4 right-4 z-50 p-2 bg-gray-800/50 rounded-full hover:bg-gray-800 text-white opacity-0 hover:opacity-100 transition-opacity pointer-events-auto">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue';

// --- 動画ファイルの定義 ---
// ※ ファイル名が正しいか必ず確認してください
const VIDEOS = {
  idle_loop: '/videos/idle_loop.mp4',
  thinking_start: '/videos/thinking_start.mp4',
  thinking_loop: '/videos/thinking_loop.mp4',
  happy_action: '/videos/happy_action.mp4',
  happy_return: '/videos/happy_return.mp4',
  sorry_action: '/videos/sorry_action.mp4',
  sorry_return: '/videos/sorry_return.mp4',
  neutral_action: '/videos/neutral_action.mp4',
  neutral_return: '/videos/neutral_return.mp4',
};

// --- ステート管理 ---
const currentMessage = ref('');
const activeVideo = ref('A');
const srcA = ref(VIDEOS.idle_loop);
const srcB = ref('');
const videoA = ref(null);
const videoB = ref(null);

const playbackQueue = ref([]);
const isLooping = ref(true); // 現在再生中の動画をループさせるか
const channel = new BroadcastChannel('livraria_channel');

// --- 通信受信 ---
channel.onmessage = (event) => {
  const { type, text, state } = event.data;
  if (type !== 'chat') return;
  
  console.log(`State received: ${state}, Text: ${text}`);

  if (state === 'thinking') {
    currentMessage.value = '';
    startThinkingSequence();
  } else if (state === 'idle') {
    returnToIdle();
  } else {
    if (text) currentMessage.value = text;
    playEmotionAction(state);
  }
};

// --- 動画制御ロジック ---

const playNextInQueue = async () => {
  if (playbackQueue.value.length === 0) return;

  const nextVideoKey = playbackQueue.value.shift();
  const nextSrc = VIDEOS[nextVideoKey];
  
  if (!nextSrc) {
    console.warn(`Video source not found: ${nextVideoKey}`);
    return;
  }

  // ループ設定の更新: ファイル名に 'loop' が含まれていればループ有効
  // これにより <video :loop="..."> が反応し、ネイティブループになる
  isLooping.value = nextVideoKey.includes('loop');

  const nextPlayerId = activeVideo.value === 'A' ? 'B' : 'A';
  const nextPlayerRef = nextPlayerId === 'A' ? videoA : videoB;
  const nextSrcRef = nextPlayerId === 'A' ? srcA : srcB;

  nextSrcRef.value = nextSrc;
  await nextTick();
  
  const player = nextPlayerRef.value;
  player.load();
  
  try {
    await player.play();
    
    // 切り替え
    activeVideo.value = nextPlayerId;
    
    // 前のプレイヤーを停止
    const prevPlayer = nextPlayerId === 'A' ? videoB.value : videoA.value;
    prevPlayer.pause();
    prevPlayer.currentTime = 0;
    
  } catch (e) {
    console.error("Play failed:", e);
  }
};

// 再生終了時のハンドラ
// ※ ネイティブループ有効時は発火しないため、ループしない動画の終了検知専用になる
const handleVideoEnded = (playerId) => {
  if (playerId !== activeVideo.value) return;

  if (playbackQueue.value.length > 0) {
    playNextInQueue();
  } else {
    // キューが空で、かつループ設定でない場合（アクション動画の最後など）
    // 最後のフレームで停止したままにする（pause状態）
    if (!isLooping.value) {
      const current = activeVideo.value === 'A' ? videoA.value : videoB.value;
      current.pause();
    }
  }
};

// --- シナリオ定義 ---

const startThinkingSequence = () => {
  // 思考開始：現在の再生を中断して即座に遷移
  playbackQueue.value = [
    'thinking_start',
    'thinking_loop'
  ];
  playNextInQueue(); // 強制割り込み再生
};

const playEmotionAction = (emotion) => {
  let actionKey = 'neutral_action';
  if (emotion === 'happy') actionKey = 'happy_action';
  if (emotion === 'sorry') actionKey = 'sorry_action';
  if (emotion === 'thinking') actionKey = 'thinking_loop';
  
  playbackQueue.value = [actionKey];
  playNextInQueue(); // 強制割り込み再生
};

const returnToIdle = () => {
  const returnKey = 'neutral_return'; 
  
  playbackQueue.value = [
    returnKey,
    'idle_loop'
  ];
  
  // ここでは強制割り込みせず、現在のアクション（発話）が終わるのを待つ
  // もし現在がループ動画（思考中など）なら強制遷移させる
  if (isLooping.value) {
    playNextInQueue();
  }
};

// 初期化
onMounted(async () => {
  const player = videoA.value;
  player.src = VIDEOS.idle_loop;
  isLooping.value = true; // 初期状態はループ
  await nextTick();
  player.play().catch(e => console.log("Init play error", e));
  videoB.value.src = "";
});

onUnmounted(() => {
  channel.close();
});

const handleVideoError = (e) => {
  console.error("Video Error:", e);
};

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(e => console.log(e));
  } else {
    document.exitFullscreen();
  }
};
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease, transform 0.5s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>