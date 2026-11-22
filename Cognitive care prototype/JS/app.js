const API_BASE_URL = "http://127.0.0.1:8000";
function showAuthPanel(panel) {
  document.getElementById("login-panel").hidden = panel !== "login";
  document.getElementById("register-panel").hidden = panel !== "register";
  document.getElementById("age-panel").hidden = true;
  document.getElementById("aptitude-panel").hidden = true;
  document.getElementById("message").textContent = "";
}

function showAgePanel() {
  document.getElementById("login-panel").hidden = true;
  document.getElementById("register-panel").hidden = true;
  document.getElementById("age-panel").hidden = false;
  document.getElementById("aptitude-panel").hidden = true;
  document.getElementById("message").textContent =
    "Please enter your age once to finish setting up your account.";
}

function showAptitudePanel(age, saved = null) {
  if (age != null) localStorage.setItem("user_age", String(age));
  document.getElementById("login-panel").hidden = true;
  document.getElementById("register-panel").hidden = true;
  document.getElementById("age-panel").hidden = true;
  document.getElementById("aptitude-panel").hidden = false;
  const initial = saved || {};
  const ageMode = age < 45 ? "hard" : age <= 60 ? "medium" : "easy";
  document.getElementById("apt-memory").value = initial.memory || ageMode;
  document.getElementById("apt-working-memory").value = initial.working_memory || ageMode;
  document.getElementById("apt-pattern").value = initial.pattern_recognition || ageMode;
  document.getElementById("apt-attention").value = initial.attention || ageMode;
  document.getElementById("apt-speed").value = initial.processing_speed || ageMode;
  document.getElementById("message").textContent = "Choose the starting challenge that feels right for each area.";
}

function continueToDashboard(age) {
  if (age != null) localStorage.setItem("user_age", String(age));
  window.location.href = "dashboard.html";
}

function startRequiredAssessment() {
  sessionStorage.removeItem("neurocare_assessment_report");
  sessionStorage.removeItem("neurocare_assessment_game_run");
  sessionStorage.removeItem("neurocare_initial_assessment_ready");
  window.location.href = "initial-assessment.html";
}

async function authenticate(email, password) {
  const response = await fetch(`${API_BASE_URL}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password })
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Login failed. Check your email and password.");

  const normalizedEmail = email.trim().toLowerCase();
  const previousEmail = (localStorage.getItem("username") || "").trim().toLowerCase();
  if (previousEmail && previousEmail !== normalizedEmail) {
    localStorage.removeItem("initial_assessment_complete");
    localStorage.removeItem("assessment_in_progress");
  }
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("username", email);
  if (data.age == null) {
    showAgePanel();
    return;
  }
  startRequiredAssessment();
}

async function login() {
  const email = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const message = document.getElementById("message");
  if (!email || !password) {
    message.textContent = "Enter your email and password.";
    return;
  }

  message.textContent = "Logging in…";
  try {
    await authenticate(email, password);
  } catch (error) {
    console.error("Login error:", error);
    message.textContent = error.message;
  }
}

async function registerAccount() {
  const email = document.getElementById("register-email").value.trim();
  const password = document.getElementById("register-password").value;
  const age = Number(document.getElementById("register-age").value);
  const message = document.getElementById("message");

  if (!email || !password || !Number.isInteger(age) || age < 1 || age > 120) {
    message.textContent = "Enter a valid email, a password of at least 8 characters, and an age from 1 to 120.";
    return;
  }

  message.textContent = "Creating your account…";
  try {
    const response = await fetch(`${API_BASE_URL}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, age })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not create the account.");
    await authenticate(email, password);
  } catch (error) {
    console.error("Registration error:", error);
    message.textContent = error.message;
  }
}

async function saveMissingAge() {
  const age = Number(document.getElementById("login-age").value);
  const message = document.getElementById("message");
  const token = localStorage.getItem("access_token");

  if (!Number.isInteger(age) || age < 1 || age > 120) {
    message.textContent = "Enter an age from 1 to 120.";
    return;
  }
  if (!token) {
    message.textContent = "Your login expired. Please log in again.";
    showAuthPanel("login");
    return;
  }

  message.textContent = "Saving your age…";
  try {
    const response = await fetch(`${API_BASE_URL}/users/me/age`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ age })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not save your age.");
    startRequiredAssessment();
  } catch (error) {
    console.error("Age update error:", error);
    message.textContent = error.message;
  }
}

async function saveAptitudeLevels() {
  const token = localStorage.getItem("access_token");
  const age = Number(localStorage.getItem("user_age")) || Number(document.getElementById("register-age").value) || 60;
  const aptitude_levels = {
    memory: document.getElementById("apt-memory").value,
    working_memory: document.getElementById("apt-working-memory").value,
    pattern_recognition: document.getElementById("apt-pattern").value,
    attention: document.getElementById("apt-attention").value,
    processing_speed: document.getElementById("apt-speed").value
  };
  const message = document.getElementById("message");
  if (!token) {
    message.textContent = "Please log in again to save your starting levels.";
    showAuthPanel("login");
    return;
  }
  message.textContent = "Saving your starting levels…";
  try {
    const response = await fetch(`${API_BASE_URL}/users/me/aptitudes`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(aptitude_levels)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not save your starting levels.");
    localStorage.setItem("aptitude_levels", JSON.stringify(data.aptitude_levels));
    continueToDashboard(age);
  } catch (error) {
    console.error("Aptitude preference save error:", error);
    message.textContent = error.message;
  }
}
