import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, Terminal } from "lucide-react";

import { apiPost } from "@/lib/api";
import type { KernelTestResult } from "@/lib/types";

export default function KernelTestConsole({ evaluationId }: { evaluationId: string }) {
  const [result, setResult] = useState<KernelTestResult | null>(null);
  const [visibleLines, setVisibleLines] = useState(0);
  const testMutation = useMutation({
    mutationFn: () => apiPost<KernelTestResult>(`/evaluations/${evaluationId}/kernel-test`, {}),
    onSuccess: (response) => { setResult(response); setVisibleLines(0); },
  });

  useEffect(() => {
    if (!result || visibleLines >= result.logs.length) return;
    const timer = window.setTimeout(() => setVisibleLines((count) => count + 1), 120);
    return () => window.clearTimeout(timer);
  }, [result, visibleLines]);

  return <div className="kernel-test" data-testid="kernel-test-console">
    <button className="kernel-test-button group relative overflow-hidden" onClick={() => testMutation.mutate()} disabled={testMutation.isPending} data-testid="test-in-kernel-button">
      <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]" />
      <Terminal size={14} className="group-hover:text-[#00e5ff] transition-colors" /> 
      {testMutation.isPending ? "testing…" : "test in kernel"}
    </button>
    {(result || testMutation.isPending || testMutation.isError) && (
      <div className="kernel-terminal relative overflow-hidden" data-testid="kernel-terminal-output" style={{ boxShadow: "0 0 20px rgba(0,229,255,0.1), inset 0 0 15px rgba(0,0,0,0.8)" }}>
        {/* Retro scanline overlay */}
        <div className="absolute inset-0 pointer-events-none" style={{ background: "linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06))", backgroundSize: "100% 4px, 6px 100%" }} />
        
        <div className="kernel-terminal-head relative z-10 border-b border-[#00e5ff]/20">
          <span className="flex items-center text-[#00e5ff] text-shadow-glow">
            <i className="animate-pulse bg-[#00e5ff] shadow-[0_0_8px_#00e5ff]" /> MODEL KERNEL / SECURE DIAGNOSTICS
          </span>
          {result && <strong className={`kernel-${result.status} drop-shadow-md`}><CheckCircle2 size={12} /> {result.status}</strong>}
        </div>
        
        <div className="relative z-10 font-mono text-[#a5f3cb]">
          {testMutation.isPending && <p className="text-[#00e5ff] animate-pulse"><LoaderCircle className="spin" size={13} /> initializing isolated enclave…</p>}
          {result?.logs.slice(0, visibleLines).map((line, index) => (
            <p key={`${line}-${index}`} className="my-1 opacity-90 hover:opacity-100 transition-opacity">
              <span className="text-[#00e5ff]/50 mr-2">{line.startsWith("$") ? "" : "›"}</span>
              {line}
            </p>
          ))}
          {visibleLines < (result?.logs.length || 0) && (
             <span className="inline-block w-2 h-3 bg-[#00e5ff] animate-pulse ml-1" />
          )}
          {testMutation.isError && <p className="kernel-error text-red-400">› diagnostic run failed; enclave unreachable</p>}
        </div>
      </div>
    )}
  </div>;
}