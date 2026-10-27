/* Video Bulk Remixer — giao diện Alpine.js (không dùng CDN, không inline script). */
"use strict";

const EFFECTS = [
  { id: "crossfade", label: "Mờ dần (Crossfade)", icon: "🌊" },
  { id: "dissolve", label: "Hoà tan (Dissolve)", icon: "✨" },
  { id: "fade_black", label: "Qua đen", icon: "⬛" },
  { id: "fade_white", label: "Qua trắng", icon: "⬜" },
  { id: "slide_lr", label: "Trượt sang phải", icon: "➡️" },
  { id: "slide_rl", label: "Trượt sang trái", icon: "⬅️" },
  { id: "slide_up", label: "Trượt lên", icon: "⬆️" },
  { id: "slide_down", label: "Trượt xuống", icon: "⬇️" },
  { id: "wipe_lr", label: "Quét sang phải", icon: "▶️" },
  { id: "wipe_rl", label: "Quét sang trái", icon: "◀️" },
  { id: "wipe_tb", label: "Quét xuống", icon: "🔽" },
  { id: "wipe_bt", label: "Quét lên", icon: "🔼" },
  { id: "circle_open", label: "Nở tròn", icon: "⭕" },
  { id: "zoom_in", label: "Phóng to", icon: "🔍" },
];
const LANGS = ["ar", "bn", "da", "de", "en", "es", "fi", "fr", "hi", "id", "is", "it", "ja", "km", "ko", "lo", "mr", "ms", "my", "nl", "no", "pl", "pt", "ru", "sv", "th", "tl", "tr", "ur", "vi", "zh"];
const GEOS = ["WW", "VN", "US", "BR", "JP", "KR", "TH", "ID", "DE", "FR", "ES", "MX", "IN", "PH", "TW"];
const SEG_LABEL = { intro: "Intro", custom: "Tuỳ chọn", outro: "Outro" };

function todayDdmmyy() {
  const d = new Date();
  return String(d.getDate()).padStart(2, "0") + String(d.getMonth() + 1).padStart(2, "0") + String(d.getFullYear()).slice(-2);
}

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(url, opts);
  let data = null;
  try { data = await r.json(); } catch (e) { data = null; }
  if (!r.ok) {
    const msg = data && data.detail ? (Array.isArray(data.detail) ? "Dữ liệu chưa đúng" : data.detail) : "Có lỗi, thử lại sau";
    throw new Error(msg);
  }
  return data;
}

