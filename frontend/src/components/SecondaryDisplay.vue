<template>
  <div class="relative w-screen h-screen overflow-hidden bg-black text-white font-sans">
    
    <!-- Video A (Buffer 1) -->
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
    
    <!-- Debug Counter -->
    <div class="absolute top-4 right-4 z-50 bg-black/50 text-white p-2 rounded text-xl font-mono border border-white/30 pointer-events-none">
        Count: {{ videoChangeCount }}<br>
        State: {{ currentEmotion }}<br>
        Queue: {{ playbackQueue.length }}
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
const VIDEOS = {
  // 通常 (Neutral)
  idle_loop: '/videos/idle_loop.mp4',
  neutral_talking: '/videos/neutral_talking.mp4', // 今回は未使用

  // 思考 (Thinking)
  thinking_start: '/videos/thinking_start.mp4',
  thinking_talking: '/videos/thinking_talking.mp4', // 今回は未使用
  thinking_loop: '/videos/thinking_loop.mp4',
  thinking_return: '/videos/thinking_return.mp4',

  // 笑顔 (Happy)
  happy_start: '/videos/happy_start.mp4',
  happy_talking: '/videos/happy_talking.mp4', // 今回は未使用
  happy_loop: '/videos/happy_loop.mp4',
  happy_return: '/videos/happy_return.mp4',

  // 困り顔 (Sorry)
  sorry_start: '/videos/sorry_start.mp4',
  sorry_talking: '/videos/sorry_talking.mp4', // 今回は未使用
  sorry_loop: '/videos/sorry_loop.mp4',
  sorry_return: '/videos/sorry_return.mp4',
};

// --- ステート管理 ---
const currentMessage = ref('');
const activeVideo = ref('A');
const srcA = ref(VIDEOS.idle_loop);
const srcB = ref('');
const videoA = ref(null);
const videoB = ref(null);

const playbackQueue = ref([]);
const isLooping = ref(true); 
const currentEmotion = ref('neutral'); 
const videoChangeCount = ref(0); // デバッグ用カウンタ

const channel = new BroadcastChannel('livraria_channel');

// --- 通信受信 ---
channel.onmessage = (event) => {
  const { type, text, state } = event.data;
  if (type !== 'chat') return;
  
  console.log(`[Secondary] Received state: ${state}, Text: ${text}, CurrentEmotion: ${currentEmotion.value}`);

  if (state === 'thinking') {
    currentMessage.value = '';
    startThinkingSequence();
  } 
  else if (state === 'idle') {
    returnToIdle();
  } 
  else {
    if (text) currentMessage.value = text;
    // 修正: none が来たら強制的に neutral にする (二重防御)
    let safeState = state;
    if (!safeState || safeState === 'none') {
        console.warn(`[Secondary] Invalid state '${safeState}' detected. Forcing to 'neutral'.`);
        safeState = 'neutral';
    }
    playEmotionAction(safeState);

  }
};

// --- ヘルパー: 即時再生すべきか判定 ---
const shouldPlayImmediately = () => {
  const currentVideo = activeVideo.value === 'A' ? videoA.value : videoB.value;
  // 1. ループ中ならいつでも割り込みOK
  if (isLooping.value) return true;
  
  // 2. 動画プレイヤーが存在しない、または停止/終了しているならOK
  if (!currentVideo || currentVideo.paused || currentVideo.ended) return true;
  
  // 3. それ以外（再生中のワンショット動画）は割り込まない
  return false;
};

// --- 動画制御ロジック ---

const playNextInQueue = async () => {
  if (playbackQueue.value.length === 0) return;

  const nextVideoKey = playbackQueue.value.shift();
  const nextSrc = VIDEOS[nextVideoKey];
  
  console.log(`[Secondary] Playing next: ${nextVideoKey}`);

  if (!nextSrc) {
    console.warn(`Video source not found: ${nextVideoKey}`);
    if (playbackQueue.value.length > 0) playNextInQueue();
    return;
  }

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
    activeVideo.value = nextPlayerId;
    videoChangeCount.value++; // カウンタを加算
    
    // 前のプレイヤーを停止
    const prevPlayer = nextPlayerId === 'A' ? videoB.value : videoA.value;
    prevPlayer.pause();
    prevPlayer.currentTime = 0;
    
  } catch (e) {
    console.error("Play failed:", e);
    if (playbackQueue.value.length > 0) playNextInQueue();
  }
};

