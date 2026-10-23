// Emotion Recognition Web - front-end
// Kamera dibuka di browser. Frame dianalisis oleh server (POST /api/analyze, DeepFace)
// atau langsung di browser (face-api) bila server tidak ada, mis. di GitHub Pages.

import * as browserEngine from "./browser-engine.js";

const EMOTIONS = ["happy", "sad", "angry", "surprise", "neutral", "disgust", "fear"];
const LABELS = {
    happy: "Senang", sad: "Sedih", angry: "Marah", surprise: "Terkejut",
    neutral: "Netral", disgust: "Jijik", fear: "Takut",
};
const EMOJI = {
    happy: "😄", sad: "😢", angry: "😠", surprise: "😲",
    neutral: "😐", disgust: "🤢", fear: "😨",
};
const TIMELINE_POINTS = 60;
const SEND_WIDTH = 640;
// Versi statis (GitHub Pages) ditandai saat build; lewati pengecekan server.
const STATIC_SITE = document.querySelector('meta[name="app-mode"]')?.content === "static";

const $ = (id) => document.getElementById(id);
const el = {
    stage: $("stage"), video: $("video"), overlay: $("overlay"), preview: $("uploadPreview"),
    placeholder: $("placeholder"), dropHint: $("dropHint"),
    startBtn: $("startBtn"), stopBtn: $("stopBtn"), snapBtn: $("snapBtn"),
    cameraSelect: $("cameraSelect"), fileInput: $("fileInput"), fullscreenBtn: $("fullscreenBtn"),
    fps: $("fpsLabel"), latency: $("latencyLabel"), faces: $("facesLabel"),
    moodEmoji: $("moodEmoji"), moodLabel: $("moodLabel"), moodConfidence: $("moodConfidence"),
    moodExtra: $("moodExtra"), moodTime: $("moodTime"), bars: $("emotionBars"), vibe: $("vibeMarker"),
    modelStatus: $("modelStatus"), sessionCount: $("sessionCount"),
    historyBody: $("historyBody"), historyFilter: $("historyFilter"), historySummary: $("historySummary"),
    toast: $("toast"), dialog: $("settingsDialog"),
};
const ctx = el.overlay.getContext("2d");

// ---------- Pengaturan (tersimpan di localStorage) ----------
const DEFAULT_SETTINGS = {
    interval: 400, smoothing: 0.5, engine: "server", detector: "opencv",
    browserDetector: "tinyFaceDetector", saveEvery: 5000,
    ageGender: false, mirror: true, voice: false, emojiOverlay: true,
};
const settings = { ...DEFAULT_SETTINGS, ...loadJSON("settings", {}) };

