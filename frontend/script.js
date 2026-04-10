// ─────────────────────────────────────
// Config
// ─────────────────────────────────────
const API_BASE  = "http://127.0.0.1:8000";
const IDB_NAME  = "mentalmind-offline";
const IDB_STORE = "pending-entries";
const IDB_VER   = 1;

// ─────────────────────────────────────
// Auth helpers
// ─────────────────────────────────────
function getToken()  { return localStorage.getItem("mm_token"); }
function getUser()   { return JSON.parse(localStorage.getItem("mm_user") || "null"); }
function getUserId() { return getUser()?.id || null; }
function isPremium() { return getUser()?.tier === "premium"; }

function authHeaders() {
  const token = getToken();
  const base  = { "Content-Type": "application/json" };
  return token ? { ...base, "Authorization": `Bearer ${token}` } : base;
}

function signOut() {
  localStorage.removeItem("mm_token");
  localStorage.removeItem("mm_user");
  window.location.href = "auth.html";
}

function guardAuth() {
  if (!getToken()) { window.location.href = "auth.html"; return false; }
  return true;
}

// ─────────────────────────────────────
// Toast notifications
// ─────────────────────────────────────
function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById("toastContainer").appendChild(el);
  requestAnimationFrame(() => el.classList.add("visible"));
  setTimeout(() => {
    el.classList.remove("visible");
    setTimeout(() => el.remove(), 300);
  }, 3200);
}

// ─────────────────────────────────────
// Theme
// ─────────────────────────────────────
const MOON_SVG = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
const SUN_SVG  = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;

function resolveTheme(pref) {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return pref || "light";
}

function applyTheme(pref) {
  const actual = resolveTheme(pref);
  document.documentElement.setAttribute("data-theme", actual);
  localStorage.setItem("mm_theme", pref || "light");

  // Update all theme toggle icons
  const icon = actual === "dark" ? MOON_SVG : SUN_SVG;
  ["themeToggleBtn", "mobileThemeIcon"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = icon;
  });
  const mobileBtn = document.querySelector(".mobile-header .icon-btn");
  if (mobileBtn) mobileBtn.innerHTML = icon;

  // Update Settings theme buttons
  document.querySelectorAll(".theme-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.t === pref);
  });
}

function setTheme(pref) {
  applyTheme(pref);
}

function cycleTheme() {
  const current = localStorage.getItem("mm_theme") || "light";
  const next = current === "light" ? "dark" : current === "dark" ? "system" : "light";
  applyTheme(next);
}

// ─────────────────────────────────────
// Page routing
// ─────────────────────────────────────
let currentPage = "journal";

function navigateTo(page) {
  if (currentPage === page) return;
  currentPage = page;

  // Hide all pages
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  // Show target
  const target = document.getElementById(`page-${page}`);
  if (target) target.classList.add("active");

  // Update sidebar nav
  document.querySelectorAll(".nav-item").forEach(item => {
    item.classList.toggle("active", item.dataset.page === page);
  });
  // Update bottom nav
  document.querySelectorAll(".bottom-nav-item").forEach(item => {
    item.classList.toggle("active", item.dataset.page === page);
  });

  // Page-specific init
  if (page === "insights") initInsightsPage();
  if (page === "tasks")    loadTasks();
  if (page === "settings") initSettingsPage();

  // Update URL hash without reload
  history.pushState(null, "", `#${page}`);
}

function initInsightsPage() {
  if (isPremium()) {
    document.getElementById("insightsPremiumGate").style.display    = "none";
    document.getElementById("insightsPremiumContent").style.display = "block";
    loadStreak();
  } else {
    document.getElementById("insightsPremiumGate").style.display    = "block";
    document.getElementById("insightsPremiumContent").style.display = "none";
  }
}

// ─────────────────────────────────────
// Premium gate
// ─────────────────────────────────────
function requirePremium(action) {
  if (isPremium()) action();
  else openUpgradeModal();
}

function openUpgradeModal() {
  document.getElementById("upgradeOverlay").style.display = "flex";
  document.getElementById("upgradeModal").style.display   = "block";
}

function closeUpgradeModal() {
  document.getElementById("upgradeOverlay").style.display = "none";
  document.getElementById("upgradeModal").style.display   = "none";
}

async function upgradeAccount() {
  const btn = document.getElementById("upgradeCta");
  btn.disabled = true; btn.textContent = "Upgrading…";

  try {
    const res = await fetch(`${API_BASE}/auth/upgrade`, {
      method: "POST", headers: authHeaders(),
    });
    if (!res.ok) throw new Error();
    const data = await res.json();

    localStorage.setItem("mm_token", data.token);
    localStorage.setItem("mm_user", JSON.stringify({
      id: data.user_id, email: data.email, name: data.name, tier: data.tier,
    }));

    closeUpgradeModal();
    renderUserUI();
    initInsightsPage();
    toast("You're now on Premium! 🎉", "success");
  } catch {
    toast("Something went wrong. Please try again.", "error");
  } finally {
    btn.disabled = false; btn.textContent = "Upgrade — it's free to try";
  }
}

