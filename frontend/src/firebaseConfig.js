import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyAEOI57naDp3zP4jFKLqhpHrV0EmD2Hzdc",
  authDomain: "livraria-ffae4.firebaseapp.com",
  projectId: "livraria-ffae4",
  storageBucket: "livraria-ffae4.firebasestorage.app",
  messagingSenderId: "293054418871",
  appId: "1:293054418871:web:66e2bd1d299d746613e232",
  measurementId: "G-F3N0NMNF1L"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Firebase Authenticationのインスタンスを取得してエクスポート
const auth = getAuth(app);
export { auth };