function loadJSON(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function saveSettings() {
    try { localStorage.setItem("settings", JSON.stringify(settings)); } catch { /* abaikan */ }
}

// ---------- State ----------
const state = {
    stream: null, running: false, inFlight: false, timer: null, serverAvailable: false,
    faces: [], frameW: 0, frameH: 0, smoothed: [],
    lastSave: 0, frames: 0, fpsTime: performance.now(),
    session: Object.fromEntries(EMOTIONS.map((e) => [e, 0])), samples: 0,
    lastDominant: null, stableCount: 0, announced: null,
};

const useBrowser = () => !state.serverAvailable || settings.engine === "browser";

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const color = (emotion) => cssVar(`--${emotion}`) || "#888";

// ---------- UI dasar ----------
function toast(msg, ms = 2600) {
    el.toast.textContent = msg;
    el.toast.classList.add("show");
    clearTimeout(toast.t);
    toast.t = setTimeout(() => el.toast.classList.remove("show"), ms);
}

function buildBars() {
    el.bars.replaceChildren(...EMOTIONS.map((e) => {
        const li = document.createElement("li");
        li.dataset.emotion = e;
        li.innerHTML = `<span>${EMOJI[e]} ${LABELS[e]}</span>
            <div class="track"><div class="fill" style="background:${color(e)}"></div></div>
            <span class="val">0%</span>`;
        return li;
    }));
}

function renderMood(face) {
    if (!face) {
        el.moodLabel.textContent = "Tidak ada wajah";
        el.moodLabel.style.color = "";
        el.moodConfidence.textContent = "Arahkan wajah ke kamera";
        el.moodExtra.textContent = "";
        return;
    }
    const { dominant, scores } = face;
    if (el.moodEmoji.textContent !== EMOJI[dominant]) {
        el.moodEmoji.textContent = EMOJI[dominant];
        el.moodEmoji.classList.remove("pop");
        void el.moodEmoji.offsetWidth;
        el.moodEmoji.classList.add("pop");
    }
    el.moodLabel.textContent = LABELS[dominant];
    el.moodLabel.style.color = color(dominant);
    el.moodConfidence.textContent = `Keyakinan ${scores[dominant].toFixed(1)}%`;
    const extra = [];
    if (face.age != null) extra.push(`🎂 ±${face.age} th`);
    if (face.gender) extra.push(face.gender === "male" ? "👨 Pria" : "👩 Wanita");
    el.moodExtra.textContent = extra.join("  ·  ");
    el.moodTime.textContent = new Date().toLocaleTimeString("id-ID");

    for (const li of el.bars.children) {
        const v = scores[li.dataset.emotion] ?? 0;
        li.querySelector(".fill").style.width = `${v}%`;
        li.querySelector(".val").textContent = `${v.toFixed(1)}%`;
        li.classList.toggle("active", li.dataset.emotion === dominant);
    }
    const positive = scores.happy + 0.5 * scores.surprise;
    const negative = scores.sad + scores.angry + scores.fear + scores.disgust;
    const vibe = Math.max(-1, Math.min(1, (positive - negative) / 100));
    el.vibe.style.left = `${((vibe + 1) / 2) * 100}%`;
}

// ---------- Grafik ----------
let timelineChart = null;
let distChart = null;

function initCharts() {
    if (!window.Chart) return;
    Chart.defaults.color = cssVar("--muted");
    Chart.defaults.borderColor = cssVar("--border");
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    timelineChart = new Chart($("timelineChart"), {
        type: "line",
        data: {
            labels: [],
            datasets: EMOTIONS.map((e) => ({
                label: LABELS[e], data: [], borderColor: color(e), backgroundColor: color(e),
                tension: 0.35, pointRadius: 0, borderWidth: 2,
            })),
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: "index", intersect: false },
            scales: { y: { min: 0, max: 100, ticks: { callback: (v) => `${v}%` } }, x: { ticks: { maxTicksLimit: 6 } } },
            plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } },
        },
    });
    distChart = new Chart($("distChart"), {
        type: "doughnut",
        data: {
            labels: EMOTIONS.map((e) => `${EMOJI[e]} ${LABELS[e]}`),
            datasets: [{ data: EMOTIONS.map(() => 0), backgroundColor: EMOTIONS.map(color), borderWidth: 0 }],
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: "62%",
            plugins: { legend: { position: "right", labels: { boxWidth: 10 } } },
        },
    });
}

function pushTimeline(face) {
    state.samples += 1;
    state.session[face.dominant] += 1;
    el.sessionCount.textContent = `${state.samples} sampel`;
    if (!timelineChart) return;
    const labels = timelineChart.data.labels;
    labels.push(new Date().toLocaleTimeString("id-ID"));
    timelineChart.data.datasets.forEach((ds, i) => ds.data.push(+face.scores[EMOTIONS[i]].toFixed(1)));
    if (labels.length > TIMELINE_POINTS) {
        labels.shift();
        timelineChart.data.datasets.forEach((ds) => ds.data.shift());
    }
    timelineChart.update("none");
    distChart.data.datasets[0].data = EMOTIONS.map((e) => state.session[e]);
    distChart.update();
}

function resetSession() {
    state.samples = 0;
    EMOTIONS.forEach((e) => (state.session[e] = 0));
    el.sessionCount.textContent = "0 sampel";
    if (timelineChart) {
        timelineChart.data.labels = [];
        timelineChart.data.datasets.forEach((ds) => (ds.data = []));
        timelineChart.update();
        distChart.data.datasets[0].data = EMOTIONS.map(() => 0);
        distChart.update();
    }
}