// ─────────────────────────────────────
// Render user info across the UI
// ─────────────────────────────────────
function renderUserUI() {
  const user = getUser();
  if (!user) return;

  const name    = user.name || user.email.split("@")[0];
  const initial = name.charAt(0).toUpperCase();
  const tier    = user.tier === "premium" ? "Premium" : "Free";

  // Sidebar
  el("sidebarAvatar",   initial);
  el("sidebarUserName", name);
  el("sidebarUserTier", user.tier === "premium" ? "Premium plan ★" : "Free plan");

  // Settings page
  el("settingsAvatar", initial);
  el("settingsName",   name);
  el("settingsEmail",  user.email);

  const tierBadge = document.getElementById("settingsTierBadge");
  if (tierBadge) {
    tierBadge.textContent = tier;
    tierBadge.className   = user.tier === "premium" ? "badge-premium" : "badge-free";
  }

  // Hide upgrade button if already premium
  const upgradeBtn = document.getElementById("settingsUpgradeBtn");
  if (upgradeBtn) upgradeBtn.style.display = user.tier === "premium" ? "none" : "block";

  // Premium dot on Insights nav item
  const dot = document.getElementById("insightsPremiumDot");
  if (dot) dot.style.display = isPremium() ? "none" : "block";

  // Unlock notifications if premium
  const notifBlock = document.getElementById("notifBlock");
  if (notifBlock) notifBlock.classList.toggle("notif-field-disabled", !isPremium());
}

function el(id, text) {
  const node = document.getElementById(id);
  if (node) node.textContent = text;
}

// ─────────────────────────────────────
// Greeting
// ─────────────────────────────────────
function setGreeting() {
  const h = new Date().getHours();
  const g = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  const user = getUser();
  const name = user?.name ? `, ${user.name.split(" ")[0]}` : "";
  el("journalGreeting", g + name);
}

// ─────────────────────────────────────
// State
// ─────────────────────────────────────
let currentTab          = "free";
let selectedEnergy      = null;
let currentReflectionId = null;
let currentEntryId      = null;
let currentEntryContent = "";
let currentAiTags       = [];
let allEntries          = [];
let activeTagFilter     = null;
let activeEnergyFilter  = null;
let advFiltersOpen      = false;
let followupTurn        = 0;
let followupHistory     = [];
let pendingTaskText     = null;
let userPrefs           = {};
let obStep              = 1;
const OB_TOTAL          = 4;

// ─────────────────────────────────────
// Init
// ─────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  if (!guardAuth()) return;

  // Apply saved theme immediately (also done inline to avoid FOUC)
  applyTheme(localStorage.getItem("mm_theme") || "light");

  renderUserUI();
  setGreeting();
  registerServiceWorker();
  monitorOnline();

  if (!getUserId()) { signOut(); return; }

  await loadPreferences();
  checkOnboarding();
  loadPatterns();
  if (isPremium()) loadStreak();
  loadTasks();
  checkReminder();

  // Routing from hash
  const hash = location.hash.replace("#", "");
  if (hash && ["journal","history","insights","tasks","settings"].includes(hash)) {
    navigateTo(hash);
  }

  // Modal overlay click
  document.getElementById("upgradeOverlay").addEventListener("click", closeUpgradeModal);

  // Onboarding chips
  document.querySelectorAll(".ob-chip").forEach(chip => {
    chip.addEventListener("click", () => chip.classList.toggle("selected"));
  });

  // Browser back/forward
  window.addEventListener("popstate", () => {
    const h = location.hash.replace("#", "");
    if (h) navigateTo(h);
  });
});

// ─────────────────────────────────────
// Settings page init
// ─────────────────────────────────────
function initSettingsPage() {
  renderUserUI();

  // Theme buttons
  const pref = localStorage.getItem("mm_theme") || "light";
  document.querySelectorAll(".theme-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.t === pref);
  });

  // Preferences
  const tone = userPrefs.tone_preference || "gentle";
  document.querySelectorAll("#settingsToneOptions .tone-option").forEach(btn => {
    btn.classList.toggle("selected", btn.dataset.val === tone);
  });
  const tw = document.getElementById("settingsTriggerWords");
  if (tw) tw.value = (userPrefs.trigger_words || []).join(", ");
  const sv = document.getElementById("settingsValues");
  if (sv) sv.value = userPrefs.user_values || "";

  // Reminder
  const toggle = document.getElementById("reminderToggle");
  const timeEl = document.getElementById("reminderTime");
  if (toggle) toggle.checked = userPrefs.reminder_enabled || false;
  if (timeEl) {
    timeEl.style.display = (userPrefs.reminder_enabled) ? "block" : "none";
    if (userPrefs.reminder_time) timeEl.value = userPrefs.reminder_time;
  }
}

// ─────────────────────────────────────
// Service Worker & Offline
// ─────────────────────────────────────
function registerServiceWorker() {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}

function monitorOnline() {
  const banner = document.getElementById("offlineBanner");
  const update = () => {
    banner.style.display = navigator.onLine ? "none" : "block";
    if (navigator.onLine) syncOfflineQueue();
  };
  window.addEventListener("online",  update);
  window.addEventListener("offline", update);
  update();
}

// ─────────────────────────────────────
// IndexedDB offline queue
// ─────────────────────────────────────
function openIDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, IDB_VER);
    req.onupgradeneeded = e => e.target.result.createObjectStore(IDB_STORE, { autoIncrement: true });
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = () => reject(req.error);
  });
}

async function queueOfflineEntry(payload) {
  const db = await openIDB();
  const tx = db.transaction(IDB_STORE, "readwrite");
  tx.objectStore(IDB_STORE).add(payload);
  return new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = rej; });
}