function app() {
  return {
    theme: "auto",
    todayStr: todayDdmmyy(),
    geos: GEOS,
    languageOptions: LANGS,
    effects: EFFECTS,

    form: { input_dir: "", output_dir: "", voice_dir: "", music_dir: "" },
    videos: [],
    scanError: "",
    preview: null,
    now: 0,

    seg: {
      intro: { enabled: false, end: 5, source_dir: "", files: [], short: [] },
      custom: { enabled: false, start: 10, end: 20, source_dir: "", files: [], short: [] },
      outro: { enabled: false, start: 25, source_dir: "", files: [], short: [] },
    },
    focused: null,

    parts: [],
    jointLabels: [],
    transitions: {},
    fxDuration: "0.5",
    dragFx: null,
    dragOver: null,
    openedJoint: null,

    tab: "source",
    voiceFiles: [],
    musicFiles: [],
    voiceNote: "",
    musicNote: "",
    useVoice: true,
    useMusic: true,
    keepOriginal: false,
    volumes: { music: 100, voice: 100, original: 100 },
    duckMusic: false,
    tiltFor: null,
    cornerDrag: null,
    textLangs: ["vi", "en"],
    newLang: "",
    textRegions: [],
    frameAt: 1,
    frameUrl: "",
    frameInfo: "",
    frameW: 0,
    frameH: 0,
    frameLang: "",
    frameRenderUrl: "",
    renderSeq: 0,
    drawing: false,
    drawFrom: null,
    drawRect: null,

    naming: { appname: "", concept: "", geo: "WW", date: "" },
    previewNames: [],

    job: { status: "idle", done: 0, total: 0, current: "", ok: 0, outputs: [], failed: [], error: "", output_dir: "" },
    outPreview: null,
    lastPreview: false,
    update: { has: false, latest: "", busy: false, done: "", notes: "" },
    textPreviewUrl: "",
    textPreviewInfo: "",
    textPreviewBusy: false,
    shortWarnings: [],
    shortAction: "trim",
    shownShortFor: "",
    busy: false,
    message: "",
    pollTimer: null,

    /* ---------- tính toán ---------- */
    get overlapError() {
      const segs = this.enabledSegments().map(s => ({ key: s.type, start: s.start, end: s.end }));
      segs.sort((a, b) => a.start - b.start);
      for (let i = 0; i < segs.length - 1; i++) {
        if (segs[i].end > segs[i + 1].start) {
          return "⚠️ Đoạn " + SEG_LABEL[segs[i].key] + " chồng lên đoạn " + SEG_LABEL[segs[i + 1].key] + ". Hãy sửa giây để các đoạn không đè nhau.";
        }
      }
      return "";
    },
    get activeSegments() {
      return ["intro", "custom", "outro"].filter(k => this.seg[k].enabled).map(k => ({ key: k, label: SEG_LABEL[k] }));
    },
    get firstVideo() { return this.videos[0] || null; },
    get referenceDuration() {
      return (this.preview && this.preview.duration) || (this.firstVideo && this.firstVideo.duration) || 0;
    },
    get appliedVoice() { return this.useVoice ? this.voiceFiles : []; },
    get appliedMusic() { return this.useMusic ? this.musicFiles : []; },
    get hasAudioWork() { return this.appliedVoice.length > 0 || this.appliedMusic.length > 0 || this.keepOriginal; },
    get planLanguages() {
      const langs = new Set(this.appliedVoice.map(a => a.lang).filter(Boolean));
      for (const r of this.textRegions) {
        for (const l of this.textLangs) if ((r.texts[l] || "").trim()) langs.add(l);
      }
      return [...langs].sort();
    },
    get planCount() {
      const langs = this.planLanguages;
      const music = Math.max(1, this.appliedMusic.length);
      if (langs.length === 0) return music;
      let n = 0;
      for (const l of langs) {
        n += Math.max(1, this.appliedVoice.filter(a => a.lang === l).length) * music;
      }
      return n;
    },
    get sourceCombos() {
      let n = 1;
      for (const k of this.activeSegments.map(s => s.key)) n *= this.seg[k].files.length;
      return this.activeSegments.length ? n : 1;
    },
    get estimate() {
      if (this.videos.length === 0) return 0;
      return this.videos.length * this.sourceCombos * this.planCount;
    },
    get runReasons() {
      const r = [];
      if (!this.form.input_dir) r.push("Chọn thư mục video gốc (ô 1)");
      else if (this.videos.length === 0) r.push("Thư mục video gốc chưa có video");
      if (!this.form.output_dir) r.push("Chọn thư mục Output (ô 4)");
      if (this.form.output_dir && this.form.output_dir === this.form.input_dir) r.push("Output không được trùng thư mục video gốc");
      if (this.overlapError) r.push("Các đoạn đang chồng lên nhau");
      if (this.appliedVoice.some(a => !a.lang)) r.push("Có voice chưa chọn ngôn ngữ (tab Audio)");
      if (this.activeSegments.length === 0 && !this.hasAudioWork && !this.hasTextWork) {
        r.push("Chưa chọn việc gì để thay (đoạn, audio hoặc text)");
      }
      for (const s of this.activeSegments) {
        if (this.seg[s.key].files.length === 0) r.push("Source " + s.label + " chưa có video");
      }
      return r;
    },
    get hasTextWork() {
      return this.textRegions.length > 0 && this.textRegions.some(r => this.textLangs.some(l => (r.texts[l] || "").trim()));
    },
    get canRun() { return this.runReasons.length === 0; },
    get progressPct() { return this.job.total ? Math.round(this.job.done / this.job.total * 100) : 0; },
    get statusTitle() {
      return { running: "⏳ Đang xử lý…", done: "✅ Hoàn thành!", stopped: "⏹ Đã dừng", error: "❌ Dừng do lỗi" }[this.job.status] || "";
    },
    get seekValue() {
      if (!this.focused) return null;
      const [k, f] = this.focused.split(".");
      return this.seg[k] ? this.seg[k][f] : null;
    },

    enabledSegments() {
      const out = [];
      if (this.seg.intro.enabled) out.push({ type: "intro", start: 0, end: Number(this.seg.intro.end) || 0 });
      if (this.seg.custom.enabled) out.push({ type: "custom", start: Number(this.seg.custom.start) || 0, end: Number(this.seg.custom.end) || 0 });
      if (this.seg.outro.enabled) out.push({ type: "outro", start: Number(this.seg.outro.start) || 0, end: null });
      return out;
    },
    segmentPayload() {
      return this.enabledSegments().map(s => {
        const src = this.seg[s.type].source_dir || "";
        return { type: s.type, start: s.start, end: s.end, source_dir: src };
      });
    },

    /* ---------- khởi tạo ---------- */
    init() {
      this.checkUpdate();
      this.$watch("form.input_dir", (v) => { if (v) this.scanVideos(v); else this.videos = []; });
      this.$watch("form.voice_dir", (v) => { if (v) this.scanAudio("voice", v); });
      this.$watch("form.music_dir", (v) => { if (v) this.scanAudio("music", v); });
      this.$watch(() => this.segSignature(), () => this.refreshTimeline());
      this.$watch(() => this.referenceDuration, () => this.refreshTimeline());
      this.$watch(() => this.seekValue, (v) => this.seekTo(v));
      for (const k of ["intro", "custom", "outro"]) {
        this.$watch(() => this.seg[k].source_dir, () => this.scanSource(k));
      }
      this.$watch(() => JSON.stringify([this.naming, this.planLanguages]), () => this.refreshNames());
      this.refreshNames();
      this.pollTimer = setInterval(() => this.refreshJob(), 700);
      this.refreshJob();
    },
    segSignature() {
      return JSON.stringify([this.seg.intro.enabled, this.seg.intro.end, this.seg.custom.enabled, this.seg.custom.start,
        this.seg.custom.end, this.seg.outro.enabled, this.seg.outro.start]);
    },

    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", this.theme);
    },

    /* ---------- chọn thư mục / file ---------- */
    async pick(field) {
      try {
        const d = await api("GET", "/api/fs/pick");
        if (d.path) this.form[field] = d.path;
        else this.message = "Không mở được hộp chọn thư mục. Hãy dán đường dẫn vào ô bên cạnh.";
      } catch (e) {
        this.message = e.message;
      }
    },
    async pickSource(key) {
      try {
        const d = await api("GET", "/api/fs/pick");
        if (d.path) { this.seg[key].source_dir = d.path; await this.scanSource(key); }
        else this.message = "Không mở được hộp chọn. Hãy dán đường dẫn vào ô.";
      } catch (e) { this.message = e.message; }
    },
    async scanVideos(dir) {
      this.scanError = "";
      try {
        const d = await api("GET", "/api/fs/list?kind=video&dir=" + encodeURIComponent(dir));
        if (d.error) this.scanError = d.error;
        this.videos = d.files || [];
      } catch (e) { this.videos = []; this.scanError = e.message; }
    },
    async scanSource(key) {
      const dir = this.seg[key].source_dir;
      if (!dir) { this.seg[key].files = []; return; }
      try {
        const d = await api("GET", "/api/fs/list?kind=video&dir=" + encodeURIComponent(dir));
        this.seg[key].files = (d.files || []).filter(f => f.duration);
        this.seg[key].short = [];
      } catch (e) { this.seg[key].files = []; }
    },
    async scanAudio(kind, dir) {
      const key = kind === "voice" ? "voice" : "music";
      try {
        const d = await api("GET", "/api/fs/list?kind=audio&dir=" + encodeURIComponent(dir));
        const files = (d.files || []).map(f => ({
          name: f.name, path: f.path, lang: kind === "voice" ? this.guessLang(f.name) : "",
        }));
        this[key + "Files"] = files;
        this[key + "Note"] = d.error || (files.length === 0
          ? "Không thấy file audio trong thư mục này (mp3, wav, m4a, aac, ogg, flac, opus, wma, aif)."
          : "");
      } catch (e) { this[key + "Files"] = []; this[key + "Note"] = e.message; }
    },
    guessLang(name) {
      const stem = name.replace(/\.[^.]+$/, "").toLowerCase();
      const parts = stem.replace(/-/g, "_").split("_");
      for (let i = parts.length - 1; i >= 0; i--) if (LANGS.includes(parts[i])) return parts[i];
      return "";
    },
    mediaUrl(path) { return "/api/fs/media?path=" + encodeURIComponent(path); },
    thumbUrl(v) { return "/api/fs/frame?w=160&t=1&path=" + encodeURIComponent(v.path); },

    /* ---------- cập nhật ---------- */
    async checkUpdate() {
      try {
        const d = await api("GET", "/api/update/check");
        this.update.has = !!d.has_update;
        this.update.latest = d.latest || "";
        this.update.notes = d.notes_url || "";
      } catch (e) { /* không kiểm tra được thì bỏ qua, không làm phiền người dùng */ }
    },
    async applyUpdate() {
      if (this.update.busy) return;
      this.update.busy = true;
      try {
        const d = await api("POST", "/api/update/apply");
        this.update.has = false;
        this.update.done = d.message || "Đã cập nhật. Hãy mở lại app.";
      } catch (e) {
        this.message = e.message || "Không cập nhật được";
      } finally {
        this.update.busy = false;
      }
    },

    /* ---------- xem trước video gốc ---------- */
    openPreview(v) {
      if (!v.duration) { this.message = v.error || "Không đọc được video này"; return; }
      this.preview = v;
      this.now = 0;
      this.clearTextPreview();
      this.$nextTick(() => {
        const p = document.getElementById("player");
        p.src = this.mediaUrl(v.path);
        p.load();
      });
    },
    /* Xem trước có text đã thay: dựng một đoạn ngắn đúng cách chạy thật rồi phát trong trình phát. */
    clearTextPreview() {
      if (this.textPreviewUrl) URL.revokeObjectURL(this.textPreviewUrl);
      this.textPreviewUrl = "";
      this.textPreviewInfo = "";
    },
    showRawPreview() {
      if (!this.preview) return;
      this.clearTextPreview();
      const p = document.getElementById("player");
      if (p) { p.src = this.mediaUrl(this.preview.path); p.load(); }
    },
    async previewWithText() {
      const src = this.preview;
      const lang = this.frameLang || this.textLangs[0] || "";
      if (!src) { this.message = "Hãy chọn một video để xem trước."; return; }
      if (!lang) { this.message = "Chưa có ngôn ngữ để xem text."; return; }
      const regions = this.regionDtos(lang);
      if (regions.length === 0) { this.message = "Chưa điền text mới cho ngôn ngữ " + lang.toUpperCase() + "."; return; }
      const t = Math.max(0, Number(this.frameAt) || 0);
      this.textPreviewBusy = true;
      this.textPreviewInfo = "Đang dựng đoạn xem trước (khoảng 5–10 giây)…";
      try {
        const r = await fetch("/api/fs/clip-text", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: src.path, t, duration: 8, w: 1280, language: lang, regions }),
        });
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          throw new Error(d.detail || "Không dựng được đoạn xem trước");
        }
        const blob = await r.blob();
        this.clearTextPreview();
        this.textPreviewUrl = URL.createObjectURL(blob);
        const p = document.getElementById("player");
        p.src = this.textPreviewUrl;
        p.load();
        this.textPreviewInfo = "Đang xem có text " + lang.toUpperCase() + " (từ giây " + t.toFixed(1) + ", 8 giây)";
      } catch (e) {
        this.textPreviewInfo = e.message;
      } finally {
        this.textPreviewBusy = false;
      }
    },
    setFocusedFromNow() {
      if (!this.focused) { this.message = "Hãy bấm vào một ô giây ở ô 2 trước."; return; }
      const [k, f] = this.focused.split(".");
      this.seg[k][f] = Math.round(this.now * 10) / 10;
      this.message = "";
    },
    seekTo(sec) {
      const p = document.getElementById("player");
      if (!p || !p.src || sec === null || sec === undefined || Number.isNaN(Number(sec))) return;
      try { p.currentTime = Math.max(0, Number(sec)); } catch (e) { /* metadata chưa sẵn sàng */ }
    },

    /* ---------- timeline & hiệu ứng ---------- */
    async refreshTimeline() {
      const dur = this.referenceDuration;
      if (!dur || this.enabledSegments().length === 0) { this.parts = []; this.jointLabels = []; return; }
      try {
        const d = await api("POST", "/api/jobs/timeline", { segments: this.segmentPayload(), duration: dur });
        if (d.ok) { this.parts = d.parts; this.jointLabels = d.joints; this.message = ""; }
        else { this.parts = []; this.jointLabels = []; this.message = d.error; }
      } catch (e) { this.message = e.message; }
    },
    transitionFor(i) {
      if (i === null || i === undefined) return { type: "none", duration: 0.5 };
      return this.transitions[String(i)] || { type: "none", duration: 0.5 };
    },
    setTransition(i, type) {
      if (type === "none") { delete this.transitions[String(i)]; return; }
      this.transitions[String(i)] = { type, duration: parseFloat(this.fxDuration) };
    },
    setJointDuration(i, value) {
      const t = this.transitionFor(i);
      if (t.type !== "none") this.transitions[String(i)] = { type: t.type, duration: parseFloat(value) };
    },
    dropEffect(i) {
      if (this.dragFx) this.setTransition(i, this.dragFx);
      this.dragFx = null;
      this.dragOver = null;
    },
    applyDefault(id) {
      if (this.parts.length < 2) { this.message = "Cần ít nhất 2 đoạn (ví dụ Intro + Gốc) để đặt hiệu ứng."; return; }
      for (let i = 0; i < this.parts.length - 1; i++) this.setTransition(i, id);
    },
    openJoint(i) { this.openedJoint = i; this.$nextTick(() => this.drawAnim(0)); },
    effectLabel(type) {
      const e = EFFECTS.find(x => x.id === type);
      return e ? e.label : "";
    },
    previewAnim() {
      const type = this.transitionFor(this.openedJoint).type;
      if (type === "none") return;
      const start = performance.now();
      const step = (t) => {
        const p = Math.min(1, (t - start) / 2500);
        this.drawAnim(p, type);
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    },
    drawAnim(p, type) {
      const c = this.$refs.anim;
      if (!c) return;
      const g = c.getContext("2d");
      const W = c.width, H = c.height;
      const A = "#5B5BF0", B = "#F5A623";
      g.fillStyle = A; g.fillRect(0, 0, W, H);
      g.fillStyle = B;
      const q = (p * 1.2) % 1;
      const k = type || "crossfade";
      if (k === "crossfade") { g.globalAlpha = Math.min(1, q); g.fillRect(0, 0, W, H); g.globalAlpha = 1; }
      else if (k === "fade_black") { g.fillStyle = "#000"; g.globalAlpha = Math.abs(Math.sin(q * Math.PI)); g.fillRect(0, 0, W, H); g.globalAlpha = 1; }
      else if (k === "fade_white") { g.fillStyle = "#fff"; g.globalAlpha = Math.abs(Math.sin(q * Math.PI)); g.fillRect(0, 0, W, H); g.globalAlpha = 1; }
      else if (k === "slide_lr") { g.fillRect(-W + q * W, 0, W, H); }
      else if (k === "slide_rl") { g.fillRect(W - q * W, 0, W, H); }
      else if (k === "wipe_tb") { g.fillRect(0, 0, W, q * H); }
      else if (k === "wipe_bt") { g.fillRect(0, H - q * H, W, q * H); }
      else if (k === "dissolve") { g.globalAlpha = Math.min(1, q); g.fillRect(0, 0, W, H); g.globalAlpha = 1; }
      else if (k === "slide_up") { g.fillRect(0, H - q * H, W, H); }
      else if (k === "slide_down") { g.fillRect(0, -H + q * H, W, H); }
      else if (k === "wipe_lr") { g.fillRect(0, 0, q * W, H); }
      else if (k === "wipe_rl") { g.fillRect(W - q * W, 0, q * W, H); }
      else if (k === "circle_open") { g.beginPath(); g.arc(W / 2, H / 2, q * Math.hypot(W, H) / 2, 0, Math.PI * 2); g.fill(); }
      else if (k === "zoom_in") { const s = 1 + q; g.fillRect(W / 2 - W * s / 2, H / 2 - H * s / 2, W * s, H * s); }
      g.fillStyle = "#fff"; g.font = "600 14px system-ui"; g.fillText("Xem trước hiệu ứng", 10, 22);
    },

    /* ---------- khung hình để vẽ vùng text ---------- */
    async loadFrame() {
      const src = this.preview || this.firstVideo;
      if (!src) return;
      this.frameInfo = "Đang lấy khung hình…";
      try {
        const r = await fetch("/api/fs/frame?t=" + encodeURIComponent(this.frameAt || 0) + "&w=1280&path=" + encodeURIComponent(src.path));
        if (!r.ok) throw new Error("Không lấy được khung hình tại giây này");
        this.frameW = parseInt(r.headers.get("X-Video-Width"), 10) || 0;
        this.frameH = parseInt(r.headers.get("X-Video-Height"), 10) || 0;
        const blob = await r.blob();
        if (this.frameUrl) URL.revokeObjectURL(this.frameUrl);
        this.frameUrl = URL.createObjectURL(blob);
        this.frameInfo = "Video " + this.frameW + "×" + this.frameH + " px";
        this.frameRenderUrl = "";
        this.renderFrame();
      } catch (e) { this.frameInfo = e.message; }
    },
    /* Vẽ text mới lên khung hình xem trước (cùng cách với lúc chạy thật). */
    async renderFrame() {
      const src = this.preview || this.firstVideo;
      const lang = this.frameLang || this.textLangs[0] || "";
      const seq = ++this.renderSeq;
      const regions = this.regionDtos(lang);
      if (!src || !this.frameUrl || !lang || regions.length === 0) {
        this.frameRenderUrl = "";
        return;
      }
      try {
        const r = await fetch("/api/fs/frame-text", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: src.path, t: this.frameAt || 0, w: 1280, language: lang, regions }),
        });
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          throw new Error(d.detail || "Không xem trước được text");
        }
        const blob = await r.blob();
        if (seq !== this.renderSeq) return;
        if (this.frameRenderUrl) URL.revokeObjectURL(this.frameRenderUrl);
        this.frameRenderUrl = URL.createObjectURL(blob);
      } catch (e) { if (seq === this.renderSeq) this.frameInfo = e.message; }
    },
    boxStart(e) {
      const img = this.$refs.frame;
      if (!img) return;
      const b = img.getBoundingClientRect();
      const x = Math.min(Math.max(e.clientX - b.left, 0), b.width);
      const y = Math.min(Math.max(e.clientY - b.top, 0), b.height);
      this.drawFrom = { x, y };
      this.drawRect = { x, y, w: 0, h: 0 };
      this.drawing = true;
    },
    boxMove(e) {
      if (this.cornerDrag) { this.moveCorner(e); return; }
      if (!this.drawing) return;
      const img = this.$refs.frame;
      const b = img.getBoundingClientRect();
      const x = Math.min(Math.max(e.clientX - b.left, 0), b.width);
      const y = Math.min(Math.max(e.clientY - b.top, 0), b.height);
      this.drawRect = { x: Math.min(x, this.drawFrom.x), y: Math.min(y, this.drawFrom.y),
        w: Math.abs(x - this.drawFrom.x), h: Math.abs(y - this.drawFrom.y) };
    },
    boxEnd() {
      if (this.cornerDrag) {
        this.cornerDrag = null;
        this.renderFrame();
        return;
      }
      if (!this.drawing) return;
      this.drawing = false;
      const img = this.$refs.frame;
      if (!img || !this.drawRect || this.drawRect.w < 4 || this.drawRect.h < 4) return;
      const k = this.frameW / img.getBoundingClientRect().width;
      const texts = {};
      for (const l of this.textLangs) texts[l] = "";
      this.textRegions.push({
        name: "Vùng " + (this.textRegions.length + 1),
        x: Math.round(this.drawRect.x * k), y: Math.round(this.drawRect.y * k),
        width: Math.round(this.drawRect.w * k), height: Math.round(this.drawRect.h * k),
        texts,
        start: 0,
        end: "",
        points: null,
        style: { font: "Fira Sans", size: 48, color: "#FFFFFF", bold: false, align: "center", shadow: false,
                 stroke_width: 0, stroke_color: "#000000" },
      });
      this.drawRect = null;
    },
    regionDtos(lang) {
      return this.textRegions
        .filter(r => (r.texts[lang] || "").trim())
        .map(r => this.regionDto(r, lang));
    },
    regionDto(r, lang) {
      return {
        name: r.name, texts: { [lang]: r.texts[lang] },
        region: { x: r.x, y: r.y, width: r.width, height: r.height, points: r.points || [] },
        style: r.style, start: Number(r.start) || 0, end: this.endValue(r),
      };
    },
    endValue(r) {
      return r.end === "" || r.end == null ? null : Number(r.end);
    },
    toggleTilt(ri) {
      if (this.tiltFor === ri) { this.tiltFor = null; return; }
      const r = this.textRegions[ri];
      if (!r) return;
      if (!r.points) {
        r.points = [[r.x, r.y], [r.x + r.width, r.y], [r.x + r.width, r.y + r.height], [r.x, r.y + r.height]];
      }
      this.tiltFor = ri;
    },
    clearTilt(ri) {
      const r = this.textRegions[ri];
      if (r) r.points = null;
      if (this.tiltFor === ri) this.tiltFor = null;
      this.renderFrame();
    },
    cornerStyle(ci) {
      const r = this.tiltFor === null ? null : this.textRegions[this.tiltFor];
      const img = this.$refs.frame;
      if (!r || !r.points || !img || !this.frameW || !r.points[ci]) return "display:none";
      const k = img.getBoundingClientRect().width / this.frameW;
      return `left:${r.points[ci][0] * k}px;top:${r.points[ci][1] * k}px`;
    },
    startCorner(ci, e) {
      this.cornerDrag = { ri: this.tiltFor, ci };
      if (e.target && e.target.setPointerCapture) e.target.setPointerCapture(e.pointerId);
    },
    moveCorner(e) {
      const drag = this.cornerDrag;
      const r = drag ? this.textRegions[drag.ri] : null;
      const img = this.$refs.frame;
      if (!r || !r.points || !img) return;
      const b = img.getBoundingClientRect();
      const k = this.frameW / b.width;
      const x = Math.min(Math.max(e.clientX - b.left, 0), b.width) * k;
      const y = Math.min(Math.max(e.clientY - b.top, 0), b.height) * k;
      const pts = r.points.map(p => [...p]);
      pts[drag.ci] = [Math.round(x), Math.round(y)];
      r.points = pts;
      const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
      r.x = Math.min(...xs); r.y = Math.min(...ys);
      r.width = Math.max(...xs) - r.x; r.height = Math.max(...ys) - r.y;
    },
    regionStyle(r) {
      const img = this.$refs.frame;
      if (!img || !this.frameW) return "display:none";
      const k = img.getBoundingClientRect().width / this.frameW;
      return `left:${r.x * k}px;top:${r.y * k}px;width:${r.width * k}px;height:${r.height * k}px`;
    },
    get drawStyle() {
      const r = this.drawRect;
      return r ? `left:${r.x}px;top:${r.y}px;width:${r.w}px;height:${r.h}px` : "display:none";
    },
    addTextLang() {
      const l = (this.newLang || "").trim().toLowerCase();
      if (!l || this.textLangs.includes(l)) { this.newLang = ""; return; }
      this.textLangs.push(l);
      for (const r of this.textRegions) r.texts[l] = "";
      this.newLang = "";
    },

    /* ---------- tên file, chạy, kết quả ---------- */
    async refreshNames() {
      const langs = this.planLanguages.length ? this.planLanguages : ["orig"];
      try {
        const d = await api("POST", "/api/jobs/naming", { naming: this.naming, languages: langs, ratio: "9x16" });
        this.previewNames = d.names || [];
      } catch (e) { this.previewNames = []; }
    },
    payload() {
      const texts = this.textRegions.map(r => {
        const t = {};
        for (const l of this.textLangs) if ((r.texts[l] || "").trim()) t[l] = r.texts[l];
        return {
          name: r.name, region: { x: r.x, y: r.y, width: r.width, height: r.height, points: r.points || [] },
          texts: t, style: r.style, start: Number(r.start) || 0, end: this.endValue(r),
        };
      }).filter(t => Object.keys(t.texts).length > 0);
      const audio_labels = {};
      for (const a of [...this.appliedVoice, ...this.appliedMusic]) if (a.lang) audio_labels[a.name] = a.lang;
      return {
        input_dir: this.form.input_dir, output_dir: this.form.output_dir,
        segments: this.segmentPayload(),
        music_files: this.appliedMusic.map(a => a.path),
        voice_files: this.appliedVoice.map(a => a.path),
        audio_labels,
        keep_original: this.keepOriginal,
        volumes: { ...this.volumes },
        duck_music: this.duckMusic,
        texts,
        transitions: this.transitions,
        default_transition: { type: "none", duration: 0.5 },
        naming: { appname: this.naming.appname, concept: this.naming.concept, geo: this.naming.geo, date: this.naming.date },
        short_source: this.shortAction,
      };
    },
    async startJob(preview = false) {
      if (!this.canRun || this.busy) return;
      this.busy = true;
      this.message = "";
      try {
        const body = this.payload();
        const sig = JSON.stringify(body.segments.map(s => s.source_dir));
        const check = await api("POST", "/api/jobs/check", body);
        if (!check.ok) { this.message = check.error; return; }
        this.shortWarnings = check.warnings || [];
        if (this.shortWarnings.length > 0 && this.shownShortFor !== sig) {
          this.shownShortFor = sig;
          this.message = "Có source ngắn hơn đoạn cần thay. Chọn cách xử lý bên dưới rồi bấm Chạy lần nữa.";
          return;
        }
        await api("POST", "/api/jobs", preview ? { ...body, preview: true } : body);
        this.lastPreview = preview;
        this.outPreview = null;
        this.shownShortFor = "";
        await this.refreshJob();
      } catch (e) {
        this.message = e.message;
      } finally {
        this.busy = false;
      }
    },
    async stopJob() {
      try { await api("POST", "/api/jobs/stop"); } catch (e) { this.message = e.message; }
    },
    async refreshJob() {
      try {
        const j = await api("GET", "/api/jobs");
        this.job = Object.assign({}, this.job, j);
      } catch (e) { /* mất kết nối tạm thời — thử lại ở lần sau */ }
    },
    playOutput(o) {
      this.outPreview = o;
      this.$nextTick(() => {
        const v = this.$refs.outPlayer;
        v.src = this.mediaUrl(o.path);
        v.load();
      });
    },
    async openFolder() {
      try { await api("POST", "/api/fs/open", { path: this.job.output_dir }); }
      catch (e) { this.message = e.message; }
    },
  };
}