// ---------- Smoothing ----------
function smoothFaces(faces) {
    const a = settings.smoothing;
    const prev = faces.length === state.smoothed.length ? state.smoothed : [];
    state.smoothed = faces.map((f, i) => {
        const scores = {};
        for (const e of EMOTIONS) {
            const n = f.emotions[e] ?? 0;
            scores[e] = prev[i] ? prev[i].scores[e] * a + n * (1 - a) : n;
        }
        const dominant = EMOTIONS.reduce((best, e) => (scores[e] > scores[best] ? e : best), EMOTIONS[0]);
        return { ...f, scores, dominant };
    });
    return state.smoothed;
}

// ---------- Overlay ----------
function drawOverlay() {
    const { width: W, height: H } = el.overlay;
    ctx.clearRect(0, 0, W, H);
    if (!state.frameW) return;
    const s = W / state.frameW;
    // Piksel kanvas per piksel layar (object-fit: contain), agar label & garis
    // tetap berukuran sama di layar berapa pun resolusi gambarnya.
    const shown = Math.min(el.overlay.clientWidth / W, el.overlay.clientHeight / H);
    const px = shown > 0 ? 1 / shown : 1;
    state.smoothed.forEach((f, i) => {
        let { x, y, w, h } = f.region;
        x *= s; y *= s; w *= s; h *= s;
        if (settings.mirror && state.running) x = W - x - w;
        const c = color(f.dominant);
        ctx.lineWidth = 2.5 * px;
        ctx.strokeStyle = c;
        ctx.shadowColor = c;
        ctx.shadowBlur = 12 * px;
        roundRect(x, y, w, h, Math.min(w, h) * 0.12);
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Emoji dulu, label di atasnya agar teks tidak tertutup.
        if (settings.emojiOverlay) {
            const es = Math.max(24 * px, w * 0.35);
            const bob = Math.sin(performance.now() / 300 + i) * es * 0.08;
            ctx.font = `${es}px serif`;
            ctx.textBaseline = "alphabetic";
            ctx.fillText(EMOJI[f.dominant], x + w - es * 0.55, y + es * 0.35 + bob);
        }

        const label = `${i + 1}. ${LABELS[f.dominant]} ${f.scores[f.dominant].toFixed(0)}%`;
        const fs = 14 * px;
        ctx.font = `600 ${fs}px Inter, sans-serif`;
        const tw = ctx.measureText(label).width + fs;
        const lx = Math.max(0, Math.min(x, W - tw));
        const ly = y > fs * 1.8 ? y - fs * 1.7 : Math.min(y + h + 4 * px, H - fs * 1.5);
        ctx.fillStyle = c;
        roundRect(lx, ly, tw, fs * 1.5, fs * 0.4);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.textBaseline = "middle";
        ctx.fillText(label, lx + fs / 2, ly + fs * 0.76);
    });
}

function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, r);
    else ctx.rect(x, y, w, h);
}

function renderLoop() {
    if (!state.running) return;
    drawOverlay();
    state.frames += 1;
    const now = performance.now();
    if (now - state.fpsTime >= 1000) {
        el.fps.textContent = `${Math.round((state.frames * 1000) / (now - state.fpsTime))} fps`;
        state.frames = 0;
        state.fpsTime = now;
    }
    requestAnimationFrame(renderLoop);
}

// ---------- Analisis ----------
const captureCanvas = document.createElement("canvas");

async function sendForAnalysis(blob, { save, source }) {
    const form = new FormData();
    form.append("image", blob, "frame.jpg");
    form.append("detector", settings.detector);
    form.append("save", save ? "true" : "false");
    form.append("source", source);
    form.append("actions", "emotion");
    if (settings.ageGender) { form.append("actions", "age"); form.append("actions", "gender"); }
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
}

async function runAnalysis(input, { save, source, file }) {
    if (useBrowser()) {
        const data = await browserEngine.analyze(input, { detector: settings.browserDetector, ageGender: settings.ageGender });
        data.saved = save && data.faces.length ? browserEngine.localHistory.add(data.faces, source) : 0;
        return data;
    }
    const blob = file ?? await new Promise((r) => input.toBlob(r, "image/jpeg", 0.8));
    return sendForAnalysis(blob, { save, source });
}

