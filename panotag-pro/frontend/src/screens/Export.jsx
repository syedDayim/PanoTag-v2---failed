import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Export() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [path, setPath] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.projects().then((ps) => {
      setProjects(ps);
      if (ps.length && !projectId) setProjectId(String(ps[0].id));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = (e) => {
    e.preventDefault();
    setErr("");
    setMsg("");
    api
      .exportProject(Number(projectId), path.trim())
      .then((r) => setMsg(`Wrote ${r.row_count} rows to ${r.path}`))
      .catch((er) => setErr(String(er.message)));
  };

  return (
    <div className="p-8 max-w-3xl">
      <h2 className="text-xl font-semibold text-pano-accent mb-4">Export</h2>
      <p className="text-pano-muted text-sm mb-6">
        Export all tags for the project to an Excel file (column order matches the
        PanoTag spec).
      </p>
      <form onSubmit={run} className="space-y-4">
        <div className="flex flex-wrap gap-3 items-center">
          <label className="text-sm text-pano-muted">Project</label>
          <select
            className="bg-[#0d1018] border border-[#2a3045] rounded px-3 py-2 text-sm"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-pano-muted mb-1">Output .xlsx path</label>
          <input
            className="w-full bg-[#0d1018] border border-[#2a3045] rounded px-3 py-2 text-sm"
            placeholder="e.g. C:\exports\site_tags.xlsx"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
        </div>
        <button
          type="submit"
          disabled={!projectId || !path.trim()}
          className="px-4 py-2 rounded bg-[#2a3045] text-pano-accent text-sm disabled:opacity-40"
        >
          Export
        </button>
      </form>
      {msg && <p className="mt-4 text-green-400 text-sm">{msg}</p>}
      {err && <p className="mt-4 text-red-400 text-sm">{err}</p>}
    </div>
  );
}
