import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [err, setErr] = useState("");
  const [name, setName] = useState("New site");
  const [folder, setFolder] = useState("");

  const load = () => {
    setErr("");
    api
      .projects()
      .then(setProjects)
      .catch((e) => setErr(String(e.message)));
  };

  useEffect(() => {
    load();
  }, []);

  const create = (e) => {
    e.preventDefault();
    setErr("");
    api
      .createProject(name.trim(), folder.trim())
      .then(() => {
        setFolder("");
        load();
      })
      .catch((er) => setErr(String(er.message)));
  };

  return (
    <div className="p-8 max-w-4xl">
      <h2 className="text-xl font-semibold text-pano-accent mb-4">Projects</h2>
      <p className="text-pano-muted text-sm mb-6">
        Create a project pointing at a folder of panoramas, then use{" "}
        <Link className="text-pano-accent underline" to="/import">
          Batch import
        </Link>{" "}
        to scan files and{" "}
        <Link className="text-pano-accent underline" to="/processing">
          Processing
        </Link>{" "}
        to run detection.
      </p>

      <form
        onSubmit={create}
        className="flex flex-col sm:flex-row gap-3 mb-8 p-4 rounded-lg bg-pano-panel border border-[#2a3045]"
      >
        <input
          className="flex-1 bg-[#0d1018] border border-[#2a3045] rounded px-3 py-2 text-sm text-[#e8eaf0]"
          placeholder="Project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="flex-[2] bg-[#0d1018] border border-[#2a3045] rounded px-3 py-2 text-sm text-[#e8eaf0]"
          placeholder="Folder path (existing directory)"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
        />
        <button
          type="submit"
          className="px-4 py-2 rounded bg-[#2a3045] text-pano-accent text-sm font-medium hover:bg-[#343c55]"
        >
          Create project
        </button>
      </form>

      {err && (
        <p className="text-red-400 text-sm mb-4" role="alert">
          {err}
        </p>
      )}

      <ul className="space-y-2">
        {projects.map((p) => (
          <li
            key={p.id}
            className="flex flex-wrap items-center justify-between gap-2 p-3 rounded bg-[#0d1018] border border-[#2a3045]"
          >
            <div>
              <div className="font-medium text-[#e8eaf0]">{p.name}</div>
              <div className="text-xs text-pano-muted truncate max-w-xl">
                {p.folder_path}
              </div>
            </div>
            <div className="text-sm text-pano-muted">{p.photo_count} photos</div>
          </li>
        ))}
      </ul>
      {projects.length === 0 && !err && (
        <p className="text-pano-muted text-sm">No projects yet.</p>
      )}
    </div>
  );
}
