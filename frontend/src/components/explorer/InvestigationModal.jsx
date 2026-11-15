import React from 'react';
import { X, ExternalLink, BookOpen, ShieldCheck, Database, Award, Info, Flame } from 'lucide-react';

export default function InvestigationModal({ investigation, onClose }) {
  if (!investigation) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm overflow-y-auto">
      <div 
        className="relative w-full max-w-4xl bg-space-panel border border-space-border rounded-2xl shadow-2xl overflow-hidden my-8 max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-space-border bg-space-panel flex items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="px-2.5 py-0.5 rounded text-sm font-extrabold font-mono bg-blue-950 text-cyan-400 border border-blue-800">
                {investigation.acronym}
              </span>
              <span className="text-xs font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                ID: {investigation.investigation_id}
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
                {investigation.status}
              </span>
            </div>
            <h2 className="text-xl font-bold text-white">{investigation.title}</h2>
            <p className="text-xs text-slate-300">
              PI: <span className="text-white font-medium">{investigation.principal_investigator}</span> — {investigation.institution}
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 overflow-y-auto">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-space-panel border border-space-border">
              <span className="text-[10px] text-slate-500 font-mono uppercase block">Facility</span>
              <span className="font-semibold text-slate-200">{investigation.facility || "ISS Rack"}</span>
            </div>
            <div className="p-3 rounded-lg bg-space-panel border border-space-border">
              <span className="text-[10px] text-slate-500 font-mono uppercase block">Flight Mission</span>
              <span className="font-semibold text-slate-200">{investigation.flight_mission || "ISS Expedition"}</span>
            </div>
            <div className="p-3 rounded-lg bg-space-panel border border-space-border">
              <span className="text-[10px] text-slate-500 font-mono uppercase block">Category</span>
              <span className="font-semibold text-cyan-400">{investigation.category}</span>
            </div>
            <div className="p-3 rounded-lg bg-space-panel border border-space-border">
              <span className="text-[10px] text-slate-500 font-mono uppercase block">Gravity Level</span>
              <span className="font-semibold text-slate-200">{investigation.gravity_environment}</span>
            </div>
          </div>

          {/* Description & Objectives */}
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                Experiment Overview & Abstract
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed bg-space-panel p-3.5 rounded-lg border border-space-border">
                {investigation.description}
              </p>
            </div>

            {investigation.objectives && (
              <div>
                <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Research Objectives
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed bg-space-panel p-3.5 rounded-lg border border-space-border">
                  {investigation.objectives}
                </p>
              </div>
            )}
          </div>

          {/* Environmental Conditions & Fuels */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3.5 rounded-lg bg-space-panel border border-space-border space-y-1.5">
              <span className="text-xs font-bold text-orange-400 flex items-center gap-1.5">
                <Flame size={14} />
                <span>Fuels Tested</span>
              </span>
              <p className="text-xs text-slate-300">{investigation.fuel_types || "Documented in flight report"}</p>
            </div>
            <div className="p-3.5 rounded-lg bg-space-panel border border-space-border space-y-1.5">
              <span className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">
                <Info size={14} />
                <span>Atmospheric / Oxidizer Conditions</span>
              </span>
              <p className="text-xs text-slate-300">{investigation.oxidizer_environment || "Spacecraft cabin atmosphere"}</p>
            </div>
          </div>

          {/* Critical Fire Safety Relevance */}
          {investigation.fire_safety_relevance && (
            <div className="p-4 rounded-xl bg-gradient-to-r from-orange-950/30 to-space-panel border border-orange-900/60 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-orange-400 uppercase font-mono">
                <ShieldCheck size={16} />
                <span>Spacecraft Fire Safety Implication</span>
              </div>
              <p className="text-xs text-slate-200 leading-relaxed">
                {investigation.fire_safety_relevance}
              </p>
            </div>
          )}

          {/* Local datapoints, provenance unverified */}
          {investigation.datapoints && investigation.datapoints.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-400 flex items-center gap-2">
                <Database size={14} className="text-emerald-400" />
                <span>Local Datapoints — Provenance Unverified ({investigation.datapoints.length})</span>
              </h3>
              <div className="overflow-x-auto border border-space-border rounded-lg">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-space-panel text-[10px] uppercase font-mono text-slate-400 border-b border-space-border">
                    <tr>
                      <th className="p-2.5">Fuel</th>
                      <th className="p-2.5">State</th>
                      <th className="p-2.5">O2 %</th>
                      <th className="p-2.5">Airflow (cm/s)</th>
                      <th className="p-2.5">Measured Rate</th>
                      <th className="p-2.5">Phenomenon</th>
                      <th className="p-2.5">Reference</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-space-border">
                    {investigation.datapoints.map((dp, i) => (
                      <tr key={i} className="hover:bg-slate-900/40">
                        <td className="p-2.5 font-semibold text-white">{dp.fuel_name}</td>
                        <td className="p-2.5 text-slate-400">{dp.fuel_state}</td>
                        <td className="p-2.5 font-mono">{dp.ambient_o2_percent ? `${dp.ambient_o2_percent}%` : 'N/A'}</td>
                        <td className="p-2.5 font-mono">{dp.ambient_velocity_cm_s ?? '0'}</td>
                        <td className="p-2.5 font-mono text-cyan-400">{dp.burn_rate_or_flame_speed} {dp.unit}</td>
                        <td className="p-2.5 text-slate-300">{dp.phenomenon}</td>
                        <td className="p-2.5 text-[10px] text-slate-400 font-mono">{dp.source_reference}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Landmark Publications & Citations */}
          {investigation.publications && investigation.publications.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-400 flex items-center gap-2">
                <BookOpen size={14} className="text-cyan-400" />
                <span>Primary Publications & DOI Citations ({investigation.publications.length})</span>
              </h3>
              <div className="space-y-2">
                {investigation.publications.map((pub, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-space-panel border border-space-border space-y-1.5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-semibold text-xs text-white">{pub.title}</div>
                      {pub.url && (
                        <a
                          href={pub.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-cyan-400 hover:text-cyan-300 text-xs flex items-center gap-1 shrink-0"
                        >
                          <span>Open DOI</span>
                          <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {pub.authors} ({pub.year}) — <span className="italic text-slate-300">{pub.journal_or_conference}</span>
                    </div>
                    {pub.doi && (
                      <div className="text-[10px] font-mono text-cyan-500">
                        DOI: {pub.doi} {pub.ntrs_id ? `| NASA NTRS ID: ${pub.ntrs_id}` : ''}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-space-border bg-space-panel flex items-center justify-between">
          <div className="text-[11px] text-slate-400 font-mono">
            Source: NASA Physical Sciences Informatics (PSI)
          </div>
          <div className="flex items-center gap-3">
            {investigation.psi_repo_url && (
              <a
                href={investigation.psi_repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-950 text-cyan-300 border border-blue-800 hover:border-cyan-400 transition-colors"
              >
                <span>View on NASA PSI</span>
                <ExternalLink size={12} />
              </a>
            )}
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-white transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
