/** REST client — dev: same-origin + Vite proxy. file:// (Electron prod): hits backend directly. */

function baseUrl() {
  if (typeof window !== "undefined" && window.location?.protocol === "file:") {
    return "http://127.0.0.1:8756";
  }
  return import.meta.env.VITE_API_BASE || "";
}

async function request(path, options = {}) {
  const prefix = baseUrl();
  const url = path.startsWith("http") ? path : `${prefix}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const msg = data?.detail ?? data?.message ?? res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export const api = {
  health: () => request("/api/health"),
  gpu: () => request("/api/gpu"),
  projects: () => request("/api/projects"),
  createProject: (name, folderPath) =>
    request("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name, folder_path: folderPath }),
    }),
  deleteProject: (id) =>
    request(`/api/projects/${id}`, { method: "DELETE" }),
  scan: (projectId) =>
    request(`/api/projects/${projectId}/scan`, { method: "POST" }),
  photos: (projectId) => request(`/api/projects/${projectId}/photos`),
  tags: (photoId) => request(`/api/photos/${photoId}/tags`),
  processStatus: () => request("/api/process/status"),
  startProcess: (projectId, photoIds = null) =>
    request(`/api/projects/${projectId}/process`, {
      method: "POST",
      body: JSON.stringify({ photo_ids: photoIds }),
    }),
  cancelProcess: () =>
    request("/api/process/cancel", { method: "POST" }),
  exportProject: (projectId, outputPath) =>
    request(`/api/projects/${projectId}/export`, {
      method: "POST",
      body: JSON.stringify({ output_path: outputPath }),
    }),
  updateTag: (tagId, body) =>
    request(`/api/tags/${tagId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};
