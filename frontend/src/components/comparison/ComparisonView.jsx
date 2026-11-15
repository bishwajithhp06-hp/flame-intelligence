import React, { useState, useEffect } from 'react';
import { Columns3, ExternalLink, CheckCircle, ShieldCheck, Flame, Layers } from 'lucide-react';
import { api } from '../../services/api';

export default function ComparisonView() {
  const [matrix, setMatrix] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedExperiments, setSelectedExperiments] = useState(['FLEX', 'SAFFIRE', 'SPICE', 'BASS', 'ACME']);

  useEffect(() => {
    async function loadMatrix() {
      setLoading(true);
      try {
        const data = await api.getComparisonMatrix();
        setMatrix(data);
      } catch (err) {
        console.error("Failed to load comparison matrix", err);
      } finally {
        setLoading(false);
      }
    }
    loadMatrix();
  }, []);

  const toggleExperiment = (acronym) => {
    if (selectedExperiments.includes(acronym)) {
      if (selectedExperiments.length > 2) {
        setSelectedExperiments(selectedExperiments.filter(a => a !== acronym));
      }
    } else {
      setSelectedExperiments([...selectedExperiments, acronym]);
    }
  };

  const displayedItems = matrix.filter(item => selectedExperiments.includes(item.acronym));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-2xl bg-space-panel border border-space-border space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 text-white">
            <Columns3 className="text-cyan-400 w-5 h-5" />
            <h1 className="text-lg font-bold">NASA Flight Experiment Comparison Matrix</h1>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Compare 5 Foundational Investigations
          </span>
        </div>
        <p className="text-xs text-slate-300">
          Synthesizing experimental configurations, fuels, atmospheric boundaries, and spacecraft fire safety implications across NASA's primary microgravity combustion flight programs.
        </p>

        {/* Experiment Filter Pills */}
        <div className="flex items-center gap-2 pt-2 flex-wrap">
          <span className="text-[11px] font-mono text-slate-400">Active Experiments:</span>
          {matrix.map((item) => {
            const isSelected = selectedExperiments.includes(item.acronym);
            return (
              <button
                key={item.acronym}
                onClick={() => toggleExperiment(item.acronym)}
                className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20 border border-blue-400'
                    : 'bg-space-panel text-slate-400 border border-space-border hover:text-white'
                }`}
              >
                {item.acronym}
              </button>
            );
          })}
        </div>
      </div>

      {/* Comparison Grid */}
      <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-${displayedItems.length > 3 ? '4' : displayedItems.length} gap-4`}>
        {displayedItems.map((exp) => (
          <div
            key={exp.acronym}
            className="p-5 rounded-2xl bg-space-panel border border-space-border space-y-4 flex flex-col justify-between"
          >
            <div className="space-y-3">
              {/* Header */}
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded text-xs font-extrabold font-mono bg-blue-950 text-cyan-400 border border-blue-800">
                  {exp.acronym}
                </span>
                <span className="text-[10px] font-mono text-slate-400 truncate max-w-[120px]">
                  {exp.facility}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-bold text-white">{exp.title}</h3>
                <span className="text-xs text-cyan-400 font-medium block mt-0.5">
                  {exp.category}
                </span>
              </div>

              {/* Fuels & Oxidizers */}
              <div className="p-3 rounded-lg bg-space-panel border border-space-border space-y-2 text-xs">
                <div>
                  <span className="text-[10px] uppercase font-mono text-slate-500 block">Fuel Types</span>
                  <span className="text-orange-300 font-medium">{exp.fuel_types}</span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-mono text-slate-500 block">Atmosphere / Oxidizer</span>
                  <span className="text-slate-300">{exp.oxidizer_conditions}</span>
                </div>
              </div>

              {/* Key Findings */}
              <div className="space-y-1 text-xs">
                <span className="text-[10px] uppercase font-mono text-slate-500 block">Key Discovery</span>
                <p className="text-slate-300 leading-relaxed text-[11px]">
                  {exp.key_findings}
                </p>
              </div>

              {/* Safety Implication */}
              <div className="p-3 rounded-lg bg-orange-950/20 border border-orange-900/40 text-xs space-y-1">
                <span className="text-[10px] uppercase font-mono text-orange-400 font-bold block flex items-center gap-1">
                  <ShieldCheck size={12} />
                  <span>Spacecraft Fire Safety</span>
                </span>
                <p className="text-slate-200 text-[11px] leading-tight">
                  {exp.safety_implication}
                </p>
              </div>
            </div>

            {/* Links */}
            <div className="border-t border-space-border pt-3 flex items-center justify-between text-xs">
              {exp.primary_doi ? (
                <a
                  href={`https://doi.org/${exp.primary_doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:text-cyan-300 font-mono text-[10px] flex items-center gap-1"
                >
                  <span>DOI Link</span>
                  <ExternalLink size={10} />
                </a>
              ) : (
                <span className="text-slate-500 text-[10px] font-mono">NASA PSI Archive</span>
              )}

              {exp.psi_link && (
                <a
                  href={exp.psi_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-400 hover:text-white text-[10px] flex items-center gap-1"
                >
                  <span>PSI Repo</span>
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