const handleVideoEnded = (playerId) => {
  if (playerId !== activeVideo.value) return;

  if (playbackQueue.value.length > 0) {
    playNextInQueue();
  } else {
    // キューが空
    if (!isLooping.value) {
      const current = activeVideo.value === 'A' ? videoA.value : videoB.value;
      current.pause(); // 最後のフレームで停止
    }
  }
};

// --- シナリオ遷移定義 ---

// 1. 思考中へ遷移
const startThinkingSequence = () => {
  currentEmotion.value = 'thinking';
  
  // 修正: talkingをスキップし、start -> loop へ直結
  playbackQueue.value = [
    'thinking_start',
    'thinking_loop'
  ];
  // 存在しないキーを除外
  playbackQueue.value = playbackQueue.value.filter(key => VIDEOS[key]);
  
  if (shouldPlayImmediately()) {
    playNextInQueue();
  }
};

// 2. 感情発話アクションへ遷移 (回答受信時)
const playEmotionAction = (emotion) => {
  let transitionQueue = [];
  
  if (currentEmotion.value === 'thinking') {
    transitionQueue.push('thinking_return');
  } else if (currentEmotion.value !== 'neutral' && currentEmotion.value !== emotion) {
    const returnKey = `${currentEmotion.value}_return`;
    if (VIDEOS[returnKey]) transitionQueue.push(returnKey);
  }

  currentEmotion.value = emotion;
  let actionSequence = [];

  // 修正: talkingをスキップし、start -> loop へ直結
  if (emotion === 'happy') {
    actionSequence = ['happy_start', 'happy_loop'];
  } else if (emotion === 'sorry') {
    actionSequence = ['sorry_start', 'sorry_loop'];
  } else if (emotion === 'neutral') {
    // neutralの場合は特定のstartモーションがないため、基本待機(idle_loop)に戻す
    actionSequence = ['idle_loop'];
  } else {
    actionSequence = ['idle_loop'];
  }

  playbackQueue.value = [...transitionQueue, ...actionSequence];
  
  if (shouldPlayImmediately()) {
    playNextInQueue();
  }
};

// 3. 待機へ戻る (発話終了時)
const returnToIdle = () => {
  let returnSequence = [];
  const emotion = currentEmotion.value;

  // 各感情に対応するループ動画とリターンシーケンスを定義
  let loopVideo = '';

  if (emotion === 'happy') {
    loopVideo = 'happy_loop';
    returnSequence = ['happy_return', 'idle_loop'];
  } else if (emotion === 'sorry') {
    loopVideo = 'sorry_loop';
    returnSequence = ['sorry_return', 'idle_loop'];
  } else if (emotion === 'thinking') {
    loopVideo = 'thinking_loop';
    returnSequence = ['thinking_return', 'idle_loop'];
  } else {
    // neutralの場合
    returnSequence = ['idle_loop'];
  }

  currentEmotion.value = 'neutral';

  // 修正: キュー内に「その感情のループ動画」がまだ残っているか確認
  // 残っている場合＝まだその感情の再生が始まっていない、または途中
  // この場合は、キューを上書きせず、ループ動画の後にリターンシーケンスを追記する
  const loopIndex = playbackQueue.value.indexOf(loopVideo);

  if (loopIndex !== -1) {
    // ループ動画までは維持し、その後にリターンシーケンスを結合
    const preservedQueue = playbackQueue.value.slice(0, loopIndex + 1);
    playbackQueue.value = [...preservedQueue, ...returnSequence];
  } else {
    // ループ動画がない（すでに再生中、または存在しない）場合は、通常通りリターンシーケンスで上書き
    playbackQueue.value = returnSequence;
  }

  console.log(`[Secondary] Return queue:`, playbackQueue.value);

  if (shouldPlayImmediately()) {
    playNextInQueue();
  }
};

// 初期化
onMounted(async () => {
  const player = videoA.value;
  player.src = VIDEOS.idle_loop;
  isLooping.value = true;
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