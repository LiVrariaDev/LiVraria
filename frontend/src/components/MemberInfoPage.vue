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
      <button @click="goBack" class="flex items-center bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-2 px-4 rounded-lg transition-colors">
        <span>戻る</span>
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
        カード登録・編集
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
        基本情報変更
      </button>
      <button
        @click="currentTab = 'credits'"
        :class="[
          'px-6 py-4 font-semibold transition-colors border-b-2 transition-colors',
          currentTab === 'credits'
            ? 'text-purple-600 border-purple-600'
            : 'text-slate-600 border-transparent hover:text-slate-700'
        ]"
      >
        利用している外部サービス
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

      <!-- 利用している外部サービス（各 API の利用条件にもとづく表示） -->
      <div v-show="currentTab === 'credits'" class="p-8">
        <div class="max-w-2xl mx-auto bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h2 class="text-lg font-bold text-slate-700 mb-4">利用している外部サービス</h2>
          <ul class="divide-y divide-slate-100">
            <li v-for="service in externalServices" :key="service.name" class="py-3">
              <div class="font-semibold text-slate-700">{{ service.name }}</div>
              <div class="text-sm text-slate-500">{{ service.provider }}</div>
              <div class="text-sm text-slate-600 mt-1">{{ service.usage }}</div>
            </li>
          </ul>
          <p class="text-xs text-slate-400 mt-4">Supported by Rakuten Developers</p>
        </div>
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

const externalServices = [
  { name: '楽天ブックス', provider: '楽天グループ株式会社（楽天ブックス書籍検索API）', usage: '本の検索と、書名・著者・表紙・内容紹介・レビューの表示' },
  { name: 'カーリル', provider: '株式会社カーリル（カーリル図書館API）', usage: '公共図書館の蔵書と貸出状況の確認' },
  { name: 'CiNii Books', provider: '国立情報学研究所（CiNii Books API）', usage: '大学図書館の所蔵の確認' },
  { name: 'レファレンス協同データベース', provider: '国立国会図書館（レファレンス協同データベースAPI）', usage: '似た相談の事例を、本の探し方の参考として利用（事例の内容は表示しません）' },
];

const goBack = () => {
  props.onBack();
};
</script>

<style scoped>
/* タブアニメーション */
</style>