async function syncOfflineQueue() {
  let db; try { db = await openIDB(); } catch { return; }
  const tx    = db.transaction(IDB_STORE, "readwrite");
  const store = tx.objectStore(IDB_STORE);
  const allReq = store.getAll();
  const keyReq = store.getAllKeys();
  allReq.onsuccess = async () => {
    for (let i = 0; i < allReq.result.length; i++) {
      try {
        await fetch(`${API_BASE}/entries`, {
          method: "POST", headers: authHeaders(), body: JSON.stringify(allReq.result[i]),
        });
        db.transaction(IDB_STORE, "readwrite").objectStore(IDB_STORE).delete(keyReq.result[i]);
      } catch { /* still offline */ }
    }
  };
}

// ─────────────────────────────────────
// Preferences
// ─────────────────────────────────────
async function loadPreferences() {
  const userId = getUserId();
  if (!userId) return;
  try {
    const res = await fetch(`${API_BASE}/preferences/${userId}`, { headers: authHeaders() });
    if (res.ok) userPrefs = await res.json();
  } catch { userPrefs = {}; }
}

function selectPrefTone(btn) {
  const container = btn.closest(".tone-options");
  container.querySelectorAll(".tone-option").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
}

function toggleReminder() {
  const enabled = document.getElementById("reminderToggle").checked;
  document.getElementById("reminderTime").style.display = enabled ? "block" : "none";
}

async function savePrefs() {
  const userId = getUserId();
  if (!userId) return;

  const toneBtn  = document.querySelector("#settingsToneOptions .tone-option.selected");
  const tone     = toneBtn ? toneBtn.dataset.val : "gentle";
  const rawWords = document.getElementById("settingsTriggerWords")?.value || "";
  const trigWords = rawWords.split(",").map(w => w.trim()).filter(Boolean);
  const values    = document.getElementById("settingsValues")?.value.trim() || "";
  const remEnabled = isPremium() && (document.getElementById("reminderToggle")?.checked || false);
  const remTime    = document.getElementById("reminderTime")?.value || "20:00";

  const body = {
    tone_preference:  tone,
    trigger_words:    trigWords,
    user_values:      values || null,
    reminder_enabled: remEnabled,
    reminder_time:    remEnabled ? remTime : null,
  };

  try {
    const res = await fetch(`${API_BASE}/preferences/${userId}`, {
      method: "PUT", headers: authHeaders(), body: JSON.stringify(body),
    });
    if (res.ok) {
      userPrefs = await res.json();
      toast("Preferences saved.", "success");
    }
  } catch { toast("Could not save preferences.", "error"); }
}

// ─────────────────────────────────────
// Onboarding
// ─────────────────────────────────────
function checkOnboarding() {
  if (!userPrefs.onboarding_complete) {
    document.getElementById("onboardingOverlay").style.display = "flex";
    obStep = 1; renderObStep();
  }
}

function renderObStep() {
  document.querySelectorAll(".ob-step").forEach((s, i) => s.classList.toggle("active", i + 1 === obStep));
  document.querySelectorAll(".prog-dot").forEach((d, i) => d.classList.toggle("active", i + 1 <= obStep));
  document.getElementById("obBackBtn").style.visibility = obStep === 1 ? "hidden" : "visible";
  document.getElementById("obNextBtn").textContent = obStep === OB_TOTAL ? "Get started →" : "Continue →";
}

function obNext() { if (obStep < OB_TOTAL) { obStep++; renderObStep(); } else finishOnboarding(); }
function obPrev() { if (obStep > 1) { obStep--; renderObStep(); } }

function selectTone(btn) {
  btn.closest(".tone-options").querySelectorAll(".tone-option").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
}

async function finishOnboarding() {
  const userId = getUserId(); if (!userId) return;
  const toneBtn  = document.querySelector("#ob-step-2 .tone-option.selected");
  const rawGoals = [...document.querySelectorAll(".ob-chip.selected")].map(b => b.dataset.val).join(", ");
  const rawWords = document.getElementById("obTriggerWords").value;
  const body = {
    tone_preference:     toneBtn?.dataset.val || "gentle",
    trigger_words:       rawWords.split(",").map(w => w.trim()).filter(Boolean),
    goals_for_journaling: rawGoals || null,
    user_values:         document.getElementById("obValues").value.trim() || null,
    onboarding_complete: true,
  };
  try {
    const res = await fetch(`${API_BASE}/preferences/${userId}`, {
      method: "PUT", headers: authHeaders(), body: JSON.stringify(body),
    });
    if (res.ok) userPrefs = await res.json();
  } catch { /* silent */ }
  document.getElementById("onboardingOverlay").style.display = "none";
}

