// Firebase pageview counter
// Fill in your Firebase Web App config below (from Firebase Console → Project Settings → General → Your apps)

import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js';
import {
    getFirestore,
    doc,
    setDoc,
    getDoc,
    onSnapshot,
    increment
} from 'https://www.gstatic.com/firebasejs/11.0.1/firebase-firestore.js';

const firebaseConfig = {
    apiKey: 'AIzaSyAldkDxHWDpyleDw7qvs6yrDMqIrdrrn2w',
    authDomain: 'imachneyuwang-click.firebaseapp.com',
    projectId: 'imachneyuwang-click',
    storageBucket: 'imachneyuwang-click.firebasestorage.app',
    messagingSenderId: '1079858984335',
    appId: '1:1079858984335:web:fbfd629aa48c6162b807fa',
    measurementId: 'G-DZEQTFN9SM'
};

let firestore;

function initializeFirebaseIfNeeded() {
    if (firestore) return firestore;
    const app = initializeApp(firebaseConfig);
    firestore = getFirestore(app);
    return firestore;
}

function getGlobalCounterRef() {
    const db = initializeFirebaseIfNeeded();
    return doc(db, 'stats', 'site');
}

function getPerPageCounterRef() {
    const db = initializeFirebaseIfNeeded();
    const pageKey = encodeURIComponent(window.location.pathname || '/');
    return doc(db, 'pageviews', pageKey);
}

async function incrementCountersOncePerSession() {
    const sessionKey = `pv-incremented:${window.location.pathname || '/'}`;
    if (sessionStorage.getItem(sessionKey)) return;

    try {
        // Global site counter
        await setDoc(getGlobalCounterRef(), { count: increment(1) }, { merge: true });
        // Per-page counter
        await setDoc(getPerPageCounterRef(), { count: increment(1) }, { merge: true });
        sessionStorage.setItem(sessionKey, '1');
    } catch (error) {
        // eslint-disable-next-line no-console
        console.warn('[pageview-counter] Increment failed:', error);
    }
}

async function readCountsAndRender() {
    try {
        const globalEl = document.getElementById('site-views');
        const pageEl = document.getElementById('page-views');

        if (!globalEl && !pageEl) return; // No UI to update

        const globalRef = getGlobalCounterRef();
        const pageRef = getPerPageCounterRef();

        if (globalEl) {
            onSnapshot(globalRef, snapshot => {
                const data = snapshot.data();
                const value = (data && typeof data.count === 'number') ? data.count : 0;
                globalEl.textContent = String(value);
            });
        }

        if (pageEl) {
            onSnapshot(pageRef, snapshot => {
                const data = snapshot.data();
                const value = (data && typeof data.count === 'number') ? data.count : 0;
                pageEl.textContent = String(value);
            });
        }
    } catch (error) {
        // eslint-disable-next-line no-console
        console.warn('[pageview-counter] Read/render failed:', error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    incrementCountersOncePerSession();
    readCountsAndRender();
});


