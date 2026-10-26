/* Video Bulk Remixer — giao diện Alpine.js (không dùng CDN, không inline script). */
"use strict";

const EFFECTS = [
  { id: "crossfade", label: "Crossfade", icon: "🌊" },
  { id: "fade_black", label: "Fade to black", icon: "⬛" },
  { id: "fade_white", label: "Fade to white", icon: "⬜" },
  { id: "slide_lr", label: "Slide →", icon: "➡️" },
  { id: "slide_rl", label: "Slide ←", icon: "⬅️" },
  { id: "wipe_tb", label: "Wipe ↓", icon: "⬇️" },
  { id: "wipe_bt", label: "Wipe ↑", icon: "⬆️" },
];
const LANGS = ["vi", "en", "es", "pt", "fr", "de", "ja", "ko", "zh", "th", "id", "ar", "ru", "it", "tr"];
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

    form: { input_dir: "", output_dir: "", audio_dir: "" },
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
    audioFiles: [],
    textLangs: ["vi", "en"],
    newLang: "",
    textRegions: [],
    frameAt: 1,
    frameUrl: "",
    frameInfo: "",
    frameW: 0,
    frameH: 0,
    drawing: false,
    drawFrom: null,
    drawRect: null,

    naming: { appname: "", concept: "", geo: "WW", date: "" },
    previewNames: [],

    job: { status: "idle", done: 0, total: 0, current: "", ok: 0, outputs: [], failed: [], error: "", output_dir: "" },
    outPreview: null,
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
    get planLanguages() {
      const langs = new Set(this.audioFiles.map(a => a.lang).filter(Boolean));
      for (const r of this.textRegions) {
        for (const l of this.textLangs) if ((r.texts[l] || "").trim()) langs.add(l);
      }
      return [...langs].sort();
    },
    get planCount() {
      const langs = this.planLanguages;
      if (langs.length === 0) return 1;
      let n = 0;
      for (const l of langs) n += Math.max(1, this.audioFiles.filter(a => a.lang === l).length);
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
      if (this.activeSegments.length === 0 && this.audioFiles.length === 0 && !this.hasTextWork) {
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
      this.$watch("form.input_dir", (v) => { if (v) this.scanVideos(v); else this.videos = []; });
      this.$watch("form.audio_dir", (v) => { if (v) this.scanAudio(v); });
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
    async scanAudio(dir) {
      try {
        const d = await api("GET", "/api/fs/list?kind=audio&dir=" + encodeURIComponent(dir));
        this.audioFiles = (d.files || []).map(f => ({ name: f.name, path: f.path, lang: this.guessLang(f.name) }));
      } catch (e) { this.audioFiles = []; }
    },
    guessLang(name) {
      const stem = name.replace(/\.[^.]+$/, "").toLowerCase();
      const parts = stem.replace(/-/g, "_").split("_");
      for (let i = parts.length - 1; i >= 0; i--) if (LANGS.includes(parts[i])) return parts[i];
      return "";
    },
    mediaUrl(path) { return "/api/fs/media?path=" + encodeURIComponent(path); },
    thumbUrl(v) { return "/api/fs/frame?w=160&t=1&path=" + encodeURIComponent(v.path); },

    /* ---------- xem trước video gốc ---------- */
    openPreview(v) {
      if (!v.duration) { this.message = v.error || "Không đọc được video này"; return; }
      this.preview = v;
      this.now = 0;
      this.$nextTick(() => {
        const p = document.getElementById("player");
        p.src = this.mediaUrl(v.path);
        p.load();
      });
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
      } catch (e) { this.frameInfo = e.message; }
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
      if (!this.drawing) return;
      const img = this.$refs.frame;
      const b = img.getBoundingClientRect();
      const x = Math.min(Math.max(e.clientX - b.left, 0), b.width);
      const y = Math.min(Math.max(e.clientY - b.top, 0), b.height);
      this.drawRect = { x: Math.min(x, this.drawFrom.x), y: Math.min(y, this.drawFrom.y),
        w: Math.abs(x - this.drawFrom.x), h: Math.abs(y - this.drawFrom.y) };
    },
    boxEnd() {
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
        style: { font: "Fira Sans", size: 48, color: "#FFFFFF", bold: false, align: "center", shadow: false,
                 stroke_width: 0, stroke_color: "#000000" },
      });
      this.drawRect = null;
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
        return { name: r.name, region: { x: r.x, y: r.y, width: r.width, height: r.height }, texts: t, style: r.style };
      }).filter(t => Object.keys(t.texts).length > 0);
      const audio_labels = {};
      for (const a of this.audioFiles) if (a.lang) audio_labels[a.name] = a.lang;
      return {
        input_dir: this.form.input_dir, output_dir: this.form.output_dir,
        segments: this.segmentPayload(),
        audio_files: this.audioFiles.map(a => a.path), audio_labels,
        texts,
        transitions: this.transitions,
        default_transition: { type: "none", duration: 0.5 },
        naming: { appname: this.naming.appname, concept: this.naming.concept, geo: this.naming.geo, date: this.naming.date },
        short_source: this.shortAction,
      };
    },
    async startJob() {
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
        await api("POST", "/api/jobs", body);
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