// ─────────────────────────────────────
// Streak
// ─────────────────────────────────────
async function loadStreak() {
  if (!isPremium()) return;
  const userId = getUserId(); if (!userId) return;
  try {
    const res = await fetch(`${API_BASE}/streaks/${userId}`, { headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();

    // Update streak card on Insights page
    const card = document.getElementById("streakCard");
    if (card && data.current_streak > 0) {
      el("streakNumber",  String(data.current_streak));
      el("streakMessage", data.message || "");
      card.style.display = "flex";
    }

    // Badge in header area
    if (data.current_streak >= 2) {
      const badgeText = `🔥 ${data.current_streak}-day streak`;
      ["desktopStreakBadge","mobileStreakBadge"].forEach(id => {
        const b = document.getElementById(id);
        if (b) { b.textContent = badgeText; b.style.display = "inline-flex"; }
      });
    }
  } catch { /* optional */ }
}

// ─────────────────────────────────────
// Reminder banner
// ─────────────────────────────────────
function checkReminder() {
  if (!isPremium() || !userPrefs.reminder_enabled || !userPrefs.reminder_time) return;
  const now = new Date();
  const [hh, mm] = (userPrefs.reminder_time).split(":").map(Number);
  const target = new Date(now); target.setHours(hh, mm, 0, 0);
  if (Math.abs(now - target) / 60000 <= 30) {
    el("reminderText", "Your journaling reminder — take a few minutes to write today.");
    document.getElementById("reminderBanner").style.display = "flex";
  }
}
function dismissReminder() { document.getElementById("reminderBanner").style.display = "none"; }

// ─────────────────────────────────────
// Pattern banner
// ─────────────────────────────────────
async function loadPatterns() {
  const userId = getUserId(); if (!userId) return;
  try {
    const res  = await fetch(`${API_BASE}/patterns/${userId}`, { headers: authHeaders() });
    const data = await res.json();
    if (data.has_pattern && data.pattern_message) {
      el("patternMessage", data.pattern_message);
      document.getElementById("patternBanner").style.display = "flex";
    }
  } catch { /* optional */ }
}

// ─────────────────────────────────────
// Tab navigation
// ─────────────────────────────────────
function showTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.getElementById(`tab-${tab}`).classList.add("active");
  ["free","prompts","checkin"].forEach(t => {
    document.getElementById(`panel-${t}`).style.display = t === tab ? "block" : "none";
  });
  hideReflection();
  if (tab === "checkin") loadCheckin();
}

// ─────────────────────────────────────
// Energy
// ─────────────────────────────────────
function selectEnergy(btn) {
  document.querySelectorAll(".energy-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
  selectedEnergy = parseInt(btn.dataset.val, 10);
}

// ─────────────────────────────────────
// Emotion chips
// ─────────────────────────────────────
function selectEmotion(btn) {
  document.querySelectorAll(".chip").forEach(c => c.classList.remove("selected"));
  btn.classList.add("selected");
  document.getElementById("selectedEmotion").value  = btn.dataset.emotion;
  document.getElementById("selectedPromptId").value = "";
  document.getElementById("promptContent").style.display = "none";
  loadPromptsForEmotion(btn.dataset.emotion);
}

async function loadPromptsForEmotion(emotion) {
  const c = document.getElementById("promptCards");
  c.innerHTML = ""; c.style.display = "none";
  try {
    const res = await fetch(`${API_BASE}/prompts/${emotion}`, { headers: authHeaders() });
    const prompts = await res.json();
    prompts.forEach(p => {
      const card = document.createElement("button");
      card.className = "prompt-card"; card.dataset.promptId = p.id; card.textContent = p.text;
      card.onclick = () => selectPrompt(card, p.id);
      c.appendChild(card);
    });
    c.style.display = "flex";
  } catch { /* ignore */ }
}

function selectPrompt(card, promptId) {
  document.querySelectorAll(".prompt-card").forEach(c => c.classList.remove("selected"));
  card.classList.add("selected");
  document.getElementById("selectedPromptId").value = promptId;
  const ta = document.getElementById("promptContent");
  ta.style.display = "block"; ta.focus();
}

// ─────────────────────────────────────
// Personalized prompt
// ─────────────────────────────────────
async function loadPersonalizedPrompt() {
  const userId = getUserId(); if (!userId) return;
  const btn = document.getElementById("ppGenBtn");
  btn.disabled = true; btn.textContent = "Generating…";
  try {
    const res  = await fetch(`${API_BASE}/prompts/personalized`, {
      method: "POST", headers: authHeaders(), body: JSON.stringify({ user_id: userId }),
    });
    const data = await res.json();
    el("personalizedPromptText", data.prompt);
    document.getElementById("personalizedPromptRow").style.display = "flex";
  } catch {
    el("personalizedPromptText", "What's one thing that's been quietly on your mind?");
    document.getElementById("personalizedPromptRow").style.display = "flex";
  } finally {
    btn.disabled = false; btn.textContent = "✦ Generate a prompt for me";
  }
}

function usePersonalizedPrompt() {
  const text = document.getElementById("personalizedPromptText").textContent;
  const ta   = document.getElementById("freeContent");
  if (!ta.value.trim()) ta.placeholder = text;
  dismissPersonalizedPrompt(); ta.focus();
}
function dismissPersonalizedPrompt() {
  document.getElementById("personalizedPromptRow").style.display = "none";
}

// ─────────────────────────────────────
// Check-in
// ─────────────────────────────────────
async function loadCheckin() {
  const userId = getUserId(); if (!userId) return;
  document.getElementById("checkinLoading").style.display = "flex";
  document.getElementById("checkinContent").style.display = "none";
  try {
    const res  = await fetch(`${API_BASE}/checkin/${userId}`, { headers: authHeaders() });
    const data = await res.json();
    el("checkinQuestion", data.checkin_question);
    el("checkinContext",  data.context_summary || "");
    document.getElementById("checkinContent").style.display = "block";
  } catch {
    el("checkinQuestion", "How are you feeling today?");
    document.getElementById("checkinContent").style.display = "block";
  } finally {
    document.getElementById("checkinLoading").style.display = "none";
  }
}

// ─────────────────────────────────────
// Submit entry
// ─────────────────────────────────────
async function submitEntry() {
  const btn = document.getElementById("submitBtn");
  btn.disabled = true; btn.textContent = "Reflecting…";
  hideReflection();
  try {
    let data;
    if (currentTab === "free")    data = await submitFreeWrite();
    if (currentTab === "prompts") data = await submitPrompt();
    if (currentTab === "checkin") data = await submitCheckin();
    if (data) showReflection(data);
  } catch (err) {
    console.error(err);
    showReflection({ reflection_text: "Something went wrong. Please try again.", ai_tags: [] });
  } finally {
    btn.disabled = false; btn.textContent = "Reflect →";
  }
}

async function submitFreeWrite() {
  const userId  = getUserId();
  const content = document.getElementById("freeContent").value.trim();
  if (!content) { toast("Write something before reflecting.", "error"); return null; }
  const payload = { user_id: userId, content, energy_level: selectedEnergy || null };
  if (!navigator.onLine) {
    await queueOfflineEntry(payload);
    return { reflection_text: "You're offline — your entry has been saved and will sync when you reconnect.", ai_tags: [] };
  }
  const res = await fetch(`${API_BASE}/entries`, {
    method: "POST", headers: authHeaders(), body: JSON.stringify(payload),
  });
  currentEntryContent = content;
  return res.json();
}

async function submitPrompt() {
  const userId   = getUserId();
  const content  = document.getElementById("promptContent").value.trim();
  const promptId = document.getElementById("selectedPromptId").value;
  const emotion  = document.getElementById("selectedEmotion").value;
  if (!promptId) { toast("Select a prompt first.", "error"); return null; }
  if (!content)  { toast("Write your response before reflecting.", "error"); return null; }
  const res = await fetch(`${API_BASE}/entries/prompt`, {
    method: "POST", headers: authHeaders(),
    body: JSON.stringify({ user_id: userId, content, prompt_id: promptId, emotion: emotion || null, energy_level: selectedEnergy || null }),
  });
  currentEntryContent = content;
  return res.json();
}

async function submitCheckin() {
  const userId   = getUserId();
  const content  = document.getElementById("checkinResponse").value.trim();
  const question = document.getElementById("checkinQuestion").textContent;
  if (!content) { toast("Write your response before reflecting.", "error"); return null; }
  const res = await fetch(`${API_BASE}/entries/checkin`, {
    method: "POST", headers: authHeaders(),
    body: JSON.stringify({ user_id: userId, content, checkin_question: question, energy_level: selectedEnergy || null }),
  });
  currentEntryContent = content;
  return res.json();
}

// ─────────────────────────────────────
// Reflection display
// ─────────────────────────────────────
function showReflection(data) {
  currentReflectionId = data.reflection_id || null;
  currentEntryId      = data.entry_id      || null;
  currentAiTags       = data.ai_tags       || [];
  followupTurn = 0; followupHistory = [];

  el("reflectionText", data.reflection_text || "");

  const badge = document.getElementById("templateBadge");
  if (data.template_used) {
    badge.textContent = `✦ ${data.template_used} reflection`; badge.style.display = "inline-block";
  } else { badge.style.display = "none"; }

  const tagDisplay = document.getElementById("tagDisplay");
  tagDisplay.innerHTML = "";
  if (currentAiTags.length > 0) {
    currentAiTags.forEach(tag => {
      const chip = document.createElement("span");
      chip.className = "tag-chip"; chip.textContent = tag;
      tagDisplay.appendChild(chip);
    });
    document.getElementById("tagRow").style.display = "flex";
  } else { document.getElementById("tagRow").style.display = "none"; }

  document.querySelectorAll(".feedback-btn").forEach(b => b.classList.remove("chosen"));
  document.getElementById("fb-expand").disabled = false;
  ["followupThread","nextStepRow","nextStepPrompt","microTaskRow","suggestTaskBtn","calendarRow"].forEach(id => {
    const node = document.getElementById(id);
    if (node) {
      node.style.display = "none";
      if (node.tagName !== "BUTTON") node.innerHTML = id === "followupThread" ? "" : node.innerHTML;
    }
  });

  document.getElementById("reflectionSection").style.display = "block";
  document.getElementById("reflectionSection").scrollIntoView({ behavior: "smooth", block: "nearest" });

  if (selectedEnergy && selectedEnergy <= 2) {
    document.getElementById("calendarRow").style.display = "flex";
  }
}

function hideReflection() {
  document.getElementById("reflectionSection").style.display = "none";
}

// ─────────────────────────────────────
// Feedback
// ─────────────────────────────────────
async function sendFeedback(value) {
  document.querySelectorAll(".feedback-btn").forEach(b => b.classList.remove("chosen"));
  document.getElementById(`fb-${value}`).classList.add("chosen");
  document.getElementById("nextStepRow").style.display    = "flex";
  document.getElementById("suggestTaskBtn").style.display = "block";
  if (!currentReflectionId) return;
  try {
    await fetch(`${API_BASE}/reflections/${currentReflectionId}/feedback`, {
      method: "PATCH", headers: authHeaders(), body: JSON.stringify({ feedback: value }),
    });
  } catch { /* ignore */ }
}

// ─────────────────────────────────────
// Follow-up conversation
// ─────────────────────────────────────
async function startExpand() {
  const btn = document.getElementById("fb-expand");
  btn.disabled = true; btn.textContent = "Loading…";
  const thread = document.getElementById("followupThread");
  thread.style.display = "flex"; thread.innerHTML = "";
  followupTurn = 1; followupHistory = [];
  await requestFollowup(null);
  btn.textContent = "Expand →";
}

async function requestFollowup(userMessage) {
  const thread = document.getElementById("followupThread");
  if (userMessage) {
    const ub = document.createElement("div");
    ub.className = "followup-bubble user"; ub.textContent = userMessage;
    thread.appendChild(ub);
    followupHistory.push({ role: "user", content: userMessage });
  }
  try {
    const res  = await fetch(`${API_BASE}/followup`, {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({
        entry_id: currentEntryId, entry_content: currentEntryContent,
        conversation_history: followupHistory, user_message: userMessage, turn: followupTurn,
      }),
    });
    const data = await res.json();
    followupHistory.push({ role: "assistant", content: data.text });
    const ab = document.createElement("div");
    ab.className = "followup-bubble assistant"; ab.textContent = data.text;
    thread.appendChild(ab);

    if (data.is_final) {
      const note = document.createElement("p");
      note.className = "followup-final"; note.textContent = "— end of follow-up —";
      thread.appendChild(note);
      document.getElementById("nextStepRow").style.display    = "flex";
      document.getElementById("suggestTaskBtn").style.display = "block";
    } else if (data.options?.length > 0) {
      const row = document.createElement("div"); row.className = "followup-options";
      data.options.forEach(opt => {
        const b = document.createElement("button"); b.className = "followup-option-btn"; b.textContent = opt;
        b.onclick = () => { row.querySelectorAll("button").forEach(x => { x.disabled = true; x.style.opacity = x.textContent === opt ? "1" : "0.4"; }); if (followupTurn <= 3) requestFollowup(opt); };
        row.appendChild(b);
      });
      thread.appendChild(row);
    } else { renderFollowupInput(thread); }
    followupTurn++;
    thread.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch {
    const err = document.createElement("p"); err.className = "empty-state"; err.textContent = "Couldn't load follow-up.";
    thread.appendChild(err);
  }
}

function renderFollowupInput(thread) {
  const wrapper = document.createElement("div"); wrapper.className = "followup-input";
  const ta  = document.createElement("textarea"); ta.className = "followup-textarea"; ta.placeholder = "Write your response…"; ta.rows = 3;
  const btn = document.createElement("button"); btn.className = "followup-send-btn"; btn.textContent = "Send";
  btn.onclick = () => { const msg = ta.value.trim(); if (!msg) return; ta.disabled = btn.disabled = true; wrapper.remove(); if (followupTurn <= 3) requestFollowup(msg); };
  wrapper.appendChild(ta); wrapper.appendChild(btn); thread.appendChild(wrapper); ta.focus();
}

// ─────────────────────────────────────
// Next step
// ─────────────────────────────────────
const TAG_TO_EMOTION = { overwhelm:"overwhelmed",overwhelmed:"overwhelmed",burnout:"burnout",exhaustion:"burnout",tired:"burnout",anxiety:"anxiety",anxious:"anxiety",worry:"anxiety",decision:"decision","self-doubt":"self-doubt",doubt:"self-doubt",grief:"grief",loss:"grief",gratitude:"gratitude" };
function pickBestEmotion(tags) { for (const t of tags) { const k = TAG_TO_EMOTION[t.toLowerCase().trim()]; if (k) return k; } return null; }

async function showNextStepPrompt() {
  document.getElementById("nextStepRow").style.display = "none";
  const box = document.getElementById("nextStepPrompt");
  box.textContent = "Finding a prompt for you…"; box.style.display = "block";
  const emotion = pickBestEmotion(currentAiTags);
  try {
    const url = emotion ? `${API_BASE}/prompts/${emotion}` : `${API_BASE}/prompts/`;
    const res = await fetch(url, { headers: authHeaders() });
    const prompts = await res.json();
    if (Array.isArray(prompts) && prompts.length > 0 && typeof prompts[0] === "object") {
      box.textContent = `Try this: "${prompts[Math.floor(Math.random() * prompts.length)].text}"`;
    } else { box.textContent = "Take a breath and try writing freely again soon."; }
  } catch { box.textContent = "Take a breath and try writing freely again soon."; }
}

function dismissNextStep() {
  document.getElementById("nextStepRow").style.display    = "none";
  document.getElementById("nextStepPrompt").style.display = "none";
}

// ─────────────────────────────────────
// Micro-task
// ─────────────────────────────────────
async function suggestTask() {
  const userId = getUserId(); if (!userId) return;
  document.getElementById("suggestTaskBtn").style.display = "none";
  const row  = document.getElementById("microTaskRow");
  const text = document.getElementById("microTaskText");
  text.textContent = "Finding a small step for you…"; row.style.display = "block";
  try {
    const res  = await fetch(`${API_BASE}/tasks/suggest`, {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ user_id: userId, reflection_text: document.getElementById("reflectionText").textContent, energy_level: selectedEnergy || null }),
    });
    const data = await res.json();
    pendingTaskText = data.task_text; text.textContent = data.task_text;
  } catch { pendingTaskText = "Take one slow breath and notice how you feel."; text.textContent = pendingTaskText; }
}

async function saveTask() {
  const userId = getUserId(); if (!pendingTaskText || !userId) return;
  try {
    await fetch(`${API_BASE}/tasks`, {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ user_id: userId, task_text: pendingTaskText, energy_required: selectedEnergy || null }),
    });
    pendingTaskText = null;
    document.getElementById("microTaskRow").style.display = "none";
    loadTasks();
    toast("Step saved to My Steps.", "success");
  } catch { /* ignore */ }
}
function dismissTask() { pendingTaskText = null; document.getElementById("microTaskRow").style.display = "none"; }