function handleResult(data) {
    state.frameW = data.width;
    state.frameH = data.height;
    el.latency.textContent = `${Math.round(data.took_ms)} ms`;
    el.faces.textContent = `${data.faces.length} wajah`;
    const faces = smoothFaces(data.faces);
    const primary = faces.reduce((big, f) => (!big || f.region.w * f.region.h > big.region.w * big.region.h ? f : big), null);
    renderMood(primary);
    if (primary) {
        pushTimeline(primary);
        announce(primary.dominant);
    }
    if (data.saved) refreshHistorySoon();
}

function announce(emotion) {
    state.stableCount = emotion === state.lastDominant ? state.stableCount + 1 : 1;
    state.lastDominant = emotion;
    if (!settings.voice || !("speechSynthesis" in window)) return;
    if (state.stableCount === 3 && state.announced !== emotion) {
        state.announced = emotion;
        const u = new SpeechSynthesisUtterance(`Kamu terlihat ${LABELS[emotion].toLowerCase()}`);
        u.lang = "id-ID";
        speechSynthesis.cancel();
        speechSynthesis.speak(u);
    }
}

async function analyzeTick() {
    if (!state.running) return;
    const v = el.video;
    if (!state.inFlight && v.readyState >= 2 && v.videoWidth) {
        state.inFlight = true;
        const scale = Math.min(1, SEND_WIDTH / v.videoWidth);
        captureCanvas.width = Math.round(v.videoWidth * scale);
        captureCanvas.height = Math.round(v.videoHeight * scale);
        captureCanvas.getContext("2d").drawImage(v, 0, 0, captureCanvas.width, captureCanvas.height);
        const now = Date.now();
        const save = settings.saveEvery > 0 && now - state.lastSave >= settings.saveEvery;
        try {
            const data = await runAnalysis(captureCanvas, { save, source: "browser" });
            if (save && data.saved) state.lastSave = now;
            if (state.running) handleResult(data);
        } catch (err) {
            el.latency.textContent = "error";
            console.warn(err);
        } finally {
            state.inFlight = false;
        }
    }
    // Selalu ganti timer lama agar hanya ada satu loop analisis.
    clearTimeout(state.timer);
    if (state.running && !document.hidden) state.timer = setTimeout(analyzeTick, settings.interval);
}

// ---------- Kamera ----------
async function listCameras() {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
    const current = el.cameraSelect.value;
    el.cameraSelect.replaceChildren(...devices.map((d, i) => new Option(d.label || `Kamera ${i + 1}`, d.deviceId)));
    if (current) el.cameraSelect.value = current;
    el.cameraSelect.hidden = devices.length < 2;
}

async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
        toast("Browser tidak mendukung kamera (gunakan HTTPS atau localhost)");
        return;
    }
    stopCamera(true);
    try {
        const deviceId = el.cameraSelect.value;
        state.stream = await navigator.mediaDevices.getUserMedia({
            video: deviceId ? { deviceId: { exact: deviceId } } : { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
            audio: false,
        });
    } catch (err) {
        toast(`Kamera tidak bisa dibuka: ${err.message}`);
        return;
    }
    el.video.srcObject = state.stream;
    await el.video.play();
    el.overlay.width = el.video.videoWidth;
    el.overlay.height = el.video.videoHeight;
    el.preview.hidden = true;
    el.video.hidden = false;
    el.placeholder.hidden = true;
    state.running = true;
    state.smoothed = [];
    el.startBtn.disabled = true;
    el.stopBtn.disabled = false;
    el.snapBtn.disabled = false;
    listCameras();
    requestAnimationFrame(renderLoop);
    analyzeTick();
}

function stopCamera(silent = false) {
    state.running = false;
    clearTimeout(state.timer);
    state.stream?.getTracks().forEach((t) => t.stop());
    state.stream = null;
    el.video.srcObject = null;
    el.startBtn.disabled = false;
    el.stopBtn.disabled = true;
    if (!silent) {
        ctx.clearRect(0, 0, el.overlay.width, el.overlay.height);
        state.smoothed = [];
        el.placeholder.hidden = false;
        el.snapBtn.disabled = true;
        el.fps.textContent = "0 fps";
    }
}

