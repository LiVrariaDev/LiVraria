<template>
  <div class="max-w-2xl mx-auto">
    <!-- ローディング状態 -->
    <div v-if="isLoading" class="bg-white rounded-2xl shadow-md p-8 text-center">
      <div class="flex justify-center items-center space-x-2 h-20">
        <div class="w-3 h-3 bg-purple-400 rounded-full animate-bounce"></div>
        <div class="w-3 h-3 bg-purple-400 rounded-full animate-bounce delay-75"></div>
        <div class="w-3 h-3 bg-purple-400 rounded-full animate-bounce delay-150"></div>
      </div>
      <p class="text-slate-600 mt-4">情報を読み込み中...</p>
    </div>

    <!-- フォーム -->
    <div v-else class="bg-white rounded-2xl shadow-md p-8">
      <h2 class="text-2xl font-bold text-slate-700 mb-2">
        <span class="text-3xl mr-2">👤</span>基本情報を変更
      </h2>
      <p class="text-sm text-slate-500 mb-6">初回登録時の情報を編集できます</p>

      <form @submit.prevent="submitChanges" class="space-y-6">
        <!-- 名前 -->
        <div>
          <label class="block text-sm font-bold text-slate-700 mb-2">
            <span class="text-red-500">*</span> お名前 (ニックネーム)
          </label>
          <input
            type="text"
            v-model="formData.name"
            placeholder="例: 太郎"
            required
            class="w-full bg-slate-50 border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-200 transition-all"
          />
          <p class="text-xs text-slate-500 mt-1">AIとの会話の中で親しみを込めて呼びかけられます</p>
        </div>

        <!-- 性別 -->
        <div>
          <label class="block text-sm font-bold text-slate-700 mb-3">
            <span class="text-red-500">*</span> 性別
          </label>
          <div class="flex space-x-4">
            <label class="flex items-center space-x-2 cursor-pointer">
              <input type="radio" v-model="formData.gender" value="男性" class="w-4 h-4" />
              <span class="text-slate-700">男性</span>
            </label>
            <label class="flex items-center space-x-2 cursor-pointer">
              <input type="radio" v-model="formData.gender" value="女性" class="w-4 h-4" />
              <span class="text-slate-700">女性</span>
            </label>
            <label class="flex items-center space-x-2 cursor-pointer">
              <input type="radio" v-model="formData.gender" value="その他" class="w-4 h-4" />
              <span class="text-slate-700">その他</span>
            </label>
          </div>
        </div>

        <!-- 年齢 -->
        <div>
          <label class="block text-sm font-bold text-slate-700 mb-2">
            <span class="text-red-500">*</span> 年齢
          </label>
          <input
            type="number"
            v-model.number="formData.age"
            min="0"
            max="150"
            required
            class="w-full bg-slate-50 border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-200 transition-all"
          />
        </div>

        <!-- 都道府県 -->
        <div>
          <label class="block text-sm font-bold text-slate-700 mb-2">
            <span class="text-slate-400">*</span> 都道府県
          </label>
          <div class="relative">
            <select
              v-model="formData.live_pref"
              class="w-full bg-slate-50 border border-slate-300 rounded-lg py-3 px-4 appearance-none focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-200 transition-all"
            >
              <option value="" disabled>選択してください</option>
              <option v-for="pref in PREFECTURES" :key="pref" :value="pref">
                {{ pref }}
              </option>
            </select>
            <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-500">
              <svg class="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/></svg>
            </div>
          </div>
        </div>

        <!-- 市区町村 -->
        <div>
          <label class="block text-sm font-bold text-slate-700 mb-2">
            <span class="text-slate-400">*</span> 市区町村
          </label>
          <input
            type="text"
            v-model="formData.live_city"
            placeholder="例: 渋谷区"
            class="w-full bg-slate-50 border border-slate-300 rounded-lg py-3 px-4 focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-200 transition-all"
          />
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
          <button
            type="button"
            @click="resetForm"
            class="flex-1 bg-slate-200 text-slate-700 font-bold py-3 rounded-lg hover:bg-slate-300 transition-colors"
          >
            リセット
          </button>
          <button
            type="submit"
            :disabled="isSaving"
            class="flex-1 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold py-3 rounded-lg shadow-md hover:shadow-lg hover:from-purple-600 hover:to-pink-600 disabled:from-gray-400 disabled:to-gray-400 transition-all transform active:scale-95 flex items-center justify-center space-x-2"
          >
            <span v-if="!isSaving" class="text-xl">💾</span>
            <span v-if="!isSaving">変更を保存</span>
            <span v-else>⏳ 保存中...</span>
          </button>
        </div>
      </form>

      <!-- 最終更新日時 -->
      <div v-if="lastUpdated" class="mt-8 pt-6 border-t border-slate-200">
        <p class="text-xs text-slate-500 text-center">
          最終更新: {{ lastUpdated }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { getIdToken } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { api } from '../services/api';

const PREFECTURES = [
  "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
  "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
  "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
  "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
  "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
  "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
  "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
];

const props = defineProps({
  onBack: {
    type: Function,
    required: true
  }
});

const isLoading = ref(true);
const isSaving = ref(false);
const errorMessage = ref('');
const successMessage = ref('');
const lastUpdated = ref('');

const formData = reactive({
  name: '',
  gender: '男性',
  age: 0,
  live_pref: '',
  live_city: ''
});

const originalData = reactive({
  name: '',
  gender: '男性',
  age: 0,
  live_pref: '',
  live_city: ''
});

const fetchUserProfile = async () => {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    const user = auth.currentUser;
    if (!user) {
      throw new Error('ログインしてください');
    }

    const token = await getIdToken(user);
    const userInfo = await api.getUser(user.uid, token);

    // ユーザー情報をフォームに反映
    if (userInfo.personal) {
      formData.name = userInfo.personal.name || '';
      formData.gender = userInfo.personal.gender || '男性';
      formData.age = userInfo.personal.age || 0;
      formData.live_pref = userInfo.personal.live_pref || '';
      // unknownの場合は空文字にする
      formData.live_city = (userInfo.personal.live_city === 'unknown' || !userInfo.personal.live_city) ? '' : userInfo.personal.live_city;

      // オリジナル値も保存
      originalData.name = formData.name;
      originalData.gender = formData.gender;
      originalData.age = formData.age;
      originalData.live_pref = formData.live_pref;
      originalData.live_city = formData.live_city;
    }

    if (userInfo.lastlogin) {
      const date = new Date(userInfo.lastlogin);
      lastUpdated.value = date.toLocaleString('ja-JP');
    }
  } catch (error) {
    console.error('プロフィール取得エラー:', error);
    errorMessage.value = `情報取得エラー: ${error.message}`;
  } finally {
    isLoading.value = false;
  }
};

