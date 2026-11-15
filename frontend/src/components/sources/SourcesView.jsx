import React, { useState, useEffect } from 'react';
import { Database, ExternalLink, RefreshCw, CheckCircle, AlertTriangle, ShieldCheck, Globe } from 'lucide-react';
import { api } from '../../services/api';

export default function SourcesView() {
  const [sources, setSources] = useState([]);
  const [verifying, setVerifying] = useState(false);
  const [checkResult, setCheckResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadSources() {
      setLoading(true);
      try {
        const data = await api.getSources();
        setSources(data);
      } catch (err) {
        console.error("Failed to load sources", err);
      } finally {
        setLoading(false);
      }
    }
    loadSources();
  }, []);

  const handleVerifySources = async () => {
    setVerifying(true);
    try {
      const res = await api.verifySources();
      setCheckResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Verification Panel */}
      <div className="p-5 rounded-2xl bg-space-panel border border-space-border space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              <Database className="text-cyan-400 w-5 h-5" />
              <span>NASA Scientific Data Sources & Collector Registry</span>
            </h1>
            <p className="text-xs text-slate-300">
              Official repositories and physical science informatics sources powering FLAME INTELLIGENCE.
            </p>
          </div>

          <button
            onClick={handleVerifySources}
            disabled={verifying}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-space-panel border border-space-border hover:border-cyan-500/50 text-slate-200 transition-colors disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw size={13} className={verifying ? "animate-spin text-cyan-400" : "text-cyan-400"} />
            <span>{verifying ? "Verifying Endpoints..." : "Verify NASA Connectivity"}</span>
          </button>
        </div>

        {/* Live Status Check Results */}
        {checkResult && (
          <div className="p-3.5 rounded-xl bg-space-panel border border-cyan-900/60 text-xs space-y-2">
            <div className="font-semibold text-cyan-300 font-mono text-[11px]">
              Connectivity Verification Report:
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {checkResult.status_checks.map((chk, i) => (
                <div key={i} className="p-2 rounded bg-space-panel border border-space-border flex items-center justify-between">
                  <span className="font-medium text-slate-200">{chk.provider}</span>
                  <span className={`font-mono text-[10px] px-2 py-0.5 rounded ${
                    chk.is_accessible ? 'bg-emerald-950 text-emerald-300' : 'bg-red-950 text-red-300'
                  }`}>
                    {chk.is_accessible ? `ONLINE (HTTP ${chk.status_code || 200})` : 'UNREACHABLE'}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-400 italic">
              * {checkResult.message}
            </p>
          </div>
        )}
      </div>

      {/* Collector Principles Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div className="p-4 rounded-xl bg-space-panel border border-space-border space-y-2">
          <div className="font-bold text-cyan-400 font-mono text-[11px] uppercase flex items-center gap-1.5">
            <CheckCircle size={14} />
            <span>Respectful Collection</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-[11px]">
            Strict adherence to NASA website terms and robots.txt. Does not automatically fetch massive video binaries or large multi-gigabyte raw telemetry packets.
          </p>
        </div>

        <div className="p-4 rounded-xl bg-space-panel border border-space-border space-y-2">
          <div className="font-bold text-orange-400 font-mono text-[11px] uppercase flex items-center gap-1.5">
            <ShieldCheck size={14} />
            <span>Zero Fabrication</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-[11px]">
            Every investigation, publication title, author, and DOI is cross-verified against NASA STI records. Missing attributes are left unfilled rather than guessed.
          </p>
        </div>

        <div className="p-4 rounded-xl bg-space-panel border border-space-border space-y-2">
          <div className="font-bold text-emerald-400 font-mono text-[11px] uppercase flex items-center gap-1.5">
            <Globe size={14} />
            <span>Modular Ingestion</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-[11px]">
            Extensible backend services (<code className="font-mono text-cyan-300">nasa_psi_service.py</code> and <code className="font-mono text-cyan-300">nasa_ntrs_service.py</code>) ready for additional combustion experiments.
          </p>
        </div>
      </div>

      {/* Primary Sources Directory */}
      <div className="space-y-3">
        <h2 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-400">
          Archived NASA Source Registries ({sources.length})
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sources.map((src) => (
            <div
              key={src.id}
              className="p-5 rounded-xl bg-space-panel border border-space-border flex flex-col justify-between space-y-3"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-cyan-400 border border-blue-800">
                    {src.resource_id}
                  </span>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
                    {src.status}
                  </span>
                </div>

                <h3 className="text-sm font-bold text-white">{src.title}</h3>
                <p className="text-[11px] text-cyan-400 font-medium">{src.resource_type}</p>
                <p className="text-xs text-slate-300 leading-relaxed">{src.notes}</p>
              </div>

              <div className="border-t border-space-border pt-3 flex items-center justify-between text-xs">
                <span className="text-[10px] font-mono text-slate-500">
                  Verified: {src.last_verified}
                </span>

                <a
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 font-medium text-xs"
                >
                  <span>Access NASA Portal</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
