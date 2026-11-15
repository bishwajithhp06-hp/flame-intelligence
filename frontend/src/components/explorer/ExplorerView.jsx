import React, { useState, useEffect } from 'react';
import { Search, Filter, Rocket, ExternalLink, ArrowRight, BookOpen, Database, Flame, CheckCircle } from 'lucide-react';
import { api } from '../../services/api';
import InvestigationModal from './InvestigationModal';
import StoredNasaExperiments from './StoredNasaExperiments';

export default function ExplorerView({ selectedId, onClearSelected }) {
  const [investigations, setInvestigations] = useState([]);
  const [selectedInvestigation, setSelectedInvestigation] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [loading, setLoading] = useState(true);
  const [recordMode, setRecordMode] = useState('investigations');

  const categories = [
    "All Categories",
    "Droplet Combustion & Cool Flames",
    "Large-Scale Material Flammability",
    "Soot Formation & Radiation",
    "Solid Fuel Extinguishment Limits",
    "Gaseous Flame Dynamics"
  ];

  useEffect(() => {
    async function loadInvestigations() {
      setLoading(true);
      try {
        const cat = selectedCategory === "All Categories" ? "" : selectedCategory;
        const data = await api.getInvestigations(cat, searchQuery);
        setInvestigations(data);

        // If an ID was requested externally
        if (selectedId) {
          const detail = await api.getInvestigationDetail(selectedId);
          setSelectedInvestigation(detail);
        }
      } catch (err) {
        console.error("Failed to load investigations", err);
      } finally {
        setLoading(false);
      }
    }
    loadInvestigations();
  }, [selectedCategory, searchQuery, selectedId]);

  const handleOpenDetail = async (id) => {
    try {
      const detail = await api.getInvestigationDetail(id);
      setSelectedInvestigation(detail);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCloseModal = () => {
    setSelectedInvestigation(null);
    if (onClearSelected) onClearSelected();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-space-border bg-space-panel p-3" aria-label="Explorer collection">
        <button type="button" onClick={() => setRecordMode('investigations')} className={`rounded-lg px-3 py-2 text-xs ${recordMode === 'investigations' ? 'bg-cyan-900/50 text-cyan-200' : 'text-slate-400 hover:text-white'}`}>Investigation catalogue</button>
        <button type="button" onClick={() => setRecordMode('stored')} className={`rounded-lg px-3 py-2 text-xs ${recordMode === 'stored' ? 'bg-cyan-900/50 text-cyan-200' : 'text-slate-400 hover:text-white'}`}>Retrieved NASA records</button>
      </div>
      {recordMode === 'stored' ? <StoredNasaExperiments /> : <>
      {/* Search and Filters Bar */}
      <div className="p-4 rounded-xl bg-space-panel border border-space-border space-y-3">
        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by experiment acronym (FLEX, SAFFIRE), fuel (heptane, PMMA), or keyword..."
              className="w-full pl-9 pr-4 py-2 text-xs bg-space-panel border border-space-border rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
            />
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          </div>

          <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
            <Filter size={14} className="text-slate-400 shrink-0" />
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="bg-space-panel border border-space-border rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              {categories.map((c, i) => (
                <option key={i} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
          <span>Showing {investigations.length} local investigation records</span>
          <span className="text-cyan-400">Database Grounding: NASA PSI & NTRS</span>
        </div>
      </div>

      {/* Investigations Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {investigations.map((inv) => (
          <div
            key={inv.id}
            className="rounded-xl bg-space-panel border border-space-border hover:border-cyan-500/50 p-5 flex flex-col justify-between space-y-4 transition-all group"
          >
            <div className="space-y-3">
              {/* Header Badges */}
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded text-xs font-extrabold font-mono bg-blue-950 text-cyan-400 border border-blue-800">
                  {inv.acronym}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                  {inv.status}
                </span>
              </div>

              {/* Title & Category */}
              <div>
                <h3 className="text-sm font-bold text-white group-hover:text-cyan-300 transition-colors">
                  {inv.title}
                </h3>
                <span className="text-[11px] text-cyan-400 font-medium block mt-1">
                  {inv.category}
                </span>
              </div>

              {/* Facility & Investigator */}
              <div className="space-y-1 text-xs text-slate-400 border-t border-space-border pt-2.5">
                <div>
                  <span className="text-slate-500">Facility:</span>{" "}
                  <span className="text-slate-300">{inv.facility || "ISS CIR / MSG"}</span>
                </div>
                <div>
                  <span className="text-slate-500">Principal Investigator:</span>{" "}
                  <span className="text-slate-300">{inv.principal_investigator}</span>
                </div>
                {inv.fuel_types && (
                  <div className="truncate">
                    <span className="text-slate-500">Fuels:</span>{" "}
                    <span className="text-orange-300 font-mono text-[11px]">{inv.fuel_types}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Actions */}
            <div className="border-t border-space-border pt-3 flex items-center justify-between text-xs">
              <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
                <span className="flex items-center gap-1">
                  <BookOpen size={12} className="text-cyan-400" />
                  {inv.publications_count} Pubs
                </span>
                <span className="flex items-center gap-1">
                  <Database size={12} className="text-emerald-400" />
                  {inv.datapoints_count} Points
                </span>
              </div>

              <button
                onClick={() => handleOpenDetail(inv.id)}
                className="inline-flex items-center gap-1 text-xs font-semibold text-cyan-400 hover:text-cyan-300 group-hover:translate-x-0.5 transition-all cursor-pointer"
              >
                <span>Full Details</span>
                <ArrowRight size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Modal for Deep Inspection */}
      {selectedInvestigation && (
        <InvestigationModal
          investigation={selectedInvestigation}
          onClose={handleCloseModal}
        />
      )}
      </>}
    </div>
  );
}
