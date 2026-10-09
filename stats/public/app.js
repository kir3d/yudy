const accessView = document.querySelector("#accessView");
const dashboard = document.querySelector("#dashboard");
const codeForm = document.querySelector("#codeForm");
const codeInput = document.querySelector("#codeInput");
const verifyButton = document.querySelector("#verifyButton");
const resendButton = document.querySelector("#resendButton");
const accessStatus = document.querySelector("#accessStatus");
const logoutButton = document.querySelector("#logoutButton");

let countdownTimer;

function setStatus(message, isError = false) {
  accessStatus.textContent = message;
  accessStatus.classList.toggle("error", isError);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || "Request failed");
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function startCountdown(seconds = 60) {
  clearInterval(countdownTimer);
  let remaining = seconds;
  resendButton.disabled = true;
  resendButton.textContent = `Send another code in ${remaining}s`;
  countdownTimer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(countdownTimer);
      resendButton.disabled = false;
      resendButton.textContent = "Send another code";
    } else {
      resendButton.textContent = `Send another code in ${remaining}s`;
    }
  }, 1000);
}

async function requestCode() {
  resendButton.disabled = true;
  setStatus("Requesting a secure code…");
  try {
    const result = await api("/api/auth/request", { method: "POST", body: "{}" });
    if (result.authenticated) return loadDashboard();
    setStatus("A six-digit access code has been sent. It expires in 10 minutes.");
    startCountdown(60);
    codeInput.focus();
  } catch (error) {
    if (error.status === 429) {
      setStatus("A code was sent recently. Enter it below.");
      startCountdown(error.data.retryAfter || 60);
      codeInput.focus();
      return;
    }
    setStatus(error.message, true);
    resendButton.disabled = false;
  }
}

function number(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function linePath(values, width, height, padding = 3) {
  const max = Math.max(1, ...values);
  const step = values.length > 1 ? (width - padding * 2) / (values.length - 1) : 0;
  return values.map((value, index) => {
    const x = padding + index * step;
    const y = height - padding - (value / max) * (height - padding * 2);
    return `${index ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
}

function drawMini(id, values, color) {
  const svg = document.querySelector(id);
  const path = linePath(values, 240, 64, 4);
  svg.innerHTML = `
    <path d="M4 60H236" stroke="#263635" stroke-width="1"/>
    <path d="${path}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/>
  `;
}

function drawActivity(series) {
  const svg = document.querySelector("#activityChart");
  const width = 1000;
  const height = 260;
  const padding = 18;
  const paths = [
    [series.map((row) => row.accounts), "#0bb7c3"],
    [series.map((row) => row.aiRequests), "#5b83ff"],
    [series.map((row) => row.processedAssets), "#a86cff"],
  ];
  const grid = [0, 1, 2, 3, 4].map((index) => {
    const y = padding + index * ((height - padding * 2) / 4);
    return `<path d="M${padding} ${y}H${width - padding}" stroke="#263635" stroke-width="1"/>`;
  }).join("");
  svg.innerHTML = grid + paths.map(([values, color]) =>
    `<path d="${linePath(values, width, height, padding)}" fill="none" stroke="${color}" stroke-width="3" vector-effect="non-scaling-stroke"/>`,
  ).join("");
}

function renderStats(data) {
  document.querySelector("#accountsTotal").textContent = number(data.totals.registeredAccounts);
  document.querySelector("#aiTotal").textContent = number(data.totals.aiRequests);
  document.querySelector("#assetsTotal").textContent = number(data.totals.processedAssets);
  document.querySelector("#updatedAt").textContent = new Date(data.updatedAt).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  const series = data.series;
  drawMini("#accountsMini", series.map((row) => row.accounts), "#0bb7c3");
  drawMini("#aiMini", series.map((row) => row.aiRequests), "#5b83ff");
  drawMini("#assetsMini", series.map((row) => row.processedAssets), "#a86cff");
  drawActivity(series);
  const dateOptions = { month: "short", day: "numeric" };
  document.querySelector("#startDate").textContent = new Date(`${series[0].day}T00:00:00`).toLocaleDateString([], dateOptions);
  document.querySelector("#endDate").textContent = new Date(`${series.at(-1).day}T00:00:00`).toLocaleDateString([], dateOptions);
}

async function loadDashboard() {
  try {
    const data = await api("/api/stats");
    renderStats(data);
    accessView.hidden = true;
    dashboard.hidden = false;
    document.body.classList.add("dashboard-open");
    logoutButton.hidden = false;
    document.title = "YUDY // Product Stats";
    return true;
  } catch (error) {
    if (error.status !== 401) setStatus(error.message, true);
    return false;
  }
}

codeInput.addEventListener("input", () => {
  codeInput.value = codeInput.value.replace(/\D/g, "").slice(0, 6);
});

codeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (codeInput.value.length !== 6) return setStatus("Enter all six digits.", true);
  verifyButton.disabled = true;
  setStatus("Checking code…");
  try {
    await api("/api/auth/verify", { method: "POST", body: JSON.stringify({ code: codeInput.value }) });
    await loadDashboard();
  } catch (error) {
    setStatus(error.message, true);
    codeInput.select();
  } finally {
    verifyButton.disabled = false;
  }
});

resendButton.addEventListener("click", requestCode);
logoutButton.addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST", body: "{}" }).catch(() => {});
  window.location.reload();
});

(async function init() {
  if (!(await loadDashboard())) await requestCode();
})();