// ─────────────────────────────────────
// Calendar block
// ─────────────────────────────────────
async function downloadCalendarBlock() {
  document.getElementById("calendarRow").style.display = "none";
  try {
    const res = await fetch(`${API_BASE}/reports/calendar-block`, {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ user_id: getUserId(), duration_hours: 2, label: "Rest & Recovery" }),
    });
    if (!res.ok) { toast("Could not generate calendar file.", "error"); return; }
    triggerDownload(await res.blob(), "mentalmind-recovery.ics", "text/calendar");
    toast("Calendar block downloaded.", "success");
  } catch { toast("Could not generate calendar file.", "error"); }
}
function dismissCalendar() { document.getElementById("calendarRow").style.display = "none"; }

// ─────────────────────────────────────
// PDF exports
// ─────────────────────────────────────
async function downloadWeeklyReport() {
  const userId = getUserId(); if (!userId) return;
  toast("Generating PDF…", "info");
  try {
    const res = await fetch(`${API_BASE}/reports/weekly/${userId}`, { headers: authHeaders() });
    if (!res.ok) { const e = await res.json().catch(() => ({})); toast(e.detail || "PDF unavailable.", "error"); return; }
    triggerDownload(await res.blob(), "mentalmind-weekly-report.pdf", "application/pdf");
    toast("Weekly report downloaded.", "success");
  } catch { toast("Could not download report.", "error"); }
}

