// refine-motion mock v1 — frontend logic
// Push-to-talk → upload audio → display agent reply → speak it via SpeechSynthesis.

const $ = (sel) => document.querySelector(sel);

const state = {
  sessionId: null,
  status: "idle",
  recorder: null,
  chunks: [],
  audioStream: null,
};

// ----- DOM -----
const setupCard = $("#setup");
const sessionCard = $("#session");
const startForm = $("#start-form");
const transcriptEl = $("#transcript");
const statusPill = $("#status-pill");
const pttBtn = $("#ptt");
const pttLabel = pttBtn.querySelector(".ptt-label");
const textFallbackBtn = $("#text-fallback-btn");
const textForm = $("#text-form");
const textInput = $("#text-input");
const contractCard = $("#contract");
const contractBody = $("#contract-body");
const resultCard = $("#result");
const issueLink = $("#issue-link");

// ----- helpers -----
function setStatus(status) {
  state.status = status;
  statusPill.textContent = status;
  statusPill.className = "pill " + status;
  pttBtn.disabled = status === "submitted";
  textInput.disabled = status === "submitted";
}

function appendTurn(role, text) {
  const div = document.createElement("div");
  div.className = "turn " + role;
  const r = document.createElement("div");
  r.className = "role";
  r.textContent = role;
  const t = document.createElement("div");
  t.className = "text";
  t.textContent = text;
  div.appendChild(r);
  div.appendChild(t);
  transcriptEl.appendChild(div);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.0;
    u.pitch = 1.0;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  } catch (e) {
    console.warn("TTS failed", e);
  }
}

function renderContract(c) {
  if (!c) {
    contractCard.classList.add("hidden");
    return;
  }
  contractBody.innerHTML = "";
  const title = document.createElement("p");
  title.innerHTML = `<strong>${escapeHtml(c.title || "(no title)")}</strong>`;
  contractBody.appendChild(title);

  const jsLabel = document.createElement("div");
  jsLabel.className = "label";
  jsLabel.textContent = "Job statement";
  contractBody.appendChild(jsLabel);
  const js = document.createElement("p");
  js.textContent = c.job_statement || "";
  contractBody.appendChild(js);

  const biLabel = document.createElement("div");
  biLabel.className = "label";
  biLabel.textContent = "Behavioral intent";
  contractBody.appendChild(biLabel);
  const ul = document.createElement("ul");
  for (const b of c.behavioral_intent || []) {
    const li = document.createElement("li");
    li.textContent = b;
    ul.appendChild(li);
  }
  contractBody.appendChild(ul);
  contractCard.classList.remove("hidden");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

// ----- API -----
async function startSession(owner, repo, issueNumber) {
  const r = await fetch("/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ owner, repo, issue_number: issueNumber || null }),
  });
  if (!r.ok) throw new Error(`start failed: ${r.status} ${await r.text()}`);
  return r.json();
}

async function sendTurn({ audioBlob, text }) {
  const fd = new FormData();
  if (audioBlob) fd.append("audio", audioBlob, "turn.webm");
  if (text) fd.append("text", text);
  const r = await fetch(`/sessions/${state.sessionId}/turn`, {
    method: "POST",
    body: fd,
  });
  if (!r.ok) throw new Error(`turn failed: ${r.status} ${await r.text()}`);
  return r.json();
}

// ----- audio (PTT) -----
async function ensureMic() {
  if (state.audioStream) return state.audioStream;
  state.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  return state.audioStream;
}

async function startRecording() {
  const stream = await ensureMic();
  state.chunks = [];
  state.recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
  state.recorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) state.chunks.push(e.data);
  };
  state.recorder.start();
  pttBtn.classList.add("recording");
  pttLabel.textContent = "release to send";
}

async function stopRecording() {
  if (!state.recorder) return null;
  return new Promise((resolve) => {
    state.recorder.onstop = () => {
      const blob = new Blob(state.chunks, { type: "audio/webm" });
      pttBtn.classList.remove("recording");
      pttLabel.textContent = "hold to speak";
      resolve(blob);
    };
    state.recorder.stop();
  });
}

async function handlePttRelease() {
  if (!state.recorder) return;
  const blob = await stopRecording();
  if (!blob || blob.size < 1000) {
    appendTurn("agent", "(no audio captured — hold the button longer)");
    return;
  }
  pttBtn.disabled = true;
  pttLabel.textContent = "transcribing…";
  try {
    const result = await sendTurn({ audioBlob: blob });
    handleTurnResult(result);
  } catch (e) {
    appendTurn("agent", `(error: ${e.message})`);
  } finally {
    pttBtn.disabled = state.status === "submitted";
    pttLabel.textContent = "hold to speak";
  }
}

function handleTurnResult(result) {
  if (result.user_text) appendTurn("user", result.user_text);
  appendTurn("agent", result.agent_text);
  speak(result.agent_text);
  setStatus(result.status);
  if (result.contract) renderContract(result.contract);
  if (result.issue_url) {
    resultCard.classList.remove("hidden");
    issueLink.href = result.issue_url;
    issueLink.textContent = result.issue_url;
  }
}

// ----- wire-up -----
startForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const owner = $("#owner").value.trim();
  const repo = $("#repo").value.trim();
  const issueNumber = $("#issue-number").value.trim();

  const submitBtn = startForm.querySelector("button");
  submitBtn.disabled = true;
  submitBtn.textContent = "loading…";
  try {
    const data = await startSession(owner, repo, issueNumber);
    state.sessionId = data.session_id;
    setupCard.classList.add("hidden");
    sessionCard.classList.remove("hidden");
    appendTurn("agent", data.agent_text);
    speak(data.agent_text);
    setStatus(data.status);
    pttBtn.disabled = false;
  } catch (err) {
    alert("Could not start session:\n" + err.message);
    submitBtn.disabled = false;
    submitBtn.textContent = "Start session";
  }
});

// PTT — mouse + touch
pttBtn.addEventListener("mousedown", startRecording);
pttBtn.addEventListener("mouseup", handlePttRelease);
pttBtn.addEventListener("mouseleave", () => {
  if (state.recorder && state.recorder.state === "recording") handlePttRelease();
});
pttBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
pttBtn.addEventListener("touchend", (e) => { e.preventDefault(); handlePttRelease(); });

// Text fallback
textFallbackBtn.addEventListener("click", () => {
  textForm.classList.toggle("hidden");
  if (!textForm.classList.contains("hidden")) textInput.focus();
});
textForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = textInput.value.trim();
  if (!text) return;
  textInput.value = "";
  textInput.disabled = true;
  try {
    const result = await sendTurn({ text });
    handleTurnResult(result);
  } catch (err) {
    appendTurn("agent", `(error: ${err.message})`);
  } finally {
    textInput.disabled = state.status === "submitted";
  }
});
