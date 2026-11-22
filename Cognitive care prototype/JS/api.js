// All game pages load this shared file. Require the signed-in user to finish
// the one-time Level 1 baseline before any game can open.
if (
  localStorage.getItem("access_token") &&
  localStorage.getItem("initial_assessment_complete") !== "true"
) {
  window.location.replace("../initial-assessment.html");
}

const API_BASE_URL = "http://127.0.0.1:8000";

// Assessment games call this after recording their one-level result. The
// assessment page then launches the next game in its randomized sequence.
function isAssessmentGameRound() {
  return new URLSearchParams(window.location.search).get("assessment") === "1";
}

if (isAssessmentGameRound()) {
  window.addEventListener("DOMContentLoaded", () => {
    const notice = document.createElement("div");
    notice.textContent = "Assessment: finish one level. Your result will be saved, then the next project game will open.";
    notice.setAttribute("role", "status");
    notice.style.cssText = "position:fixed;z-index:9999;top:10px;left:50%;transform:translateX(-50%);width:max-content;max-width:calc(100vw - 24px);padding:9px 14px;border-radius:10px;background:#173b5b;color:#fff;font:600 13px/1.4 Segoe UI,Arial,sans-serif;box-shadow:0 4px 16px #0002;text-align:center";
    document.body.appendChild(notice);
  }, { once: true });
}

function finishAssessmentGame(gameName, score) {
  if (!isAssessmentGameRound()) return false;
  const knownGames = new Set([
    "memory_card", "stroop_test", "number_sequence",
    "reaction_time", "sequence_recall"
  ]);
  if (!knownGames.has(gameName)) {
    console.error("Unknown assessment game:", gameName);
    return false;
  }
  try {
    const run = JSON.parse(sessionStorage.getItem("neurocare_assessment_game_run") || "null");
    if (run && Number.isFinite(Number(score))) {
      run.gameScores = run.gameScores || {};
      run.gameScores[gameName] = Math.max(0, Math.min(100, Number(score)));
      sessionStorage.setItem("neurocare_assessment_game_run", JSON.stringify(run));
    }
  } catch (error) {
    console.warn("Could not store this assessment game score:", error);
  }
  window.location.replace(`../initial-assessment.html?assessmentRoundDone=1&game=${encodeURIComponent(gameName)}`);
  return true;
}

const BACKEND_GAME_NAMES = new Set([
  "memory_card",
  "sequence_memory",
  "number_sequence",
  "sequence_recall",
  "stroop_test",
  "pattern_recognition",
  "reaction_time"
]);

function makeBackendGameResult(result) {
  if (!result || !BACKEND_GAME_NAMES.has(result.game_name)) {
    throw new Error(`Unsupported game_name: ${result?.game_name ?? "missing"}`);
  }

  const score = Number(result.score);
  const accuracy = Number(result.accuracy);
  const completionTime = Number(result.completion_time_seconds);
  const errors = Number(result.errors);
  const level = Number(result.level ?? 1);
  const maxLevel = Number(result.max_level ?? 10);
  const mode = result.mode ?? "easy";

  if (![score, accuracy, completionTime, errors, level, maxLevel].every(Number.isFinite)) {
    throw new Error("Game result contains a missing or invalid number.");
  }
  if (!["easy", "medium", "hard"].includes(mode)) {
    throw new Error(`Unsupported game mode: ${mode}`);
  }

  return {
    game_name: result.game_name,
    score: Math.min(100, Math.max(0, score)),
    accuracy: Math.min(100, Math.max(0, accuracy)),
    completion_time_seconds: Math.max(0.1, completionTime),
    errors: Math.max(0, Math.floor(errors)),
    mode,
    level: Math.max(1, Math.floor(level)),
    max_level: Math.max(1, Math.floor(maxLevel))
  };
}

async function saveGameResultToBackend(result) {
  const token =
    sessionStorage.getItem("access_token") ||
    localStorage.getItem("access_token");

  if (!token) {
    console.error("No access token found. Log in through the frontend first.");
    return false;
  }

  let payload;
  try {
    payload = makeBackendGameResult(result);
  } catch (error) {
    console.error("Invalid backend game result:", error);
    return false;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/results`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    });

    const body = await response.json();

    if (!response.ok) {
      console.error("Save failed:", response.status, body);
      return false;
    }

    if (body.level_recommendation) {
      localStorage.setItem(
        `level_recommendation:${payload.game_name}`,
        JSON.stringify(body.level_recommendation)
      );
    }
    console.log("Backend accepted game result and level recommendation:", body);
    return body;
  } catch (error) {
    console.error("Could not reach backend:", error);
    return false;
  }
}

async function getRecommendedGameLevel(gameName) {
  const token = sessionStorage.getItem("access_token") || localStorage.getItem("access_token");
  if (!token || !BACKEND_GAME_NAMES.has(gameName)) return null;

  try {
    const response = await fetch(
      `${API_BASE_URL}/recommendation/level/${encodeURIComponent(gameName)}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) throw new Error(`Recommendation request failed (${response.status}).`);
    return await response.json();
  } catch (error) {
    console.warn("Could not load adaptive level recommendation:", error);
    return null;
  }
}