async function downloadClinicianExport() {
  const userId = getUserId(); if (!userId) return;
  toast("Generating export…", "info");
  try {
    const res = await fetch(`${API_BASE}/reports/clinician/${userId}`, { headers: authHeaders() });
    if (!res.ok) { const e = await res.json().catch(() => ({})); toast(e.detail || "PDF unavailable.", "error"); return; }
    triggerDownload(await res.blob(), "mentalmind-clinician-export.pdf", "application/pdf");
    toast("Clinician export downloaded.", "success");
  } catch { toast("Could not download export.", "error"); }
}

function triggerDownload(blob, filename, type) {
  const url = URL.createObjectURL(new Blob([blob], { type }));
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ─────────────────────────────────────
// Insights
// ─────────────────────────────────────
async function loadInsights() {
  const userId = getUserId(); if (!userId) return;
  const body = document.getElementById("insightsBody");
  body.innerHTML = '<div class="empty-state"><span class="loading-dot"></span> Analysing entries…</div>';
  try {
    const res  = await fetch(`${API_BASE}/insights/${userId}`, { headers: authHeaders() });
    if (!res.ok) { body.innerHTML = `<div class="empty-state">${res.status === 403 ? "Premium required." : "Could not load insights."}</div>`; return; }
    renderInsights(await res.json());
  } catch { body.innerHTML = '<div class="empty-state">Could not load insights.</div>'; }
}

function renderInsights(data) {
  const body = document.getElementById("insightsBody");
  body.innerHTML = "";
  if (data.emotional_arc) {
    const l = document.createElement("p"); l.className = "insight-section-label"; l.textContent = "Emotional trend";
    const v = document.createElement("p"); v.className = "insight-arc"; v.textContent = data.emotional_arc;
    body.appendChild(l); body.appendChild(v);
  }
  if (data.recurring_triggers?.length) {
    const l = document.createElement("p"); l.className = "insight-section-label"; l.style.marginTop = "8px"; l.textContent = "Recurring triggers";
    const t = document.createElement("div"); t.className = "insight-triggers";
    data.recurring_triggers.forEach(trig => {
      const s = document.createElement("span"); s.className = "insight-trigger"; s.textContent = trig; t.appendChild(s);
    });
    body.appendChild(l); body.appendChild(t);
  }
  if (data.insights?.length) {
    const l = document.createElement("p"); l.className = "insight-section-label"; l.style.marginTop = "8px"; l.textContent = "Patterns noticed";
    body.appendChild(l);
    data.insights.forEach(insight => {
      const item = document.createElement("div"); item.className = "insight-item";
      item.innerHTML = `<span class="insight-dot"></span><span>${escapeHtml(insight)}</span>`;
      body.appendChild(item);
    });
  }
  if (!body.children.length) body.innerHTML = '<div class="empty-state">Keep journaling — patterns emerge over time.</div>';
}

// ─────────────────────────────────────
// Tasks
// ─────────────────────────────────────
async function loadTasks() {
  const userId = getUserId(); if (!userId) return;
  try {
    const res   = await fetch(`${API_BASE}/tasks/${userId}?status=pending`, { headers: authHeaders() });
    const tasks = await res.json();
    const list  = document.getElementById("tasksList");
    list.innerHTML = "";
    if (!tasks || tasks.length === 0) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✓</div><p>No pending steps. Add one from your next reflection.</p></div>';
      return;
    }
    tasks.forEach(t => {
      const item = document.createElement("div"); item.className = "task-item"; item.dataset.taskId = t.task_id;
      item.innerHTML = `<span class="task-text">${escapeHtml(t.task_text)}</span><div class="task-actions"><button class="task-action-btn done-btn" onclick="updateTask('${t.task_id}','done')">Done ✓</button><button class="task-action-btn skip-btn" onclick="updateTask('${t.task_id}','skipped')">Skip</button></div>`;
      list.appendChild(item);
    });
  } catch { /* ignore */ }
}

