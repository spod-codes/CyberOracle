import { useEffect, useState } from "react";
import { FileText, House, LayoutDashboard } from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";

export default function AppHeader() {
  const { evaluationId: paramEvaluationId } = useParams();
  const location = useLocation();
  const [lastEvaluationId, setLastEvaluationId] = useState(() => window.localStorage.getItem("cyber-oracle-last-evaluation"));
  const evaluationId = paramEvaluationId ?? lastEvaluationId;
  const dashboardPath = evaluationId ? `/dashboard/${evaluationId}` : "/";
  const briefingPath = evaluationId ? `/briefing/${evaluationId}` : "/";



  useEffect(() => {
    if (paramEvaluationId) {
      window.localStorage.setItem("cyber-oracle-last-evaluation", paramEvaluationId);
      setLastEvaluationId(paramEvaluationId);
    }
  }, [paramEvaluationId]);

  const dockItem = "dock-item";
  const disabledDockItem = `${dockItem} dock-item-disabled`;
  return <nav className="floating-dock" aria-label="Primary navigation" data-testid="primary-navigation">
      <Link to="/" className="dock-brand" data-testid="dock-brand-link"><span>CYBER ORACLE</span><b>CO</b></Link><span className="dock-divider" />
      <Link to="/" className={`${dockItem} ${location.pathname === "/" ? "dock-item-active" : ""}`} data-label="Home / Ingest" title="Home and CSV ingestion" data-testid="nav-ingest-link"><House size={18} /></Link>
      <span className="dock-divider" />
      <Link to={dashboardPath} className={evaluationId ? `${dockItem} ${location.pathname.startsWith("/dashboard") ? "dock-item-active" : ""}` : disabledDockItem} data-label="Dashboard" title={evaluationId ? "Open active dashboard" : "Run an evaluation to open the dashboard"} data-testid="nav-dashboard-link" aria-disabled={!evaluationId}><LayoutDashboard size={18} /></Link>
      <Link to={briefingPath} className={evaluationId ? `${dockItem} ${location.pathname.startsWith("/briefing") ? "dock-item-active" : ""}` : disabledDockItem} data-label="Briefing" title={evaluationId ? "Open printable briefing" : "Run an evaluation to create a briefing"} data-testid="nav-briefing-link" aria-disabled={!evaluationId}><FileText size={18} /></Link>
    </nav>;
}
