<template>
  <div class="w-full h-full bg-slate-50 flex flex-col">
    <!-- ヘッダー -->
    <header class="bg-white/90 backdrop-blur border-b border-slate-200 p-4 px-8 flex justify-between items-center shadow-sm">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-full flex items-center justify-center text-white font-bold text-lg shadow">
          N
        </div>
        <h1 class="text-xl font-bold text-slate-700">NFC会員情報編集</h1>
      </div>
      <button @click="goBack" class="flex items-center space-x-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-2 px-4 rounded-lg transition-colors">
        <span>🔙</span> <span>戻る</span>
      </button>
    </header>

    <!-- メインコンテンツ -->
    <div class="flex-1 overflow-y-auto p-8">
      <div class="max-w-2xl mx-auto">
        <!-- 手順 1: NFC読み取り または NFC ID入力 -->
        <div v-if="!memberInfo" class="bg-white rounded-2xl shadow-md p-8 border-2 border-orange-100">
          <h2 class="text-2xl font-bold text-slate-700 mb-6">Step 1: NFC会員カードを読み取る</h2>
          
          <div class="space-y-6">
            <!-- 方法1: NFC読み取り -->
            <div class="bg-gradient-to-br from-orange-50 to-red-50 border-2 border-orange-200 rounded-xl p-6">
              <h3 class="text-lg font-bold text-orange-700 mb-4">📱 NFCカードをリーダーにかざす</h3>
              <button @click="startNfcReading" 
                      :disabled="isReadingNfc"
                      class="w-full bg-gradient-to-r from-orange-500 to-red-500 text-white font-bold py-4 rounded-lg hover:from-orange-600 hover:to-red-600 disabled:from-gray-400 disabled:to-gray-400 transition-all transform active:scale-95">
                <span v-if="!isReadingNfc" class="text-xl">🔍 NFC読み取り開始</span>
                <span v-else class="text-xl animate-pulse">⏳ 読み取り中...</span>
              </button>
              <p class="text-sm text-orange-600 mt-3 text-center">タイムアウト: 30秒</p>
            </div>

            <!-- または -->
            <div class="flex items-center space-x-4">
              <div class="flex-1 border-t border-slate-300"></div>
              <span class="text-slate-500 font-semibold">または</span>
              <div class="flex-1 border-t border-slate-300"></div>
            </div>

            <!-- 方法2: 手動入力 -->
            <div class="bg-slate-50 border-2 border-slate-200 rounded-xl p-6">
              <h3 class="text-lg font-bold text-slate-700 mb-4">✏️ NFC IDを手動で入力</h3>
              <input type="text" 
                     v-model="manualNfcId" 
                     placeholder="例: 0123456789ABCDEF"
                     class="w-full bg-white border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all"
                     @keydown.enter="searchByManualId">
              <button @click="searchByManualId"
                      class="w-full mt-4 bg-slate-600 text-white font-bold py-3 rounded-lg hover:bg-slate-700 transition-colors">
                検索
              </button>
            </div>

            <!-- エラーメッセージ -->
            <div v-if="errorMessage" class="bg-red-50 border-l-4 border-red-500 p-4 rounded">
              <p class="text-red-700 font-semibold">❌ エラー</p>
              <p class="text-red-600 text-sm">{{ errorMessage }}</p>
            </div>
          </div>
        </div>

        <!-- 手順 2: 会員情報編集 -->
        <div v-else class="bg-white rounded-2xl shadow-md p-8">
          <h2 class="text-2xl font-bold text-slate-700 mb-2">Step 2: 会員情報を編集</h2>
          <p class="text-sm text-slate-500 mb-6">NFC ID: <span class="font-mono bg-slate-100 px-2 py-1 rounded">{{ currentNfcId }}</span></p>

          <form @submit.prevent="submitChanges" class="space-y-6">
            <!-- 名前 -->
            <div>
              <label class="block text-sm font-bold text-slate-700 mb-2">お名前 (ニックネーム)</label>
              <input type="text" 
                     v-model="formData.name"
                     placeholder="例: 太郎"
                     class="w-full bg-slate-50 border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all">
            </div>

            <!-- 性別 -->
            <div>
              <label class="block text-sm font-bold text-slate-700 mb-2">性別</label>
              <div class="flex space-x-4">
                <label class="flex items-center space-x-2 cursor-pointer">
                  <input type="radio" v-model="formData.gender" value="男性" class="w-4 h-4">
                  <span class="text-slate-700">男性</span>
                </label>
                <label class="flex items-center space-x-2 cursor-pointer">
                  <input type="radio" v-model="formData.gender" value="女性" class="w-4 h-4">
                  <span class="text-slate-700">女性</span>
                </label>
                <label class="flex items-center space-x-2 cursor-pointer">
                  <input type="radio" v-model="formData.gender" value="その他" class="w-4 h-4">
                  <span class="text-slate-700">その他</span>
                </label>
              </div>
            </div>

            <!-- 年齢 -->
            <div>
              <label class="block text-sm font-bold text-slate-700 mb-2">年齢</label>
              <input type="number" 
                     v-model.number="formData.age"
                     min="0"
                     max="150"
                     class="w-full bg-slate-50 border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all">
            </div>

            <!-- 都道府県 -->
            <div>
              <label class="block text-sm font-bold text-slate-700 mb-2">都道府県</label>
              <input type="text" 
                     v-model="formData.live_pref"
                     placeholder="例: 東京都"
                     class="w-full bg-slate-50 border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all">
            </div>

            <!-- 市区町村 -->
            <div>
              <label class="block text-sm font-bold text-slate-700 mb-2">市区町村</label>
              <input type="text" 
                     v-model="formData.live_city"
                     placeholder="例: 渋谷区"
                     class="w-full bg-slate-50 border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all">
            </div>

            <!-- エラーメッセージ -->
            <div v-if="errorMessage" class="bg-red-50 border-l-4 border-red-500 p-4 rounded">
              <p class="text-red-700 font-semibold">❌ エラー</p>
              <p class="text-red-600 text-sm">{{ errorMessage }}</p>
            </div>

            <!-- 成功メッセージ -->
            <div v-if="successMessage" class="bg-green-50 border-l-4 border-green-500 p-4 rounded">
              <p class="text-green-700 font-semibold">✅ 成功</p>
              <p class="text-green-600 text-sm">{{ successMessage }}</p>
            </div>

            <!-- ボタン -->
            <div class="flex space-x-4 pt-4">
              <button type="button"
                      @click="resetForm"
                      class="flex-1 bg-slate-200 text-slate-700 font-bold py-3 rounded-lg hover:bg-slate-300 transition-colors">
                リセット
              </button>
              <button type="submit"
                      :disabled="isSaving"
                      class="flex-1 bg-gradient-to-r from-orange-500 to-red-500 text-white font-bold py-3 rounded-lg hover:from-orange-600 hover:to-red-600 disabled:from-gray-400 disabled:to-gray-400 transition-all transform active:scale-95">
                <span v-if="!isSaving">💾 保存する</span>
                <span v-else>⏳ 保存中...</span>
              </button>
            </div>
          </form>

          <!-- 別のカードを読み取る -->
          <div class="mt-8 pt-8 border-t border-slate-200">
            <button @click="resetSearch"
                    class="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-3 rounded-lg transition-colors">
              別のNFCカードを読み取る
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { getIdToken } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { api } from '../services/api';