async function updateTask(taskId, status) {
  try {
    await fetch(`${API_BASE}/tasks/${taskId}/status`, {
      method: "PATCH", headers: authHeaders(), body: JSON.stringify({ status }),
    });
    document.querySelector(`[data-task-id="${taskId}"]`)?.remove();
    toast(status === "done" ? "Great work — step completed! 🎉" : "Step skipped.", status === "done" ? "success" : "info");
    if (!document.getElementById("tasksList")?.children.length) loadTasks();
  } catch { /* ignore */ }
}

// ─────────────────────────────────────
// History
// ─────────────────────────────────────
async function loadEntries() {
  const userId = getUserId(); if (!userId) return;
  const btn = document.getElementById("loadEntriesBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Loading…"; }
  const list = document.getElementById("historyList");
  list.innerHTML = '<div class="empty-state"><span class="loading-dot"></span> Loading entries…</div>';
  try {
    const res  = await fetch(`${API_BASE}/entries/${userId}`, { headers: authHeaders() });
    allEntries = await res.json();
    buildFilterChips(allEntries);
    renderEntries(allEntries);
    document.getElementById("historyFilters").style.display = allEntries.length > 0 ? "flex" : "none";
  } catch { list.innerHTML = '<div class="empty-state">Could not load entries.</div>'; }
  finally { if (btn) { btn.disabled = false; btn.textContent = "Load entries"; } }
}

