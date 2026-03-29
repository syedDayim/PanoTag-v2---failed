import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useWs } from "../WsContext.jsx";

export default function Processing() {
  const { connected, lastMessage, logLines, gpu, send, clearLogs } = useWs();
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.projects().then((ps) => {
      setProjects(ps);
      if (ps.length && !projectId) setProjectId(String(ps[0].id));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setInterval(() => {
      api.processStatus().then((s) => setRunning(!!s.running));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (lastMessage?.type === "process_finished" || lastMessage?.type === "cancelled") {
      api.processStatus().then((s) => setRunning(!!s.running));
    }
  }, [lastMessage]);

  const start = () => {
    setErr("");
    clearLogs();
    api
      .startProcess(Number(projectId), null)
      .then(() => setRunning(true))
      .catch((e) => setErr(String(e.message)));
  };

  const cancel = () => {
    api.cancelProcess().catch(() => {});
    send({ command: "cancel" });
  };

  return (
    <div className="p-8 max-w-4xl flex flex-col gap-6">
      <h2 className="text-xl font-semibold text-pano-accent">Processing</h2>
      <p className="text-pano-muted text-sm">
        Start detection for queued / errored photos. Live log and GPU stats stream over
        WebSocket (connection:{" "}
        <span className={connected ? "text-green-400" : "text-red-400"}>
          {connected ? "live" : "reconnecting…"}
        </span>
        ).
      </p>

      <div className="flex flex-wrap gap-3 items-center">
        <select
          className="bg-[#0d1018] border border-[#2a3045] rounded px-3 py-2 text-sm text-[#e8eaf0]"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!projectId || running}
          onClick={start}
          className="px-4 py-2 rounded bg-[#2a3045] text-pano-accent text-sm disabled:opacity-40"
        >
          Start queue
        </button>
        <button
          type="button"
          disabled={!running}
          onClick={cancel}
          className="px-4 py-2 rounded border border-[#553333] text-red-300 text-sm disabled:opacity-40"
        >
          Cancel
        </button>
      </div>

      {err && <p className="text-red-400 text-sm">{err}</p>}

      {gpu && (
        <div className="flex gap-6 text-sm text-pano-muted">
          <span>
            GPU: <span className="text-pano-accent">{gpu.gpu_util}%</span>
          </span>
          <span>
            VRAM: {gpu.mem_used_mb} / {gpu.mem_total_mb} MB
          </span>
        </div>
      )}

      {lastMessage && (
        <div className="text-xs text-pano-muted font-mono break-all">
          Last event: {lastMessage.type}
          {lastMessage.photo_id != null && ` · photo ${lastMessage.photo_id}`}
        </div>
      )}

      <div className="flex-1 min-h-[280px] rounded-lg bg-[#0a0c10] border border-[#2a3045] p-3 font-mono text-xs text-[#b8c0d4] overflow-y-auto max-h-[420px]">
        {logLines.length === 0 && (
          <span className="text-pano-muted">Logs from the detector appear here…</span>
        )}
        {logLines.map((line, i) => (
          <div key={`${i}-${line.slice(0, 24)}`}>{line}</div>
        ))}
      </div>
    </div>
  );
}
