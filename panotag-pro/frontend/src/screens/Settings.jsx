import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [gpu, setGpu] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e) => setErr(String(e.message)));
    api
      .gpu()
      .then(setGpu)
      .catch(() => setGpu({ error: "unavailable" }));
  }, []);

  return (
    <div className="p-8 max-w-3xl">
      <h2 className="text-xl font-semibold text-pano-accent mb-4">Settings</h2>
      <p className="text-pano-muted text-sm mb-6">
        API base is same-origin (Vite proxies <code className="text-pano-accent">/api</code>{" "}
        and <code className="text-pano-accent">/ws</code> to{" "}
        <code className="text-pano-accent">127.0.0.1:8756</code> in dev).
      </p>
      {err && <p className="text-red-400 text-sm mb-4">{err}</p>}
      <dl className="space-y-2 text-sm">
        <dt className="text-pano-muted">Health</dt>
        <dd className="font-mono text-[#e8eaf0]">
          {health ? JSON.stringify(health) : "—"}
        </dd>
        <dt className="text-pano-muted pt-2">GPU</dt>
        <dd className="font-mono text-[#e8eaf0]">
          {gpu ? JSON.stringify(gpu) : "—"}
        </dd>
      </dl>
    </div>
  );
}
