import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./screens/Dashboard.jsx";
import BatchImport from "./screens/BatchImport.jsx";
import Processing from "./screens/Processing.jsx";
import Review from "./screens/Review.jsx";
import Export from "./screens/Export.jsx";
import Settings from "./screens/Settings.jsx";

const screens = [
  { path: "/", name: "Dashboard", el: <Dashboard /> },
  { path: "/import", name: "Batch import", el: <BatchImport /> },
  { path: "/processing", name: "Processing", el: <Processing /> },
  { path: "/review", name: "Review", el: <Review /> },
  { path: "/export", name: "Export", el: <Export /> },
  { path: "/settings", name: "Settings", el: <Settings /> },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-pano-bg text-[#e8eaf0]">
      <header className="bg-pano-panel border-b border-[#2a3045] px-6 py-4 flex items-center justify-between">
        <div className="font-bold tracking-tight text-pano-accent text-lg">
          PANOTAG PRO
        </div>
        <nav className="flex flex-wrap gap-2 text-sm">
          {screens.map((s) => (
            <NavLink
              key={s.path}
              to={s.path}
              className={({ isActive }) =>
                `px-3 py-1 rounded ${isActive ? "bg-[#2a3045] text-pano-accent" : "text-pano-muted hover:text-[#e8eaf0]"}`
              }
            >
              {s.name}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1">
        <Routes>
          {screens.map((s) => (
            <Route key={s.path} path={s.path} element={s.el} />
          ))}
        </Routes>
      </main>
    </div>
  );
}
