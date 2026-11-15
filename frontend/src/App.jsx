import React, { lazy, Suspense, useState, useEffect } from 'react';
import Navbar from './components/common/Navbar';
import Sidebar from './components/common/Sidebar';
import DashboardView from './components/dashboard/DashboardView';
import ExplorerView from './components/explorer/ExplorerView';
import AiAssistantView from './components/ai/AiAssistantView';
import AnalyticsView from './components/analytics/AnalyticsView';
import ComparisonView from './components/comparison/ComparisonView';
import InsightsView from './components/insights/InsightsView';
import SourcesView from './components/sources/SourcesView';
import MissionIntelligenceView from './components/mission/MissionIntelligenceView';
import { api } from './services/api';

const VisualLabView = lazy(() => import('./components/visual-lab/VisualLabView.jsx'));

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedInvestigationId, setSelectedInvestigationId] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [backendHealthy, setBackendHealthy] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [searchModalOpen, setSearchModalOpen] = useState(false);

  // Health check on mount and interval
  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch('/api/health');
        if (res.ok) {
          const data = await res.json();
          setBackendHealthy(data.status === 'healthy');
        } else {
          setBackendHealthy(false);
        }
      } catch (e) {
        setBackendHealthy(false);
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectInvestigation = (id) => {
    setSelectedInvestigationId(id);
    setActiveTab('explorer');
  };

  const handleSearch = async (query) => {
    if (!query) return;
    try {
      const results = await api.search(query);
      setSearchResults(results);
      setSearchModalOpen(true);
    } catch (err) {
      console.error("Search failed", err);
    }
  };

  return (
    <div className="min-h-screen bg-space-bg text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-black">
      {/* Top Navigation Bar */}
      <Navbar
        onSearch={handleSearch}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        backendStatus={backendHealthy}
        mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={setMobileMenuOpen}
      />

      <div className="flex flex-1">
        {/* Modern Sidebar Navigation */}
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          mobileMenuOpen={mobileMenuOpen}
          setMobileMenuOpen={setMobileMenuOpen}
        />

        {/* Main Content Area */}
        <main className="flex-1 p-4 lg:p-8 max-w-7xl mx-auto w-full overflow-y-auto">
          {activeTab === 'dashboard' && (
            <DashboardView
              onSelectInvestigation={handleSelectInvestigation}
              setActiveTab={setActiveTab}
            />
          )}

          {activeTab === 'explorer' && (
            <ExplorerView
              selectedId={selectedInvestigationId}
              onClearSelected={() => setSelectedInvestigationId(null)}
            />
          )}

          {activeTab === 'ai' && <AiAssistantView />}

          {activeTab === 'mission' && <MissionIntelligenceView />}

          {activeTab === 'visual-lab' && (
            <Suspense fallback={<p role="status" className="p-6 text-xs text-cyan-200">Loading Visual Lab…</p>}>
              <VisualLabView />
            </Suspense>
          )}

          {activeTab === 'analytics' && <AnalyticsView />}

          {activeTab === 'comparison' && <ComparisonView />}

          {activeTab === 'insights' && <InsightsView />}

          {activeTab === 'sources' && <SourcesView />}
        </main>
      </div>

      {/* Global Search Results Modal */}
      {searchModalOpen && searchResults && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-2xl bg-space-panel border border-space-border rounded-2xl p-6 space-y-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-space-border pb-3">
              <h2 className="text-sm font-bold text-white font-mono uppercase">
                Search Results for: <span className="text-cyan-400">"{searchResults.query}"</span>
              </h2>
              <button
                onClick={() => setSearchModalOpen(false)}
                className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-900 border border-slate-800"
              >
                Close
              </button>
            </div>

            {/* Investigations matches */}
            {searchResults.investigations.length > 0 && (
              <div className="space-y-2">
                <span className="text-[10px] font-mono text-cyan-400 uppercase font-bold">
                  NASA Investigations ({searchResults.investigations.length})
                </span>
                <div className="space-y-1.5">
                  {searchResults.investigations.map((inv) => (
                    <div
                      key={inv.id}
                      onClick={() => {
                        handleSelectInvestigation(inv.id);
                        setSearchModalOpen(false);
                      }}
                      className="p-2.5 rounded bg-space-panel border border-space-border hover:border-cyan-500/50 cursor-pointer flex items-center justify-between text-xs"
                    >
                      <div>
                        <span className="font-bold text-white mr-2 font-mono text-cyan-300">{inv.acronym}</span>
                        <span className="text-slate-300">{inv.title}</span>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">{inv.facility}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Publications matches */}
            {searchResults.publications.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="text-[10px] font-mono text-orange-400 uppercase font-bold">
                  Landmark Publications ({searchResults.publications.length})
                </span>
                <div className="space-y-1.5">
                  {searchResults.publications.map((pub) => (
                    <div key={pub.id} className="p-2.5 rounded bg-space-panel border border-space-border text-xs space-y-1">
                      <div className="font-semibold text-white">{pub.title}</div>
                      <div className="text-[11px] text-slate-400">
                        {pub.authors} ({pub.year}) {pub.doi && `• DOI: ${pub.doi}`}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Findings matches */}
            {searchResults.findings.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="text-[10px] font-mono text-emerald-400 uppercase font-bold">
                  Fire Safety Findings ({searchResults.findings.length})
                </span>
                <div className="space-y-1.5">
                  {searchResults.findings.map((f) => (
                    <div key={f.id} className="p-2.5 rounded bg-space-panel border border-space-border text-xs space-y-1">
                      <div className="text-slate-200 font-medium">{f.finding_text}</div>
                      <div className="text-[11px] text-slate-400 italic">Safety: {f.implication}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {searchResults.investigations.length === 0 &&
              searchResults.publications.length === 0 &&
              searchResults.findings.length === 0 && (
                <div className="p-6 text-center text-xs text-slate-400 font-mono">
                  No matching microgravity combustion records found. Try "cool flames", "saffire", "droplet", "PMMA", or "soot".
                </div>
              )}
          </div>
        </div>
      )}
    </div>
  );
}
