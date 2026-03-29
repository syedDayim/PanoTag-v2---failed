import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Review() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [photos, setPhotos] = useState([]);
  const [photoId, setPhotoId] = useState("");
  const [tags, setTags] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.projects().then((ps) => {
      setProjects(ps);
      if (ps.length && !projectId) setProjectId(String(ps[0].id));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!projectId) return;
    api
      .photos(Number(projectId))
      .then((list) => {
        setPhotos(list);
        setPhotoId(list.length ? String(list[0].id) : "");
      })
      .catch(() => {
        setPhotos([]);
        setPhotoId("");
      });
  }, [projectId]);

  useEffect(() => {
    if (!photoId) {
      setTags([]);
      return;
    }
    api
      .tags(Number(photoId))
      .then(setTags)
      .catch((e) => setErr(String(e.message)));
  }, [photoId]);

  return (
    <div className="p-8 max-w-5xl">
      <h2 className="text-xl font-semibold text-pano-accent mb-4">Review</h2>
      <p className="text-pano-muted text-sm mb-6">
        Inspect detected tags per photo. Box editing on canvas (Fabric.js) can be added
        on top of this data.
      </p>

      <div className="flex flex-wrap gap-3 mb-6 items-center">
        <select
          className="bg-[#0d1018] border border-[#2a3045] rounded px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => {
            setProjectId(e.target.value);
            setPhotoId("");
          }}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          className="bg-[#0d1018] border border-[#2a3045] rounded px-3 py-2 text-sm min-w-[200px]"
          value={photoId}
          onChange={(e) => setPhotoId(e.target.value)}
        >
          <option value="">— photo —</option>
          {photos.map((ph) => (
            <option key={ph.id} value={ph.id}>
              {ph.filename} ({ph.status})
            </option>
          ))}
        </select>
      </div>

      {err && <p className="text-red-400 text-sm mb-4">{err}</p>}

      <div className="border border-[#2a3045] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-pano-panel">
            <tr className="text-left text-pano-muted">
              <th className="p-2 pl-3">Tag</th>
              <th className="p-2">Conf</th>
              <th className="p-2">Box</th>
              <th className="p-2 pr-3">Pan/Tilt TL</th>
            </tr>
          </thead>
          <tbody>
            {tags.map((t) => (
              <tr key={t.id} className="border-t border-[#2a3045]">
                <td className="p-2 pl-3 max-w-xs truncate">{t.tag_name}</td>
                <td className="p-2 text-pano-muted">{t.confidence.toFixed(3)}</td>
                <td className="p-2 text-xs text-pano-muted whitespace-nowrap">
                  {Math.round(t.x1)},{Math.round(t.y1)} — {Math.round(t.x2)},
                  {Math.round(t.y2)}
                </td>
                <td className="p-2 pr-3 text-xs">
                  {t.pan_tl.toFixed(2)}, {t.tilt_tl.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {photoId && tags.length === 0 && (
          <p className="p-4 text-pano-muted text-sm">No tags for this photo yet.</p>
        )}
      </div>
    </div>
  );
}
