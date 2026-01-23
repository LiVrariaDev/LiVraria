<template>
  <div class="max-w-2xl mx-auto">
    <!-- 登録状態に応じた表示 -->
    <div v-if="!registeredCard" class="space-y-6">
      <!-- 新規登録モード -->
      <div class="bg-white rounded-2xl shadow-md p-8 border-2 border-purple-100">
        <h2 class="text-2xl font-bold text-slate-700 mb-6">
          <span class="text-3xl mr-2">💳</span>NFCカードを登録する
        </h2>

        <div class="space-y-6">
          <!-- 方法1: NFC読み取り -->
          <div class="bg-gradient-to-br from-purple-50 to-pink-50 border-2 border-purple-200 rounded-xl p-6">
            <h3 class="text-lg font-bold text-purple-700 mb-4">📱 NFCカードをリーダーにかざす</h3>
            <button
              @click="startNfcReading"
              :disabled="isReadingNfc"
              class="w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold py-4 rounded-lg hover:from-purple-600 hover:to-pink-600 disabled:from-gray-400 disabled:to-gray-400 transition-all transform active:scale-95"
            >
              <span v-if="!isReadingNfc" class="text-xl">🔍 NFC読み取り開始</span>
              <span v-else class="text-xl animate-pulse">⏳ 読み取り中...</span>
            </button>
            <p class="text-sm text-purple-600 mt-3 text-center">タイムアウト: 30秒</p>
          </div>

          <!-- または -->
          <div class="flex items-center space-x-4">
            <div class="flex-1 border-t border-slate-300"></div>
            <span class="text-slate-500 font-semibold">または</span>
            <div class="flex-1 border-t border-slate-300"></div>
          </div>

          <!-- 方法2: 手動入力 -->
          <div class="bg-slate-50 border-2 border-slate-200 rounded-xl p-6">
            <h3 class="text-lg font-bold text-slate-700 mb-4">✏️ NFCカードIDを手動で入力</h3>
            <input
              type="text"
              v-model="manualCardId"
              placeholder="例: 0123456789ABCDEF"
              class="w-full bg-white border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-200 transition-all"
              @keydown.enter="registerCardManual"
            />
            <button
              @click="registerCardManual"
              class="w-full mt-4 bg-slate-600 text-white font-bold py-3 rounded-lg hover:bg-slate-700 transition-colors"
            >
              登録
            </button>
          </div>

          <!-- エラーメッセージ -->
          <div v-if="errorMessage" class="bg-red-50 border-l-4 border-red-500 p-4 rounded">
            <p class="text-red-700 font-semibold">❌ エラー</p>
            <p class="text-red-600 text-sm">{{ errorMessage }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- カード登録済みモード -->
    <div v-else class="space-y-6">
      <!-- 現在のカード情報 -->
      <div class="bg-white rounded-2xl shadow-md p-8 border-2 border-purple-100">
        <h2 class="text-2xl font-bold text-slate-700 mb-6">
          <span class="text-3xl mr-2">✅</span>登録済みのカード
        </h2>

        <div class="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-6 mb-6">
          <div class="flex items-center space-x-4">
            <div class="text-5xl">🎫</div>
            <div>
              <p class="text-sm text-slate-600">カードID</p>
              <p class="text-2xl font-bold text-slate-800 font-mono">{{ registeredCard }}</p>
              <p class="text-xs text-slate-500 mt-2">{{ registrationDate }}</p>
            </div>
          </div>
        </div>

        <!-- 成功メッセージ -->
        <div v-if="successMessage" class="bg-green-50 border-l-4 border-green-500 p-4 rounded mb-6">
          <p class="text-green-700 font-semibold">✅ 成功</p>
          <p class="text-green-600 text-sm">{{ successMessage }}</p>
        </div>

        <!-- ボタン -->
        <div class="flex space-x-4">
          <button
            @click="changeCard"
            class="flex-1 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold py-3 rounded-lg hover:from-purple-600 hover:to-pink-600 transition-colors"
          >
            <span class="mr-2">🔄</span>カードを変更する
          </button>
          <button
            @click="unregisterCard"
            class="flex-1 bg-red-50 hover:bg-red-100 text-red-600 font-bold py-3 rounded-lg border border-red-200 transition-colors"
          >
            <span class="mr-2">❌</span>登録を解除
          </button>
        </div>
      </div>

      <!-- 新規カード登録フォーム（変更時）-->
      <div v-if="isChangingCard" class="bg-white rounded-2xl shadow-md p-8 border-2 border-orange-100">
        <h2 class="text-2xl font-bold text-slate-700 mb-6">
          <span class="text-3xl mr-2">🔄</span>カードを変更する
        </h2>

        <div class="space-y-6">
          <!-- 方法1: NFC読み取り -->
          <div class="bg-gradient-to-br from-orange-50 to-yellow-50 border-2 border-orange-200 rounded-xl p-6">
            <h3 class="text-lg font-bold text-orange-700 mb-4">📱 新しいNFCカードをリーダーにかざす</h3>
            <button
              @click="startNfcReadingForChange"
              :disabled="isReadingNfc"
              class="w-full bg-gradient-to-r from-orange-500 to-yellow-500 text-white font-bold py-4 rounded-lg hover:from-orange-600 hover:to-yellow-600 disabled:from-gray-400 disabled:to-gray-400 transition-all transform active:scale-95"
            >
              <span v-if="!isReadingNfc" class="text-xl">🔍 NFC読み取り開始</span>
              <span v-else class="text-xl animate-pulse">⏳ 読み取り中...</span>
            </button>
          </div>

          <!-- または -->
          <div class="flex items-center space-x-4">
            <div class="flex-1 border-t border-slate-300"></div>
            <span class="text-slate-500 font-semibold">または</span>
            <div class="flex-1 border-t border-slate-300"></div>
          </div>

          <!-- 方法2: 手動入力 -->
          <div class="bg-slate-50 border-2 border-slate-200 rounded-xl p-6">
            <h3 class="text-lg font-bold text-slate-700 mb-4">✏️ 新しいNFCカードIDを入力</h3>
            <input
              type="text"
              v-model="newCardId"
              placeholder="例: FEDCBA9876543210"
              class="w-full bg-white border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all"
              @keydown.enter="confirmCardChange"
            />
            <button
              @click="confirmCardChange"
              :disabled="isSaving"
              class="w-full mt-4 bg-orange-600 text-white font-bold py-3 rounded-lg hover:bg-orange-700 disabled:bg-gray-400 transition-colors"
            >
              <span v-if="!isSaving">変更を確定</span>
              <span v-else>⏳ 処理中...</span>
            </button>
          </div>

          <!-- キャンセル -->
          <button
            @click="cancelCardChange"
            class="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-3 rounded-lg transition-colors"
          >
            キャンセル
          </button>

          <!-- エラーメッセージ -->
          <div v-if="errorMessage" class="bg-red-50 border-l-4 border-red-500 p-4 rounded">
            <p class="text-red-700 font-semibold">❌ エラー</p>
            <p class="text-red-600 text-sm">{{ errorMessage }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { getIdToken } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { api } from '../services/api';

const props = defineProps({
  onBack: {
    type: Function,
    required: true
  }
});

const registeredCard = ref(null);
const registrationDate = ref('');
const isReadingNfc = ref(false);
const isChangingCard = ref(false);
const isSaving = ref(false);
const manualCardId = ref('');
const newCardId = ref('');
const errorMessage = ref('');
const successMessage = ref('');

const startNfcReading = async () => {
  isReadingNfc.value = true;
  errorMessage.value = '';
  successMessage.value = '';

  try {
    const response = await fetch('http://localhost:5000/nfc/read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ timeout: 30 })
    });

    if (!response.ok) throw new Error('NFC読み取りに失敗しました');

    const data = await response.json();
    if (data.status === 'ok' && data.idm) {
      await registerCard(data.idm);
    } else if (data.status === 'timeout') {
      errorMessage.value = 'NFC読み取りがタイムアウトしました。もう一度試してください。';
    }
  } catch (error) {
    console.error('NFC読み取りエラー:', error);
    errorMessage.value = `NFC読み取りエラー: ${error.message}`;
  } finally {
    isReadingNfc.value = false;
  }
};

const startNfcReadingForChange = async () => {
  isReadingNfc.value = true;
  errorMessage.value = '';

  try {
    const response = await fetch('http://localhost:5000/nfc/read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ timeout: 30 })
    });

    if (!response.ok) throw new Error('NFC読み取りに失敗しました');

    const data = await response.json();
    if (data.status === 'ok' && data.idm) {
      newCardId.value = data.idm;
    } else if (data.status === 'timeout') {
      errorMessage.value = 'NFC読み取りがタイムアウトしました。もう一度試してください。';
    }
  } catch (error) {
    console.error('NFC読み取りエラー:', error);
    errorMessage.value = `NFC読み取りエラー: ${error.message}`;
  } finally {
    isReadingNfc.value = false;
  }
};

