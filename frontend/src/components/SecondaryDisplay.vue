<template>
  <div class="relative w-screen h-screen overflow-hidden bg-black text-white font-sans">
    
    <!-- 背景画像 (ユーザー指定: 16:9 PNG) -->
    <img src="/bg.jpg" class="absolute inset-0 w-full h-full object-cover z-0" alt="Background" onerror="this.style.display='none'" />
    <div class="absolute inset-0 bg-black/40 z-10 pointer-events-none"></div>
    
    <!-- Video A (Buffer 1) -->

    <video 
      ref="videoA"
      class="absolute inset-0 w-full h-full object-cover transition-opacity duration-500"
      :class="{ 'opacity-100 z-20': activeVideo === 'A', 'opacity-0 z-0': activeVideo !== 'A' }"
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
      :class="{ 'opacity-100 z-20': activeVideo === 'B', 'opacity-0 z-0': activeVideo !== 'B' }"
      :src="srcB"
      :loop="activeVideo === 'B' && isLooping"
      muted playsinline
      @ended="handleVideoEnded('B')"
      @error="handleVideoError"
    ></video>

    <!-- 字幕レイヤー -->
    <div class="absolute inset-0 z-40 flex flex-col items-center justify-end pb-8 pointer-events-none">
      <div class="w-full max-w-[90vw] px-[2vw] min-h-[15vh] flex flex-col justify-end">
         <transition-group name="subtitle" tag="div" class="flex flex-col space-y-[0.8vh] items-center">
            <div v-for="line in visibleLines" :key="line.id" 
                 class="bg-black/60 backdrop-blur-sm text-white px-[1.2vw] py-[0.8vh] rounded-[0.8vw] text-[2.5vw] font-medium tracking-wide shadow-lg border border-white/10"
                 style="text-shadow: 1px 1px 2px rgba(0,0,0,0.8);">
              {{ line.text }}
            </div>
         </transition-group>
      </div>
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
  idle_loop: '/webm/idle_loop.webm',
  neutral_talking: '/webm/neutral_talking.webm', // 今回は未使用

  // 思考 (Thinking)
  thinking_start: '/webm/thinking_start.webm',
  thinking_talking: '/webm/thinking_talking.webm', // 今回は未使用
  thinking_loop: '/webm/thinking_loop.webm',
  thinking_return: '/webm/thinking_return.webm',

  // 笑顔 (Happy)
  happy_start: '/webm/happy_start.webm',
  happy_talking: '/webm/happy_talking.webm', // 今回は未使用
  happy_loop: '/webm/happy_loop.webm',
  happy_return: '/webm/happy_return.webm',

  // 困り顔 (Sorry)
  sorry_start: '/webm/sorry_start.webm',
  sorry_talking: '/webm/sorry_talking.webm', // 今回は未使用
  sorry_loop: '/webm/sorry_loop.webm',
  sorry_return: '/webm/sorry_return.webm',
};

// --- ステート管理 ---
const visibleLines = ref([]);
const lineIdCounter = ref(0);
const activeVideo = ref('A');
const srcA = ref(VIDEOS.idle_loop);
const srcB = ref('');
const videoA = ref(null);
const videoB = ref(null);

const playbackQueue = ref([]);
const isLooping = ref(true); 
const currentEmotion = ref('neutral'); 

const channel = new BroadcastChannel('livraria_channel');

// --- テキスト処理ロジック ---
const processTextLines = async (text) => {
    if (!text) return;
    
    // 絵文字を除去
    const plainText = text.replace(/([\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF])/g, '');

    // 既存の表示をクリア（あるいは継続させるか？今回は新規発話でクリアする方針）
    visibleLines.value = [];
    
    // 句読点で分割 (。、！ ？ \n)
    // 分割文字に「、」を追加
    const rawLines = plainText.split(/([。、！？\n]+)/).reduce((acc, curr, i, arr) => {
        if (i % 2 === 0) { // 文言
            const trimmed = curr.trim();
            if (trimmed) acc.push(trimmed);
        } else { // 区切り文字
             if (acc.length > 0) acc[acc.length - 1] += curr;
        }
        return acc;
    }, []);

    // 表示ロジック
    // 一行ずつ遅延させて表示する
    for (const lineText of rawLines) {
        if (!lineText.trim()) continue;
        
        // ユニークID生成
        const id = lineIdCounter.value++;
        
        // 配列に追加
        visibleLines.value.push({ id, text: lineText });
        
        // 3行を超えたら古いものを消す
        if (visibleLines.value.length > 3) {
            visibleLines.value.shift();
        }
        
        // 読み上げ速度に合わせてウェイトを入れる（簡易計算: 1文字 * 100ms? 少し早めで）
        // 実際には音声の長さに合わせるのがベストだが、ここでは擬似的に。
        // 長すぎると待たされるので、最大でも1.5秒くらい待つ
        const waitTime = Math.min(lineText.length * 80, 1500); 
        await new Promise(resolve => setTimeout(resolve, waitTime));
    }
};

// --- 通信受信 ---
channel.onmessage = (event) => {
  const { type, text, state } = event.data;
  if (type !== 'chat') return;
  
  console.log(`[Secondary] Received state: ${state}, Text: ${text}, CurrentEmotion: ${currentEmotion.value}`);

  if (state === 'thinking') {
    visibleLines.value = [];
    startThinkingSequence();
  } 
  else if (state === 'idle') {
    returnToIdle();
  } 
  else {
    if (text) processTextLines(text);
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

  // 修正: キューに続きがある場合は、ループ動画であってもループさせない（1回再生後に次へ進むため）
  const isLoopVideo = nextVideoKey.includes('loop');
  if (playbackQueue.value.length > 0) {
    isLooping.value = false;
  } else {
    isLooping.value = isLoopVideo;
  }

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
    // videoChangeCount.value++; // カウンタ削除
    
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
  
  // 修正: talkingをスキップせず、start -> talking -> loop へ
  playbackQueue.value = [
    'thinking_start',
    'thinking_talking',
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

  // 修正: talkingをスキップせず、start -> talking -> loop へ
  if (emotion === 'happy') {
    actionSequence = ['happy_start', 'happy_talking', 'happy_loop'];
  } else if (emotion === 'sorry') {
    actionSequence = ['sorry_start', 'sorry_talking', 'sorry_loop'];
  } else if (emotion === 'neutral') {
    // neutralの場合もtalkingを挟む
    actionSequence = ['neutral_talking', 'idle_loop'];
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
.subtitle-move,
.subtitle-enter-active,
.subtitle-leave-active {
  transition: all 0.5s ease;
}

.subtitle-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.subtitle-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}

/* 削除される要素がスライドの邪魔にならないように */
.subtitle-leave-active {
  position: absolute;
}
</style>