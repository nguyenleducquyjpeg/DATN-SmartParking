import { initializeApp } from 'firebase/app';
import { getDatabase } from 'firebase/database';

const firebaseConfig = {
    apiKey: "AIzaSyDw27E9ECJKMmfjZCUkD1MO_EPFSnLrQb8",
    authDomain: "alcohol-detection-a3c5b.firebaseapp.com",
    databaseURL: "https://alcohol-detection-a3c5b-default-rtdb.asia-southeast1.firebasedatabase.app",
    projectId: "alcohol-detection-a3c5b",
    storageBucket: "alcohol-detection-a3c5b.firebasestorage.app",
    messagingSenderId: "183689759430",
    appId: "1:183689759430:web:e95ef84e72001701ab65c7"
};

const app = initializeApp(firebaseConfig);
export const db = getDatabase(app);