const registerCardManual = async () => {
  if (!manualCardId.value.trim()) {
    errorMessage.value = 'NFCカードIDを入力してください';
    return;
  }
  await registerCard(manualCardId.value);
};

const registerCard = async (cardId) => {
  errorMessage.value = '';
  successMessage.value = '';

  try {
    const user = auth.currentUser;
    if (!user) throw new Error('ログインしてください');

    const token = await getIdToken(user);
    const result = await api.registerNfc(cardId, user.uid, token);

    registeredCard.value = cardId;
    registrationDate.value = new Date().toLocaleString('ja-JP');
    successMessage.value = 'NFCカードを登録しました！';
    manualCardId.value = '';

    setTimeout(() => {
      successMessage.value = '';
    }, 3000);
  } catch (error) {
    console.error('カード登録エラー:', error);
    errorMessage.value = `登録エラー: ${error.message}`;
  }
};

const changeCard = () => {
  isChangingCard.value = true;
  newCardId.value = '';
  errorMessage.value = '';
};

const cancelCardChange = () => {
  isChangingCard.value = false;
  newCardId.value = '';
  errorMessage.value = '';
};

const confirmCardChange = async () => {
  if (!newCardId.value.trim()) {
    errorMessage.value = '新しいNFCカードIDを入力してください';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    const user = auth.currentUser;
    if (!user) throw new Error('ログインしてください');

    const token = await getIdToken(user);

    // 旧カードを解除
    if (registeredCard.value) {
      await api.unregisterNfc(registeredCard.value, token);
    }

    // 新カードを登録
    await api.registerNfc(newCardId.value, user.uid, token);

    registeredCard.value = newCardId.value;
    registrationDate.value = new Date().toLocaleString('ja-JP');
    isChangingCard.value = false;
    newCardId.value = '';
    successMessage.value = 'NFCカードを変更しました！';

    setTimeout(() => {
      successMessage.value = '';
    }, 3000);
  } catch (error) {
    console.error('カード変更エラー:', error);
    errorMessage.value = `変更エラー: ${error.message}`;
  } finally {
    isSaving.value = false;
  }
};

