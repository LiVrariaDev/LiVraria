<template>
  <div class="w-full h-full bg-slate-50 flex flex-col">
    <!-- ヘッダー -->
    <header class="bg-white/90 backdrop-blur border-b border-slate-200 p-4 px-8 flex justify-between items-center shadow-sm">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-white font-bold text-lg shadow">
          M
        </div>
        <h1 class="text-xl font-bold text-slate-700">会員情報</h1>
      </div>
      <button @click="goBack" class="flex items-center space-x-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-2 px-4 rounded-lg transition-colors">
        <span>🔙</span> <span>戻る</span>
      </button>
    </header>

    <!-- タブナビゲーション -->
    <div class="bg-white border-b border-slate-200 px-8 flex space-x-1">
      <button
        @click="currentTab = 'card'"
        :class="[
          'px-6 py-4 font-semibold transition-colors border-b-2 transition-colors',
          currentTab === 'card'
            ? 'text-purple-600 border-purple-600'
            : 'text-slate-600 border-transparent hover:text-slate-700'
        ]"
      >
        <span class="mr-2">💳</span>カード登録・編集
      </button>
      <button
        @click="currentTab = 'profile'"
        :class="[
          'px-6 py-4 font-semibold transition-colors border-b-2 transition-colors',
          currentTab === 'profile'
            ? 'text-purple-600 border-purple-600'
            : 'text-slate-600 border-transparent hover:text-slate-700'
        ]"
      >
        <span class="mr-2">👤</span>基本情報変更
      </button>
    </div>

    <!-- コンテンツエリア -->
    <div class="flex-1 overflow-y-auto">
      <!-- カード登録・編集タブ -->
      <div v-show="currentTab === 'card'" class="p-8">
        <CardRegistration :onBack="goBack" />
      </div>

      <!-- 基本情報変更タブ -->
      <div v-show="currentTab === 'profile'" class="p-8">
        <ProfileEditor :onBack="goBack" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import CardRegistration from './CardRegistration.vue';
import ProfileEditor from './ProfileEditor.vue';

const props = defineProps({
  onBack: {
    type: Function,
    required: true
  }
});

const currentTab = ref('card');

const goBack = () => {
  props.onBack();
};
</script>

<style scoped>
/* タブアニメーション */
</style>