// Props
const props = defineProps({
  onBack: {
    type: Function,
    required: true
  }
});

// State
const memberInfo = ref(null);
const currentNfcId = ref('');
const isReadingNfc = ref(false);
const manualNfcId = ref('');
const isSaving = ref(false);
const errorMessage = ref('');
const successMessage = ref('');

const formData = reactive({
  name: '',
  gender: '男性',
  age: 0,
  live_pref: '',
  live_city: ''
});

// Methods
const startNfcReading = async () => {
  isReadingNfc.value = true;
  errorMessage.value = '';
  successMessage.value = '';

  try {
    // NFC APIサーバーからNFC IDを読み取る
    const response = await fetch('http://localhost:5000/nfc/read', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ timeout: 30 })
    });

    if (!response.ok) {
      throw new Error('NFC読み取りに失敗しました');
    }

    const data = await response.json();
    if (data.status === 'ok' && data.idm) {
      currentNfcId.value = data.idm;
      await fetchMemberInfo(data.idm);
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

const searchByManualId = async () => {
  if (!manualNfcId.value.trim()) {
    errorMessage.value = 'NFC IDを入力してください';
    return;
  }

  currentNfcId.value = manualNfcId.value;
  await fetchMemberInfo(manualNfcId.value);
};

const fetchMemberInfo = async (nfcId) => {
  errorMessage.value = '';
  successMessage.value = '';

  try {
    const user = auth.currentUser;
    if (!user) {
      throw new Error('ログインしてください');
    }

    const token = await getIdToken(user);
    const info = await api.getNfcMemberInfo(nfcId, token);

    memberInfo.value = info;
    formData.name = info.personal.name || '';
    formData.gender = info.personal.gender || '男性';
    formData.age = info.personal.age || 0;
    formData.live_pref = info.personal.live_pref || '';
    formData.live_city = info.personal.live_city || '';
  } catch (error) {
    console.error('会員情報取得エラー:', error);
    errorMessage.value = `会員情報取得エラー: ${error.message}`;
    memberInfo.value = null;
  }
};

const submitChanges = async () => {
  if (!currentNfcId.value) {
    errorMessage.value = 'NFC IDが設定されていません';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';
  successMessage.value = '';

  try {
    const user = auth.currentUser;
    if (!user) {
      throw new Error('ログインしてください');
    }

    const token = await getIdToken(user);
    const updates = {
      name: formData.name,
      gender: formData.gender,
      age: formData.age,
      live_pref: formData.live_pref,
      live_city: formData.live_city
    };

    const result = await api.updateNfcMemberInfo(currentNfcId.value, updates, token);
    successMessage.value = `会員情報を更新しました: ${result.updated_fields.join(', ')}`;

    // 成功後、2秒でリセット
    setTimeout(() => {
      resetSearch();
      successMessage.value = '';
    }, 2000);
  } catch (error) {
    console.error('会員情報更新エラー:', error);
    errorMessage.value = `会員情報更新エラー: ${error.message}`;
  } finally {
    isSaving.value = false;
  }
};

const resetForm = () => {
  if (memberInfo.value) {
    formData.name = memberInfo.value.personal.name || '';
    formData.gender = memberInfo.value.personal.gender || '男性';
    formData.age = memberInfo.value.personal.age || 0;
    formData.live_pref = memberInfo.value.personal.live_pref || '';
    formData.live_city = memberInfo.value.personal.live_city || '';
  }
  errorMessage.value = '';
  successMessage.value = '';
};

const resetSearch = () => {
  memberInfo.value = null;
  currentNfcId.value = '';
  manualNfcId.value = '';
  resetForm();
};

const goBack = () => {
  props.onBack();
};
</script>

<style scoped>
/* 特別なスタイルが必要に応じて追加 */
</style>