const PERFORMANCE_HISTORY_KEY = `game-performance-history:${window.location.pathname}`;

function readPerformanceHistory() {
  try {
    return JSON.parse(sessionStorage.getItem(PERFORMANCE_HISTORY_KEY) || "[]");
  } catch (error) {
    console.warn("Could not read this game's performance history:", error);
    return [];
  }
}

function createPerformancePanel() {
  let panel = document.getElementById("game-performance-panel");
  if (panel) return panel;

  if (!document.getElementById("game-performance-panel-style")) {
    const style = document.createElement("style");
    style.id = "game-performance-panel-style";
    style.textContent = `
      #game-performance-panel { position:fixed; z-index:2147483647; top:24px; right:24px; bottom:auto; width:min(300px,calc(100vw - 32px)); max-height:68vh; display:flex; flex-direction:column; overflow:hidden; color:#20324d; background:#fff; border:1px solid #d8e1ef; border-radius:14px; box-shadow:0 10px 34px #0c1c3633; font-family:system-ui,"Segoe UI",Arial,sans-serif; }
      #game-performance-panel .performance-header { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:12px 14px; border-bottom:1px solid #e3eaf4; }
      #game-performance-panel h2 { margin:0; color:#1e3d59; font-size:1rem; }
      #game-performance-panel .performance-clear { border:0; padding:6px 9px; border-radius:8px; background:#edf2f9; color:#344762; font:inherit; cursor:pointer; }
      #game-performance-panel .performance-history { overflow:auto; padding:10px; }
      #game-performance-panel .performance-entry { margin-bottom:9px; padding:11px; border:1px solid #e1e8f2; border-radius:10px; background:#f8faff; }
      #game-performance-panel .performance-entry h3 { margin:0 0 5px; color:#1e3d59; font-size:.94rem; }
      #game-performance-panel .performance-entry p { margin:0 0 8px; color:#52617b; font-size:.82rem; line-height:1.35; }
      #game-performance-panel .performance-stats { display:grid; gap:6px; }
      #game-performance-panel .performance-stat { display:flex; justify-content:space-between; gap:8px; padding:6px 8px; border-radius:7px; background:#eef3fa; font-size:.8rem; }
      #game-performance-panel .performance-stat strong { text-align:right; }
      @media (max-width:700px) { #game-performance-panel { top:auto; left:auto; right:12px; bottom:12px; width:min(290px,calc(100vw - 24px)); max-height:36vh; } }
    `;
    document.head.appendChild(style);
  }

  panel = document.createElement("aside");
  panel.id = "game-performance-panel";
  panel.setAttribute("aria-label", "Level performance history");
  panel.innerHTML = `<div class="performance-header"><h2>Level performance</h2><button class="performance-clear" type="button">Clear</button></div><div class="performance-history" aria-live="polite"></div>`;
  panel.querySelector(".performance-clear").addEventListener("click", () => {
    sessionStorage.removeItem(PERFORMANCE_HISTORY_KEY);
    panel.querySelector(".performance-history").replaceChildren();
  });
  document.documentElement.appendChild(panel);
  return panel;
}

function renderPerformanceEntry(history, item) {
  const entry = document.createElement("section");
  entry.className = "performance-entry";
  const heading = document.createElement("h3");
  heading.textContent = item.title;
  const description = document.createElement("p");
  description.textContent = item.message;
  const statsBox = document.createElement("div");
  statsBox.className = "performance-stats";
  Object.entries(item.stats || {}).forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "performance-stat";
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = String(value);
    row.append(labelNode, valueNode);
    statsBox.appendChild(row);
  });
  entry.append(heading, description, statsBox);
  history.appendChild(entry);
}

function restorePerformanceHistory() {
  const entries = readPerformanceHistory();
  if (!entries.length) return;
  const panel = createPerformancePanel();
  const history = panel.querySelector(".performance-history");
  history.replaceChildren();
  entries.forEach(item => renderPerformanceEntry(history, item));
  history.scrollTop = 0;
}

function showGamePerformancePopup({
  title = "Level complete",
  message = "Here is your performance for this level.",
  stats = {}
} = {}) {
  const entries = readPerformanceHistory();
  entries.unshift({ title, message, stats });
  const trimmedEntries = entries.slice(0, 30);
  try {
    sessionStorage.setItem(PERFORMANCE_HISTORY_KEY, JSON.stringify(trimmedEntries));
  } catch (error) {
    console.warn("Could not save this game's performance history:", error);
  }
  restorePerformanceHistory();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", restorePerformanceHistory, { once: true });
} else {
  restorePerformanceHistory();
}