const resetForm = () => {
  formData.name = originalData.name;
  formData.gender = originalData.gender;
  formData.age = originalData.age;
  formData.live_pref = originalData.live_pref;
  formData.live_city = originalData.live_city;
  errorMessage.value = '';
  successMessage.value = '';
};

const submitChanges = async () => {
  if (!formData.name.trim()) {
    errorMessage.value = 'お名前を入力してください';
    return;
  }

  if (!formData.gender) {
    errorMessage.value = '性別を選択してください';
    return;
  }

  if (formData.age < 0 || formData.age > 150) {
    errorMessage.value = '年齢を正しく入力してください';
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

    // 変更があるかチェック
    const hasChanges =
      formData.name !== originalData.name ||
      formData.gender !== originalData.gender ||
      formData.age !== originalData.age ||
      formData.live_pref !== originalData.live_pref ||
      formData.live_city !== originalData.live_city;

    if (!hasChanges) {
      errorMessage.value = '変更がありません';
      isSaving.value = false;
      return;
    }

    // ユーザー情報を更新
    const updates = {
      personal: {
        name: formData.name,
        gender: formData.gender,
        age: formData.age,
        live_pref: formData.live_pref,
        live_city: formData.live_city
      }
    };

    await api.updateUser(user.uid, updates, token);

    // オリジナル値を更新
    originalData.name = formData.name;
    originalData.gender = formData.gender;
    originalData.age = formData.age;
    originalData.live_pref = formData.live_pref;
    originalData.live_city = formData.live_city;

    successMessage.value = '基本情報を更新しました！';
    lastUpdated.value = new Date().toLocaleString('ja-JP');

    setTimeout(() => {
      successMessage.value = '';
    }, 3000);
  } catch (error) {
    console.error('プロフィール更新エラー:', error);
    errorMessage.value = `更新エラー: ${error.message}`;
  } finally {
    isSaving.value = false;
  }
};

onMounted(() => {
  fetchUserProfile();
});
</script>

<style scoped>
/* 特別なスタイルが必要に応じて追加 */
</style>
