/**
 * Electron main: optional dev URL, or built Vite assets.
 * Spawns FastAPI (uvicorn) unless PANOTAG_SKIP_BACKEND=1 (e.g. you run uvicorn yourself).
 */
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const DEV_URL = process.env.PANOTAG_VITE_URL || "http://127.0.0.1:5173";
const BACKEND_PORT = process.env.PANOTAG_PORT || "8756";
const BACKEND_HOST = "127.0.0.1";
const isDev =
  process.env.PANOTAG_DEV === "1" || !app.isPackaged;

const backendRoot = path.join(__dirname, "..");

let backendProc = null;

function waitForHealth(maxMs = 90000) {
  const url = `http://${BACKEND_HOST}:${BACKEND_PORT}/api/health`;
  const start = Date.now();
  return new Promise((resolve, reject) => {
    function tryOnce() {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve();
          return;
        }
        schedule();
      });
      req.on("error", () => schedule());
    }
    function schedule() {
      if (Date.now() - start > maxMs) {
        reject(new Error("Backend health check timed out"));
        return;
      }
      setTimeout(tryOnce, 400);
    }
    tryOnce();
  });
}

function startBackend() {
  if (process.env.PANOTAG_SKIP_BACKEND === "1") {
    return Promise.resolve();
  }
  const python = process.env.PANOTAG_PYTHON || "python";
  backendProc = spawn(
    python,
    [
      "-m",
      "uvicorn",
      "backend.main:app",
      "--host",
      BACKEND_HOST,
      "--port",
      BACKEND_PORT,
    ],
    {
      cwd: backendRoot,
      env: { ...process.env },
      stdio: "inherit",
    }
  );
  backendProc.on("error", (err) => {
    console.error("Failed to spawn backend:", err);
  });
  return waitForHealth();
}

function stopBackend() {
  if (backendProc && !backendProc.killed) {
    try {
      if (process.platform === "win32") {
        spawn("taskkill", ["/pid", String(backendProc.pid), "/f", "/t"]);
      } else {
        backendProc.kill("SIGTERM");
      }
    } catch {
      /* ignore */
    }
    backendProc = null;
  }
}

async function createWindow() {
  if (process.env.PANOTAG_SKIP_BACKEND !== "1") {
    try {
      await startBackend();
    } catch (e) {
      console.error(e);
    }
  }

  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    backgroundColor: "#0d0f14",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (isDev) {
    win.loadURL(DEV_URL);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    const indexHtml = path.join(
      __dirname,
      "..",
      "frontend",
      "dist",
      "index.html"
    );
    win.loadFile(indexHtml);
  }
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  stopBackend();
  app.quit();
});
app.on("before-quit", () => stopBackend());
