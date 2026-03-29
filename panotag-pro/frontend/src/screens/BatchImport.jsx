import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function BatchImport() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [photos, setPhotos] = useState([]);
  const [scanResult, setScanResult] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.projects().then((ps) => {
      setProjects(ps);
      if (ps.length && !projectId) setProjectId(String(ps[0].id));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial project only
  }, []);

  useEffect(() => {
    if (!projectId) return;
    api
      .photos(Number(projectId))
      .then(setPhotos)
      .catch(() => setPhotos([]));
  }, [projectId, scanResult]);

  const scan = () => {
    setErr("");
    setScanResult(null);
    api
      .scan(Number(projectId))
      .then(setScanResult)
      .catch((e) => setErr(String(e.message)));
  };

  return (
    <div className="p-8 max-w-4xl">
      <h2 className="text-xl font-semibold text-pano-accent mb-4">Batch import</h2>
      <p className="text-pano-muted text-sm mb-6">
        Scan the project folder for images (recursive). New files are added to the
        queue; existing paths are skipped.
      </p>

      <div className="flex flex-wrap gap-3 items-center mb-6">
        <label className="text-sm text-pano-muted">Project</label>
        <select
          className="bg-[#0d1018] border border-[#2a3045] rounded px-3 py-2 text-sm text-[#e8eaf0]"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          <option value="">—</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!projectId}
          onClick={scan}
          className="px-4 py-2 rounded bg-[#2a3045] text-pano-accent text-sm disabled:opacity-40"
        >
          Scan folder
        </button>
      </div>

      {err && (
        <p className="text-red-400 text-sm mb-4" role="alert">
          {err}
        </p>
      )}
      {scanResult && (
        <p className="text-sm text-pano-muted mb-4">
          Added <span className="text-pano-accent">{scanResult.added}</span>, skipped{" "}
          <span className="text-pano-accent">{scanResult.skipped}</span> (already known).
        </p>
      )}

      <div className="border border-[#2a3045] rounded-lg overflow-hidden max-h-[480px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-pano-panel sticky top-0">
            <tr className="text-left text-pano-muted">
              <th className="p-2 pl-3">File</th>
              <th className="p-2">Size</th>
              <th className="p-2 pr-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {photos.map((ph) => (
              <tr key={ph.id} className="border-t border-[#2a3045]">
                <td className="p-2 pl-3 truncate max-w-md">{ph.filename}</td>
                <td className="p-2 text-pano-muted">
                  {ph.width}×{ph.height}
                </td>
                <td className="p-2 pr-3 text-pano-muted">{ph.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {photos.length === 0 && (
          <p className="p-4 text-pano-muted text-sm">No photos — scan a project folder first.</p>
        )}
      </div>
    </div>
  );
}
