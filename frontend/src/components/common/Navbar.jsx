import React, { useState } from 'react';
import { Flame, Search, Radio, ExternalLink, Menu, X, ShieldAlert } from 'lucide-react';

export default function Navbar({ onSearch, activeTab, setActiveTab, backendStatus, mobileMenuOpen, setMobileMenuOpen }) {
  const [searchInput, setSearchInput] = useState('');

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (onSearch) {
      onSearch(searchInput);
    }
  };

  return (
    <header className="sticky top-0 z-40 bg-space-panel/90 backdrop-blur-md border-b border-space-border px-4 lg:px-8 py-3">
      <div className="flex items-center justify-between gap-4">
        {/* Brand & Mission */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="lg:hidden p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 via-cyan-500 to-orange-500 p-0.5 shadow-lg shadow-cyan-500/20">
              <div className="w-full h-full bg-space-bg rounded-[10px] flex items-center justify-center">
                <Flame className="w-5 h-5 text-orange-400 animate-pulse" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-base tracking-wider text-white">FLAME INTELLIGENCE</span>
                <span className="px-1.5 py-0.5 text-[10px] font-mono tracking-tight font-semibold bg-cyan-950 text-cyan-400 border border-cyan-800 rounded">
                  NASA 2026
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                Microgravity Combustion Research & Spacecraft Fire Safety
              </p>
            </div>
          </div>
        </div>

        {/* Global Search Bar */}
        <div className="hidden md:flex flex-1 max-w-md mx-4">
          <form onSubmit={handleSearchSubmit} className="relative w-full">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search NASA experiments, fuels, cool flames, DOIs..."
              className="w-full pl-9 pr-4 py-1.5 text-xs bg-space-panel border border-space-border rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
            />
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
          </form>
        </div>

        {/* Status Indicators & Mission Badges */}
        <div className="flex items-center gap-3">
          <div className="hidden xl:flex items-center gap-2 text-xs font-mono px-2.5 py-1 rounded bg-space-panel border border-space-border text-slate-300">
            <span className="text-slate-500">FACILITY:</span>
            <span className="text-cyan-400">ISS CIR / MSG / CYGNUS</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-mono">
            <span className={`w-2 h-2 rounded-full ${backendStatus ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
            <span className="text-slate-300">
              {backendStatus ? 'API CONNECTED' : 'OFFLINE MODE'}
            </span>
          </div>

          <a
            href="https://psi.nasa.gov/physci/repo"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-cyan-400 transition-colors px-2 py-1"
            title="Open NASA PSI Portal"
          >
            <span>NASA PSI</span>
            <ExternalLink size={12} />
          </a>
        </div>
      </div>
    </header>
  );
}
