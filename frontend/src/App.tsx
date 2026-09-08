import { useEffect } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import Home from "@/pages/Home";
import Dashboard from "@/pages/Dashboard";
import Briefing from "@/pages/Briefing";
import LiveMonitor from "@/pages/LiveMonitor";
import Simulator from "@/pages/Simulator";

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  const location = useLocation();
  useEffect(() => { window.scrollTo({ top: 0, left: 0, behavior: "auto" }); }, [location.pathname]);
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/dashboard/:evaluationId" element={<Dashboard />} />
      <Route path="/briefing/:evaluationId" element={<Briefing />} />
      <Route path="/live" element={<LiveMonitor />} />
      <Route path="/simulator" element={<Simulator />} />
    </Routes>
  );
}
