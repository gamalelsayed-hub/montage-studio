import { useEffect, useState } from "react";
import Home from "./pages/Home";
import ProjectPage from "./pages/Project";
import SettingsDialog from "./components/SettingsDialog";

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHashRoute();
  const [showSettings, setShowSettings] = useState(false);
  const projectMatch = hash.match(/^#\/p\/(.+)$/);

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/">
          🎬 Montage Studio
        </a>
        <button className="ghost" onClick={() => setShowSettings(true)}>
          ⚙️ الإعدادات
        </button>
      </header>
      <main>
        {projectMatch ? (
          <ProjectPage key={projectMatch[1]} projectId={decodeURIComponent(projectMatch[1])} />
        ) : (
          <Home onOpenSettings={() => setShowSettings(true)} />
        )}
      </main>
      {showSettings && <SettingsDialog onClose={() => setShowSettings(false)} />}
    </div>
  );
}