// ---------- Unggah foto ----------
async function analyzeFile(file) {
    if (!file?.type.startsWith("image/")) {
        toast("File harus berupa gambar");
        return;
    }
    stopCamera(true);
    const url = URL.createObjectURL(file);
    el.preview.src = url;
    await el.preview.decode().catch(() => { });
    el.preview.hidden = false;
    el.video.hidden = true;
    el.placeholder.hidden = true;
    el.overlay.width = el.preview.naturalWidth;
    el.overlay.height = el.preview.naturalHeight;
    ctx.clearRect(0, 0, el.overlay.width, el.overlay.height);
    toast("Menganalisis foto…");
    try {
        state.smoothed = [];
        const saved = settings.saveEvery > 0;
        const data = await runAnalysis(el.preview, { save: saved, source: "upload", file });
        handleResult(data);
        drawOverlay();
        el.snapBtn.disabled = false;
        toast(data.faces.length ? `${data.faces.length} wajah terdeteksi` : "Tidak ada wajah terdeteksi");
    } catch (err) {
        toast(`Gagal: ${err.message}`);
    }
}

// ---------- Snapshot & layar penuh ----------
function snapshot() {
    const source = state.running ? el.video : el.preview;
    const c = document.createElement("canvas");
    c.width = el.overlay.width;
    c.height = el.overlay.height;
    const g = c.getContext("2d");
    if (state.running && settings.mirror) {
        g.translate(c.width, 0);
        g.scale(-1, 1);
    }
    g.drawImage(source, 0, 0, c.width, c.height);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.drawImage(el.overlay, 0, 0);
    const a = document.createElement("a");
    a.download = `emotion_${new Date().toISOString().replace(/[:.]/g, "-")}.png`;
    a.href = c.toDataURL("image/png");
    a.click();
    toast("📸 Snapshot disimpan");
}

function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else el.stage.requestFullscreen?.();
}

// ---------- Riwayat ----------
async function loadHistory() {
    const emotion = el.historyFilter.value;
    $("historyWhere").textContent = useBrowser() ? "Tersimpan di browser ini" : "Tersimpan di server";
    if (useBrowser()) {
        renderHistory(browserEngine.localHistory.recent(200, emotion));
        renderSummary(browserEngine.localHistory.stats());
        return;
    }
    try {
        const [rows, stats] = await Promise.all([
            fetch(`/api/history?limit=200${emotion ? `&emotion=${emotion}` : ""}`).then((r) => r.json()),
            fetch("/api/stats").then((r) => r.json()),
        ]);
        renderHistory(rows);
        renderSummary(stats);
    } catch (err) {
        console.warn(err);
    }
}

function refreshHistorySoon() {
    clearTimeout(refreshHistorySoon.t);
    refreshHistorySoon.t = setTimeout(loadHistory, 800);
}

function cell(text) {
    const td = document.createElement("td");
    td.textContent = text ?? "—";
    return td;
}

function renderHistory(rows) {
    if (!rows.length) {
        const tr = document.createElement("tr");
        const td = cell("Belum ada data. Nyalakan kamera untuk mulai merekam.");
        td.colSpan = 7;
        tr.append(td);
        el.historyBody.replaceChildren(tr);
        return;
    }
    el.historyBody.replaceChildren(...rows.map((r) => {
        const tr = document.createElement("tr");
        const emo = document.createElement("td");
        const tag = document.createElement("span");
        tag.className = "tag";
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.style.background = color(r.emotion);
        tag.append(dot, `${EMOJI[r.emotion] ?? ""} ${LABELS[r.emotion] ?? r.emotion}`);
        emo.append(tag);
        tr.append(
            cell(new Date(r.timestamp).toLocaleString("id-ID")),
            cell(r.source),
            cell(r.face_index + 1),
            emo,
            cell(`${Number(r.confidence).toFixed(1)}%`),
            cell(r.age),
            cell(r.gender === "male" ? "Pria" : r.gender === "female" ? "Wanita" : null),
        );
        return tr;
    }));
}

