import React, { useState, useEffect } from 'react';
import { 
  Rocket, 
  BookOpen, 
  ShieldCheck, 
  Database, 
  Activity, 
  Flame, 
  Clock, 
  ArrowRight, 
  ExternalLink,
  Layers,
  AlertTriangle,
  Sparkles
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell, 
  Tooltip as RechartsTooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis
} from 'recharts';
import { api } from '../../services/api';
import DataNoticeBanner from '../common/DataNoticeBanner';

export default function DashboardView({ onSelectInvestigation, setActiveTab }) {
  const [stats, setStats] = useState({
    total_investigations: 5,
    total_publications: 7,
    total_findings: 7,
    total_datapoints: 12,
    categories_count: 5
  });
  const [categories, setCategories] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [recentInvs, setRecentInvs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      try {
        const [statsData, catData, timelineData, recentData] = await Promise.all([
          api.getDashboardStats(),
          api.getCategories(),
          api.getTimeline(),
          api.getRecentInvestigations()
        ]);
        setStats(statsData);
        setCategories(catData);
        setTimeline(timelineData);
        setRecentInvs(recentData);
      } catch (err) {
        console.error("Error loading dashboard data", err);
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, []);

  const COLORS = ['#38BDF8', '#0B5CAD', '#F97316', '#7DD3FC', '#FB923C'];

  return (
    <div className="space-y-6">
      {/* Top Banner Notice */}
      <DataNoticeBanner />

      {/* Hero Mission Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-space-panel via-space-panel-raised to-space-panel border border-space-border p-6 lg:p-8">
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-radial from-cyan-500/10 via-transparent to-transparent pointer-events-none" />
        
        <div className="max-w-3xl space-y-3 relative z-10">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cyan-950/60 border border-cyan-800 text-cyan-300 text-xs font-mono">
            <Flame className="w-3.5 h-3.5 text-orange-400" />
            <span>NASA PHYSICAL SCIENCES INFORMATICS (PSI) HARVESTER</span>
          </div>

          <h1 className="text-2xl lg:text-3xl font-extrabold text-white tracking-tight">
            Flame in Freefall: Microgravity Combustion & Spacecraft Fire Safety
          </h1>

          <p className="text-sm text-slate-300 leading-relaxed">
            Without buoyant convection in microgravity, flames behave in ways that defy Earth physics: droplets produce invisible 
            <span className="text-cyan-400 font-semibold"> cool flames (FLEX)</span>, fabrics burn voraciously along 
            <span className="text-orange-400 font-semibold"> low-velocity ventilation drafts (SAFFIRE)</span>, and soot formation increases dramatically 
            <span className="text-amber-400 font-semibold"> (SPICE)</span>. This research dashboard organizes local investigation records and NASA publication metadata; local datapoint provenance requires independent verification.
          </p>

          <div className="pt-2 flex flex-wrap gap-3">
            <button
              onClick={() => setActiveTab('ai')}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-space-primary hover:bg-space-primary-hover text-white shadow-md transition-colors cursor-pointer"
            >
              <Sparkles size={14} />
              <span>Ask AI Research Assistant</span>
            </button>
            <button
              onClick={() => setActiveTab('explorer')}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-space-panel border border-space-border hover:border-cyan-500/50 text-slate-200 transition-all cursor-pointer"
            >
              <span>Explore 5 Target Investigations</span>
              <ArrowRight size={14} />
            </button>
            <button
              onClick={() => setActiveTab('mission')}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-space-panel border border-space-border hover:border-cyan-500/50 text-slate-200 transition-all cursor-pointer"
            >
              <span>Open Mission Control</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Primary Telemetry Metrics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            title: "Total Investigations",
            value: stats.total_investigations,
            sub: "FLEX, SAFFIRE, SPICE, BASS, ACME",
            icon: Rocket,
            color: "text-blue-400",
            border: "border-blue-900/40",
            bg: "bg-blue-950/20"
          },
          {
            title: "Research Publications",
            value: stats.total_publications,
            sub: "Peer-reviewed & NTRS records",
            icon: BookOpen,
            color: "text-cyan-400",
            border: "border-cyan-900/40",
            bg: "bg-cyan-950/20"
          },
          {
            title: "Fire Safety Findings",
            value: stats.total_findings,
            sub: "Local findings; provenance unverified",
            icon: ShieldCheck,
            color: "text-orange-400",
            border: "border-orange-900/40",
            bg: "bg-orange-950/20"
          },
          {
            title: "Stored Datapoints",
            value: stats.total_datapoints,
            sub: "Legacy numeric rows; provenance unverified",
            icon: Database,
            color: "text-emerald-400",
            border: "border-emerald-900/40",
            bg: "bg-emerald-950/20"
          }
        ].map((card, idx) => {
          const Icon = card.icon;
          return (
            <div 
              key={idx} 
              className={`p-4 rounded-xl bg-space-panel border ${card.border} flex flex-col justify-between`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">{card.title}</span>
                <div className={`p-2 rounded-lg ${card.bg}`}>
                  <Icon className={`w-4 h-4 ${card.color}`} />
                </div>
              </div>
              <div className="mt-3">
                <div className="text-2xl font-extrabold text-white font-mono">{card.value}</div>
                <div className="text-[11px] text-slate-400 mt-0.5 truncate">{card.sub}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Grid: Categories Distribution & Recent Investigations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Research Category Breakdown */}
        <div className="lg:col-span-1 rounded-xl bg-space-panel border border-space-border p-5 space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <span>Research Categories</span>
              </h2>
              <span className="text-[10px] font-mono text-slate-400">5 Domains</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Distribution of NASA microgravity combustion domains.
            </p>

            {/* Recharts Pie Chart */}
            <div className="h-52 w-full mt-3">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categories.length ? categories : [{ category: "Combustion", count: 1 }]}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={4}
                    dataKey="count"
                    nameKey="category"
                  >
                    {categories.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--space-panel)',
                      borderColor: 'var(--space-border)',
                      borderRadius: '8px', 
                      fontSize: '11px',
                      color: 'var(--space-text-primary)'
                    }} 
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-space-border">
            {categories.map((cat, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 truncate pr-2">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }}></span>
                  <span className="text-slate-300 truncate">{cat.category}</span>
                </div>
                <span className="font-mono text-slate-400 shrink-0">{cat.count} inv</span>
              </div>
            ))}
          </div>
        </div>

        {/* Target Flight Investigations Explorer Previews */}
        <div className="lg:col-span-2 rounded-xl bg-space-panel border border-space-border p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-2">
                <Rocket className="w-4 h-4 text-orange-400" />
                <span>Primary NASA Flight Investigations</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Archived in NASA PSI and tested on ISS CIR, MSG, and Cygnus.
              </p>
            </div>
            <button
              onClick={() => setActiveTab('explorer')}
              className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1"
            >
              <span>View All</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div className="space-y-2.5">
            {recentInvs.map((inv) => (
              <div
                key={inv.id}
                onClick={() => onSelectInvestigation && onSelectInvestigation(inv.id)}
                className="group p-3 rounded-lg bg-space-panel border border-space-border hover:border-cyan-500/50 hover:bg-space-panel-raised transition-all cursor-pointer flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2 py-0.5 rounded text-xs font-extrabold font-mono bg-blue-950 text-cyan-400 border border-blue-800">
                      {inv.acronym}
                    </span>
                    <span className="text-xs font-semibold text-white group-hover:text-cyan-300 transition-colors truncate">
                      {inv.title}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-400">
                    <span>PI: {inv.principal_investigator || "NASA Science"}</span>
                    <span>•</span>
                    <span className="text-slate-500">{inv.facility}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end sm:self-center shrink-0">
                  <div className="text-right text-[10px] font-mono text-slate-400">
                    <div>{inv.publications_count} Pubs</div>
                    <div>{inv.datapoints_count} Points</div>
                  </div>
                  <div className="w-7 h-7 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 group-hover:text-white group-hover:bg-cyan-600 transition-colors">
                    <ArrowRight size={13} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Flight Timeline & Milestones */}
      <div className="rounded-xl bg-space-panel border border-space-border p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-2">
            <Clock className="w-4 h-4 text-amber-400" />
            <span>NASA Microgravity Flight Combustion Timeline</span>
          </h2>
          <span className="text-xs text-slate-400 font-mono">2008 – 2024 Milestones</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 pt-2">
          {timeline.map((item, index) => (
            <div 
              key={index} 
              className="p-3 rounded-lg bg-space-panel border border-space-border relative flex flex-col justify-between space-y-2 hover:border-slate-600 transition-colors"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-cyan-400 font-bold">{item.year_or_period}</span>
                  <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-slate-800 text-slate-300">
                    {item.acronym}
                  </span>
                </div>
                <div className="text-xs font-semibold text-white mt-1.5">{item.title}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">{item.facility}</div>
              </div>
              <p className="text-[11px] text-slate-300 border-t border-slate-800/80 pt-2 leading-tight">
                {item.milestone}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
