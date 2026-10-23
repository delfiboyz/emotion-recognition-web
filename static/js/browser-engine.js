// Mesin analisis di browser (face-api / TensorFlow.js) + riwayat di localStorage.
// Dipakai saat tidak ada server Python, mis. di GitHub Pages.

const MODEL_URL = new URL("../vendor/face-api/models/", import.meta.url).href;
export const BROWSER_DETECTORS = ["tinyFaceDetector", "ssdMobilenetv1"];

// Nama ekspresi face-api -> nama emosi aplikasi (sama dengan DeepFace).
const EXPRESSION_MAP = {
    happy: "happy", sad: "sad", angry: "angry", surprised: "surprise",
    neutral: "neutral", disgusted: "disgust", fearful: "fear",
};

let faceapi = null;
let loading = null;
const loaded = new Set();

async function loadLibrary() {
    if (!faceapi) {
        faceapi = await import("../vendor/face-api/face-api.esm.js");
        try {
            await faceapi.tf.setBackend("webgl");
        } catch {
            await faceapi.tf.setBackend("cpu");
        }
        await faceapi.tf.ready();
    }
    return faceapi;
}

async function ensureModels(detector, ageGender) {
    const api = await loadLibrary();
    const needed = [detector, "faceExpressionNet", ...(ageGender ? ["ageGenderNet"] : [])];
    for (const name of needed) {
        if (!loaded.has(name)) {
            await api.nets[name].loadFromUri(MODEL_URL);
            loaded.add(name);
        }
    }
    return api;
}

/** Muat library & model default lebih awal. */
export function warmup(detector = "tinyFaceDetector") {
    loading ??= ensureModels(detector, false);
    return loading;
}

/** Analisis canvas/img; hasilnya berformat sama dengan POST /api/analyze. */
export async function analyze(input, { detector = "tinyFaceDetector", ageGender = false } = {}) {
    if (!BROWSER_DETECTORS.includes(detector)) detector = "tinyFaceDetector";
    const api = await ensureModels(detector, ageGender);
    const start = performance.now();
    const options = detector === "ssdMobilenetv1"
        ? new api.SsdMobilenetv1Options({ minConfidence: 0.5 })
        : new api.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.5 });
    let task = api.detectAllFaces(input, options).withFaceExpressions();
    if (ageGender) task = task.withAgeAndGender();
    const results = await task;
    const width = input.naturalWidth || input.videoWidth || input.width;
    const height = input.naturalHeight || input.videoHeight || input.height;

    const faces = results.map((r) => {
        const emotions = {};
        for (const [k, v] of Object.entries(r.expressions)) {
            if (EXPRESSION_MAP[k]) emotions[EXPRESSION_MAP[k]] = Math.round(v * 10000) / 100;
        }
        const dominant = Object.keys(emotions).reduce((a, b) => (emotions[b] > emotions[a] ? b : a));
        const box = r.detection.box;
        const face = {
            dominant_emotion: dominant,
            confidence: emotions[dominant],
            emotions,
            face_confidence: Math.round(r.detection.score * 1000) / 1000,
            region: { x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) },
        };
        if (ageGender) {
            face.age = Math.round(r.age);
            face.gender = r.gender;
        }
        return face;
    }).sort((a, b) => a.region.x - b.region.x);

    return {
        faces, width, height, detector,
        took_ms: Math.round((performance.now() - start) * 10) / 10,
        timestamp: new Date().toISOString(),
    };
}

// ---------- Riwayat lokal (meniru /api/history & /api/stats) ----------
const STORE_KEY = "emotion-history";
const MAX_ROWS = 5000;
const CSV_COLUMNS = ["id", "timestamp", "source", "face_index", "emotion", "confidence", "x", "y", "w", "h", "age", "gender"];

function readRows() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch { return []; }
}

function writeRows(rows) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(rows.slice(-MAX_ROWS))); } catch { /* penyimpanan penuh/diblokir */ }
}

export const localHistory = {
    add(faces, source = "browser") {
        const rows = readRows();
        let id = rows.length ? rows[rows.length - 1].id : 0;
        const timestamp = new Date().toISOString();
        faces.forEach((f, i) => rows.push({
            id: ++id, timestamp, source, face_index: i, emotion: f.dominant_emotion,
            confidence: f.confidence, scores: f.emotions, ...f.region,
            age: f.age ?? null, gender: f.gender ?? null,
        }));
        writeRows(rows);
        return faces.length;
    },

    recent(limit = 100, emotion = "") {
        return readRows().filter((r) => !emotion || r.emotion === emotion).reverse().slice(0, limit);
    },

    stats() {
        const rows = readRows();
        const by = {};
        for (const r of rows) {
            by[r.emotion] ??= { count: 0, sum: 0 };
            by[r.emotion].count += 1;
            by[r.emotion].sum += r.confidence;
        }
        const by_emotion = Object.fromEntries(Object.entries(by)
            .sort((a, b) => b[1].count - a[1].count)
            .map(([e, v]) => [e, { count: v.count, avg_confidence: Math.round((v.sum / v.count) * 100) / 100 }]));
        return { total: rows.length, first: rows[0]?.timestamp ?? null, last: rows.at(-1)?.timestamp ?? null, by_emotion };
    },

    clear() {
        const n = readRows().length;
        writeRows([]);
        return n;
    },

    exportCsv() {
        const esc = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
        const lines = [CSV_COLUMNS.join(","), ...readRows().map((r) => CSV_COLUMNS.map((c) => esc(r[c])).join(","))];
        return lines.join("\n") + "\n";
    },
};