function renderSummary(stats) {
    const chips = [`Total ${stats.total} deteksi`];
    for (const [e, v] of Object.entries(stats.by_emotion)) {
        chips.push(`${EMOJI[e] ?? ""} ${LABELS[e] ?? e}: ${v.count} (${Math.round((v.count / stats.total) * 100)}%)`);
    }
    el.historySummary.replaceChildren(...chips.map((t) => {
        const s = document.createElement("span");
        s.className = "chip";
        s.textContent = t;
        return s;
    }));
}

async function clearHistory() {
    if (!confirm("Hapus semua riwayat deteksi?")) return;
    const res = useBrowser()
        ? { deleted: browserEngine.localHistory.clear() }
        : await fetch("/api/history", { method: "DELETE" }).then((r) => r.json());
    toast(`${res.deleted} entri dihapus`);
    loadHistory();
}

function exportHistory(e) {
    if (!useBrowser()) return; // mode server: link /api/history/export biasa
    e.preventDefault();
    const blob = new Blob([browserEngine.localHistory.exportCsv()], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `emotion_history_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// ---------- Status model ----------
function setStatus(kind, text, title = "") {
    el.modelStatus.className = `pill pill-${kind}`;
    el.modelStatus.textContent = `● ${text}`;
    el.modelStatus.title = title;
}

async function warmupBrowser() {
    setStatus("wait", "Memuat model AI…");
    try {
        await browserEngine.warmup(settings.browserDetector);
        setStatus("ok", "Model siap (browser)", "Analisis berjalan di perangkat ini; gambar tidak dikirim ke mana pun");
    } catch (err) {
        console.warn(err);
        setStatus("err", "Model error", String(err));
    }
}

async function pollHealth() {
    if (useBrowser()) return warmupBrowser();
    try {
        const h = await fetch("/api/health").then((r) => r.json());
        if (h.model_error) {
            el.modelStatus.className = "pill pill-err";
            el.modelStatus.textContent = "● Model error";
            el.modelStatus.title = h.model_error;
        } else if (h.model_ready) {
            el.modelStatus.className = "pill pill-ok";
            el.modelStatus.textContent = "● Model siap";
            return;
        }
    } catch {
        el.modelStatus.className = "pill pill-err";
        el.modelStatus.textContent = "● Server offline";
    }
    setTimeout(pollHealth, 3000);
}

// ---------- Pengaturan ----------
async function initSettings() {
    const bind = (id, key, { out, fmt, type = "value" } = {}) => {
        const input = $(id);
        input[type] = settings[key];
        const sync = () => out && ($(out).textContent = fmt(settings[key]));
        sync();
        input.addEventListener("input", () => {
            settings[key] = type === "checked" ? input.checked : input.type === "range" || key === "saveEvery" ? Number(input.value) : input.value;
            sync();
            saveSettings();
            if (key === "mirror") el.stage.classList.toggle("mirror", settings.mirror);
        });
    };
    let serverDetectors = ["opencv"];
    if (state.serverAvailable) {
        try {
            const cfg = await fetch("/api/config").then((r) => r.json());
            serverDetectors = cfg.detectors;
            if (!loadJSON("settings", {}).detector) settings.detector = cfg.default_detector;
        } catch { /* pakai default */ }
    }
    // Daftar detektor mengikuti mesin yang aktif.
    const detectorSelect = $("setDetector");
    const fillDetectors = () => {
        const browser = useBrowser();
        detectorSelect.replaceChildren(...(browser ? browserEngine.BROWSER_DETECTORS : serverDetectors).map((d) => new Option(d, d)));
        detectorSelect.value = browser ? settings.browserDetector : settings.detector;
    };
    fillDetectors();
    detectorSelect.addEventListener("input", () => {
        settings[useBrowser() ? "browserDetector" : "detector"] = detectorSelect.value;
        saveSettings();
    });
    $("engineField").hidden = !state.serverAvailable;
    const engineSelect = $("setEngine");
    engineSelect.value = settings.engine;
    engineSelect.addEventListener("input", () => {
        settings.engine = engineSelect.value;
        saveSettings();
        state.smoothed = [];
        fillDetectors();
        loadHistory();
        pollHealth();
    });
    bind("setInterval", "interval", { out: "intervalOut", fmt: (v) => `${v} ms` });
    bind("setSmoothing", "smoothing", { out: "smoothOut", fmt: (v) => v.toFixed(2) });
    bind("setSaveEvery", "saveEvery");
    bind("setAgeGender", "ageGender", { type: "checked" });
    bind("setMirror", "mirror", { type: "checked" });
    bind("setVoice", "voice", { type: "checked" });
    bind("setEmojiOverlay", "emojiOverlay", { type: "checked" });
    el.stage.classList.toggle("mirror", settings.mirror);
}

function toggleTheme() {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch { /* abaikan */ }
    if (window.Chart) {
        Chart.defaults.color = cssVar("--muted");
        Chart.defaults.borderColor = cssVar("--border");
        timelineChart?.update();
        distChart?.update();
    }
}

// ---------- Event ----------
function bindEvents() {
    el.startBtn.addEventListener("click", startCamera);
    el.stopBtn.addEventListener("click", () => stopCamera());
    el.snapBtn.addEventListener("click", snapshot);
    el.fullscreenBtn.addEventListener("click", toggleFullscreen);
    el.cameraSelect.addEventListener("change", () => state.running && startCamera());
    el.fileInput.addEventListener("change", (e) => analyzeFile(e.target.files[0]));
    $("themeBtn").addEventListener("click", toggleTheme);
    $("settingsBtn").addEventListener("click", () => el.dialog.showModal());
    $("resetSessionBtn").addEventListener("click", resetSession);
    $("refreshHistoryBtn").addEventListener("click", loadHistory);
    $("clearHistoryBtn").addEventListener("click", clearHistory);
    el.historyFilter.addEventListener("change", loadHistory);
    $("exportBtn").addEventListener("click", exportHistory);

    ["dragenter", "dragover"].forEach((t) => el.stage.addEventListener(t, (e) => {
        e.preventDefault();
        el.stage.classList.add("dragging");
        el.dropHint.hidden = false;
    }));
    ["dragleave", "drop"].forEach((t) => el.stage.addEventListener(t, (e) => {
        e.preventDefault();
        el.stage.classList.remove("dragging");
        el.dropHint.hidden = true;
    }));
    el.stage.addEventListener("drop", (e) => analyzeFile(e.dataTransfer.files[0]));
    document.addEventListener("paste", (e) => {
        const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
        if (item) analyzeFile(item.getAsFile());
    });

    document.addEventListener("keydown", (e) => {
        if (e.target.closest("input, select, textarea") || e.ctrlKey || e.metaKey || el.dialog.open) return;
        const k = e.key.toLowerCase();
        if (k === " ") { e.preventDefault(); state.running ? stopCamera() : startCamera(); }
        else if (k === "s" && !el.snapBtn.disabled) snapshot();
        else if (k === "f") toggleFullscreen();
        else if (k === "t") toggleTheme();
        else if (k === ",") el.dialog.showModal();
    });
    document.addEventListener("visibilitychange", () => {
        // Hemat CPU: hentikan analisis saat tab tidak terlihat.
        if (document.hidden) clearTimeout(state.timer);
        else if (state.running) analyzeTick();
    });
    navigator.mediaDevices?.addEventListener?.("devicechange", listCameras);
    // Foto unggahan hanya digambar sekali; gambar ulang saat ukuran tampilan berubah.
    window.addEventListener("resize", () => !state.running && drawOverlay());
}

// ---------- Init ----------
async function detectServer() {
    if (STATIC_SITE) return false;
    try {
        const res = await fetch("/api/health");
        return res.ok && (await res.json()).status === "ok";
    } catch {
        return false;
    }
}

async function init() {
    buildBars();
    el.historyFilter.append(...EMOTIONS.map((e) => new Option(`${EMOJI[e]} ${LABELS[e]}`, e)));
    // Sebelum await: event "load" bisa terlewat selama pengecekan server.
    if (window.Chart) initCharts();
    else window.addEventListener("load", initCharts, { once: true });
    state.serverAvailable = await detectServer();
    await initSettings();
    bindEvents();
    listCameras();
    loadHistory();
    pollHealth();
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => { });
}

init();