const unregisterCard = async () => {
  if (!confirm('このカードの登録を解除してもよろしいですか？')) return;

  try {
    const user = auth.currentUser;
    if (!user) throw new Error('ログインしてください');

    const token = await getIdToken(user);
    await api.unregisterNfc(registeredCard.value, token);

    registeredCard.value = null;
    registrationDate.value = '';
    successMessage.value = 'NFCカードの登録を解除しました';

    setTimeout(() => {
      successMessage.value = '';
    }, 3000);
  } catch (error) {
    console.error('カード削除エラー:', error);
    errorMessage.value = `削除エラー: ${error.message}`;
  }
};

onMounted(async () => {
  // ユーザーのNFC登録状況を確認
  try {
    const user = auth.currentUser;
    if (!user) return;

    const token = await getIdToken(user);
    const userInfo = await api.getUser(user.uid, token);

    // ユーザーが既にカード登録しているか確認
    // （バックエンドで管理されているNFC IDを取得する必要があります）
    // ここでは、NFC登録状態は別途取得する必要があります
    // 簡略化のため、初期状態は「未登録」とします
  } catch (error) {
    console.error('ユーザー情報取得エラー:', error);
  }
});
</script>

<style scoped>
/* 特別なスタイルが必要に応じて追加 */
</style>