function toggleAdvFilters() {
  advFiltersOpen = !advFiltersOpen;
  document.getElementById("advFilters").style.display = advFiltersOpen ? "flex" : "none";
  document.querySelector(".adv-toggle-btn").textContent = advFiltersOpen ? "Advanced filters ▴" : "Advanced filters ▾";
}

function selectEnergyFilter(btn, val) {
  document.querySelectorAll(".adv-energy-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected"); activeEnergyFilter = val || null; filterEntries();
}

function clearAdvFilters() {
  document.getElementById("filterFrom").value = "";
  document.getElementById("filterTo").value   = "";
  activeEnergyFilter = null;
  document.querySelectorAll(".adv-energy-btn").forEach(b => b.classList.remove("selected"));
  document.querySelector('.adv-energy-btn[data-val=""]')?.classList.add("selected");
  filterEntries();
}

function buildFilterChips(entries) {
  const tagCounts = {};
  entries.forEach(e => e.tags.forEach(t => { if (t.tag !== "check-in" && !t.is_private) tagCounts[t.tag] = (tagCounts[t.tag] || 0) + 1; }));
  const sorted = Object.entries(tagCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const c = document.getElementById("filterTags"); c.innerHTML = "";
  sorted.forEach(([tag]) => {
    const chip = document.createElement("button"); chip.className = "filter-chip"; chip.textContent = tag;
    chip.onclick = () => toggleTagFilter(chip, tag); c.appendChild(chip);
  });
}

function toggleTagFilter(chip, tag) {
  if (activeTagFilter === tag) { activeTagFilter = null; chip.classList.remove("active"); }
  else { document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active")); activeTagFilter = tag; chip.classList.add("active"); }
  filterEntries();
}

function filterEntries() {
  const query       = document.getElementById("searchInput").value.toLowerCase().trim();
  const fromDate    = document.getElementById("filterFrom")?.value || "";
  const toDate      = document.getElementById("filterTo")?.value   || "";
  const showPrivate = document.getElementById("showPrivate")?.checked ?? true;
  renderEntries(allEntries.filter(e => {
    const d = e.created_at.slice(0, 10);
    return (!query || e.content.toLowerCase().includes(query))
        && (!activeTagFilter || e.tags.some(t => t.tag === activeTagFilter))
        && (!fromDate || d >= fromDate) && (!toDate || d <= toDate)
        && (!activeEnergyFilter || String(e.energy_level) === activeEnergyFilter);
  }), showPrivate);
}

function renderEntries(entries, showPrivate = true) {
  const list = document.getElementById("historyList"); list.innerHTML = "";
  if (!entries.length) { list.innerHTML = '<div class="empty-state">No entries found.</div>'; return; }
  entries.forEach(e => {
    const card = document.createElement("div"); card.className = "entry-card";
    const reflection = e.reflections[0]?.reflection_text || "";
    const rawContent = e.content.replace(/^\[Check-in\]\s*/, "");
    const tagsHTML = e.tags.filter(t => showPrivate || !t.is_private).map(t => {
      const cls = t.is_private ? "entry-tag private-tag" : t.source === "user" ? "entry-tag user-tag" : "entry-tag";
      return `<span class="${cls}">${escapeHtml(t.is_private ? "🔒 " + t.tag : t.tag)}</span>`;
    }).join("");
    card.innerHTML = `
      <div class="entry-card-header">
        <span class="entry-date">${formatDate(e.created_at)}</span>
        ${e.energy_level ? `<span class="entry-energy">Energy ${e.energy_level}/5</span>` : ""}
      </div>
      <div class="entry-card-body">
        <p class="entry-content-text">${escapeHtml(rawContent)}</p>
        ${reflection ? `<p class="entry-reflection">${escapeHtml(reflection)}</p>` : ""}
        ${tagsHTML   ? `<div class="entry-tags">${tagsHTML}</div>` : ""}
      </div>`;
    list.appendChild(card);
  });
}

// ─────────────────────────────────────
// Utilities
// ─────────────────────────────────────
function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
}

function escapeHtml(str) {
  return (str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
