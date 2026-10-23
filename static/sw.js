// Service worker sederhana: cache aset statis agar UI cepat dibuka & bisa di-install (PWA).
const CACHE = "emotion-web-v2";
// Path relatif terhadap sw.js agar jalan di root (Flask) maupun sub-path (GitHub Pages).
const ASSETS = [
    "./", "static/css/app.css", "static/js/app.js", "static/js/browser-engine.js",
    "static/vendor/chart.umd.js", "static/icon.svg", "static/manifest.webmanifest",
];

self.addEventListener("install", (e) => {
    e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
    e.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
            .then(() => self.clients.claim()),
    );
});

self.addEventListener("fetch", (e) => {
    const url = new URL(e.request.url);
    // API, stream & request non-GET selalu ke jaringan.
    if (e.request.method !== "GET" || url.origin !== location.origin || /\/(api\/|stream$)/.test(url.pathname)) return;
    // Network-first, jatuh ke cache saat offline.
    e.respondWith(
        fetch(e.request)
            .then((res) => {
                const copy = res.clone();
                caches.open(CACHE).then((c) => c.put(e.request, copy));
                return res;
            })
            .catch(() => caches.match(e.request)),
    );
});
