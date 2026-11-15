import React, { useState, useEffect } from 'react';
import { ShieldAlert, ShieldCheck, ExternalLink, AlertTriangle, Filter, CheckCircle2, Flame, Award } from 'lucide-react';
import { api } from '../../services/api';

export default function InsightsView() {
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('ALL');

  useEffect(() => {
    async function loadInsights() {
      setLoading(true);
      try {
        const data = await api.getFireSafetyInsights();
        setInsights(data);
      } catch (err) {
        console.error("Failed to load insights", err);
      } finally {
        setLoading(false);
      }
    }
    loadInsights();
  }, []);

  const categories = [
    'ALL',
    'Cool Flames & Extinction Limits',
    'Material Flammability & Ventilation Effects',
    'Soot Generation & Thresholds',
    'Extinction Velocity Sweet Spot',
    'Active Non-Chemical Flame Control',
    'Exploration Atmosphere Risks'
  ];

  const filtered = selectedCategory === 'ALL'
    ? insights
    : insights.filter(ins => ins.category === selectedCategory);

  return (
    <div className="space-y-6">
      {/* Formal Safety Disclaimer */}
      <div className="p-4 rounded-xl bg-orange-950/20 border border-orange-900/50 flex items-start gap-3 text-xs">
        <AlertTriangle className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-orange-300 uppercase tracking-wide font-mono text-[11px]">
            Spacecraft Safety Engineering Disclaimer
          </span>
          <p className="text-slate-300 leading-relaxed">
            The insights presented on this dashboard are direct scientific inferences distilled from NASA microgravity flight investigations (ISS CIR, MSG, and Cygnus Saffire). <strong>These findings do NOT constitute certified spacecraft safety assessments or engineering waivers.</strong> Actual spacecraft design must strictly comply with official NASA-STD-6001 standards and mission-specific safety panels.
          </p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="p-4 rounded-xl bg-space-panel border border-space-border flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold text-white uppercase font-mono tracking-wider">
            Scientific Fire Safety Takeaways ({filtered.length})
          </span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Filter size={13} className="text-slate-400" />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="bg-space-panel border border-space-border rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          >
            {categories.map((c, i) => (
              <option key={i} value={c}>{c === 'ALL' ? 'All Hazard Categories' : c}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Ranked Insights List */}
      <div className="grid grid-cols-1 gap-4">
        {filtered.map((item) => (
          <div
            key={item.id}
            className="p-5 rounded-xl bg-space-panel border border-space-border hover:border-cyan-500/40 transition-colors space-y-4"
          >
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-space-border pb-3">
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="px-2.5 py-0.5 rounded text-xs font-bold font-mono bg-blue-950 text-cyan-400 border border-blue-800">
                  {item.investigation_acronym}
                </span>
                <span className="text-xs font-semibold text-white">
                  {item.investigation_title}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">({item.facility})</span>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-auto">
                <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                  <Award size={11} />
                  <span>{item.evidence_strength}</span>
                </span>
              </div>
            </div>

            {/* Scientific Finding & Fire Safety Implication */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
              <div className="space-y-1.5 p-3 rounded-lg bg-space-panel border border-space-border">
                <span className="text-[10px] uppercase font-mono text-slate-400 font-semibold block">
                  Empirical Microgravity Finding
                </span>
                <p className="text-slate-200 leading-relaxed font-medium">
                  {item.finding_text}
                </p>
                <div className="text-[10px] text-cyan-400 font-mono pt-1">
                  Category: {item.category}
                </div>
              </div>

              <div className="space-y-1.5 p-3 rounded-lg bg-orange-950/20 border border-orange-900/40">
                <span className="text-[10px] uppercase font-mono text-orange-400 font-bold block flex items-center gap-1">
                  <ShieldCheck size={12} />
                  <span>Why It Matters for Human Spaceflight</span>
                </span>
                <p className="text-slate-200 leading-relaxed">
                  {item.spacecraft_fire_safety_implication}
                </p>
              </div>
            </div>

            {/* Citation & DOI */}
            <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-space-border/60">
              <span className="italic truncate pr-2">Citation: {item.source_citation}</span>
              {item.doi && (
                <a
                  href={`https://doi.org/${item.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:text-cyan-300 font-mono text-[10px] flex items-center gap-1 shrink-0"
                >
                  <span>DOI: {item.doi}</span>
                  <ExternalLink size={10} />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
