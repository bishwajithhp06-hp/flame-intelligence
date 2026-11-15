import React from 'react';
import { 
  LayoutDashboard, 
  Compass, 
  Bot, 
  LineChart, 
  Columns3, 
  ShieldAlert, 
  Database,
  ExternalLink,
  Flame,
  Radar
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, mobileMenuOpen, setMobileMenuOpen }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, badge: 'Overview' },
    { id: 'explorer', label: 'NASA Research Explorer', icon: Compass, count: '5' },
    { id: 'ai', label: 'AI Research Assistant', icon: Bot, badge: 'Gemini RAG' },
    { id: 'mission', label: 'Mission Intelligence', icon: Radar, badge: 'Stage 1' },
    { id: 'visual-lab', label: 'Visual Lab & NASA Media', icon: Flame, badge: '3D + Media' },
    { id: 'analytics', label: 'Combustion Analytics', icon: LineChart, badge: 'Telemetry' },
    { id: 'comparison', label: 'Experiment Comparison', icon: Columns3, badge: 'FLEX vs SAFFIRE' },
    { id: 'insights', label: 'Fire Safety Insights', icon: ShieldAlert, badge: 'Safety' },
    { id: 'sources', label: 'NASA Sources & Collector', icon: Database, badge: 'PSI & NTRS' },
  ];

  const handleSelect = (id) => {
    setActiveTab(id);
    if (setMobileMenuOpen) {
      setMobileMenuOpen(false);
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Container */}
      <aside className={`
        fixed lg:static top-0 bottom-0 left-0 z-40
        w-64 bg-space-sidebar border-r border-space-border flex flex-col justify-between
        transition-transform duration-200 ease-in-out
        ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Navigation Links */}
        <div className="p-4 space-y-6 overflow-y-auto">
          <div className="hidden lg:block px-2 pt-2 pb-1">
            <span className="text-[10px] font-mono tracking-wider uppercase text-slate-500 font-semibold">
              Mission Modules
            </span>
          </div>

          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item.id)}
                  className={`
                    w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left
                    ${isActive 
                      ? 'bg-blue-600/15 text-cyan-300 border border-cyan-500/30 shadow-sm' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-space-panel'
                    }
                  `}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      isActive ? 'bg-cyan-900/60 text-cyan-300' : 'bg-slate-800 text-slate-400'
                    }`}>
                      {item.badge}
                    </span>
                  )}
                  {item.count && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                      {item.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Quick Target Investigations Section */}
          <div className="pt-4 border-t border-space-border/60">
            <span className="text-[10px] font-mono tracking-wider uppercase text-slate-500 font-semibold px-2 block mb-2">
              Primary Flight Series
            </span>
            <div className="grid grid-cols-2 gap-1.5">
              {[
                { name: 'FLEX', desc: 'Droplets' },
                { name: 'SAFFIRE', desc: 'Large Fabric' },
                { name: 'SPICE', desc: 'Soot / Gas' },
                { name: 'BASS', desc: 'Solids / N2' },
                { name: 'ACME', desc: 'E-Fields' },
              ].map((exp) => (
                <button
                  key={exp.name}
                  onClick={() => {
                    handleSelect('explorer');
                  }}
                  className="px-2 py-1.5 rounded bg-space-panel border border-space-border hover:border-cyan-500/40 text-left transition-colors"
                >
                  <div className="text-[11px] font-bold text-slate-200">{exp.name}</div>
                  <div className="text-[9px] text-slate-400">{exp.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer Info Box */}
        <div className="p-4 border-t border-space-border bg-space-bg/50">
          <div className="p-2.5 rounded-lg bg-space-panel border border-space-border space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold text-slate-300">NASA Challenge 2026</span>
              <span className="text-[10px] text-orange-400 font-mono">v1.0.0</span>
            </div>
            <p className="text-[10px] text-slate-400 leading-tight">
              Flame in Freefall: AI-Powered Fire Safety Insights.
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}
