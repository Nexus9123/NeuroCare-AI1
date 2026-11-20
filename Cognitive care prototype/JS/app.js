const API_BASE_URL = "http://127.0.0.1:8000";

function showAuthPanel(panel) {
  document.getElementById("login-panel").hidden = panel !== "login";
  document.getElementById("register-panel").hidden = panel !== "register";
  document.getElementById("age-panel").hidden = true;
  document.getElementById("message").textContent = "";
}

function showAgePanel() {
  document.getElementById("login-panel").hidden = true;
  document.getElementById("register-panel").hidden = true;
  document.getElementById("age-panel").hidden = false;
  document.getElementById("message").textContent =
    "Please enter your age once to finish setting up your account.";
}

function continueToDashboard(age) {
  if (age != null) localStorage.setItem("user_age", String(age));
  window.location.href = "dashboard.html";
}

async function authenticate(email, password) {
  const response = await fetch(`${API_BASE_URL}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password })
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Login failed. Check your email and password.");

  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("username", email);
  if (data.age == null) showAgePanel();
  else continueToDashboard(data.age);
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
    continueToDashboard(data.age);
  } catch (error) {
    console.error("Age update error:", error);
    message.textContent = error.message;
  }
}
