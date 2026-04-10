const API = "http://localhost:8000";

/* ── Tab switching ── */
function showLogin() {
  document.getElementById("loginForm").style.display = "flex";
  document.getElementById("signupForm").style.display = "none";
  document.getElementById("loginTab").classList.add("active");
  document.getElementById("signupTab").classList.remove("active");
  clearErrors();
}

function showSignup() {
  document.getElementById("loginForm").style.display = "none";
  document.getElementById("signupForm").style.display = "flex";
  document.getElementById("loginTab").classList.remove("active");
  document.getElementById("signupTab").classList.add("active");
  clearErrors();
}

function clearErrors() {
  ["loginError", "signupError"].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.style.display = "none"; el.textContent = ""; }
  });
  document.querySelectorAll(".form-input.error").forEach(el => el.classList.remove("error"));
}

/* ── Password toggle ── */
function togglePw(inputId, btn) {
  const input = document.getElementById(inputId);
  if (input.type === "password") {
    input.type = "text";
    btn.textContent = "Hide";
  } else {
    input.type = "password";
    btn.textContent = "Show";
  }
}

/* ── Token helpers ── */
function storeAuth(data) {
  localStorage.setItem("mm_token", data.token);
  localStorage.setItem("mm_user", JSON.stringify({
    id: data.user_id,
    email: data.email,
    name: data.name,
    tier: data.tier,
  }));
}

function showError(errorId, message) {
  const el = document.getElementById(errorId);
  el.textContent = message;
  el.style.display = "block";
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (loading) {
    btn.disabled = true;
    btn.dataset.original = btn.textContent;
    btn.textContent = "Please wait…";
  } else {
    btn.disabled = false;
    btn.textContent = btn.dataset.original || btn.textContent;
  }
}

/* ── Login ── */
async function handleLogin(e) {
  e.preventDefault();
  clearErrors();

  const email    = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  setLoading("loginBtn", true);
  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      showError("loginError", data.detail || "Sign-in failed. Please check your credentials.");
      document.getElementById("loginEmail").classList.add("error");
      document.getElementById("loginPassword").classList.add("error");
      return;
    }

    storeAuth(data);
    window.location.href = "index.html";
  } catch {
    showError("loginError", "Could not connect to server. Is the backend running?");
  } finally {
    setLoading("loginBtn", false);
  }
}

/* ── Signup ── */
async function handleSignup(e) {
  e.preventDefault();
  clearErrors();

  const name     = document.getElementById("signupName").value.trim();
  const email    = document.getElementById("signupEmail").value.trim();
  const password = document.getElementById("signupPassword").value;

  if (password.length < 8) {
    showError("signupError", "Password must be at least 8 characters.");
    document.getElementById("signupPassword").classList.add("error");
    return;
  }

  setLoading("signupBtn", true);
  try {
    const res = await fetch(`${API}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name: name || null }),
    });
    const data = await res.json();

    if (!res.ok) {
      showError("signupError", data.detail || "Could not create account. Try a different email.");
      document.getElementById("signupEmail").classList.add("error");
      return;
    }

    storeAuth(data);
    window.location.href = "index.html";
  } catch {
    showError("signupError", "Could not connect to server. Is the backend running?");
  } finally {
    setLoading("signupBtn", false);
  }
}

/* ── Guard: redirect to auth if already logged in ── */
(function checkAlreadyLoggedIn() {
  const token = localStorage.getItem("mm_token");
  if (token) window.location.href = "index.html";
})();
