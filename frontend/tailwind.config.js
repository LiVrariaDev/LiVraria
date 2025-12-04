export default {
  // content: Tailwindがスキャンするファイルを指定します
  // これにより、.vueファイルと.htmlファイル内のクラス名が認識されます
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
