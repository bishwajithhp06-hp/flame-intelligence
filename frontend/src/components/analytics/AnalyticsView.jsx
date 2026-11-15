import React, { useState, useEffect } from 'react';
import { 
  LineChart as LineChartIcon, 
  Database, 
  ShieldCheck, 
  Filter, 
  Flame, 
  Wind, 
  Layers,
  AlertCircle
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  Legend, 
  CartesianGrid, 
  ScatterChart, 
  Scatter, 
  LineChart, 
  Line 
} from 'recharts';
import { api } from '../../services/api';

export default function AnalyticsView() {
  const [datapoints, setDatapoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterState, setFilterState] = useState('ALL');

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const data = await api.getDatapoints(false);
        setDatapoints(data);
      } catch (err) {
        console.error("Failed to load datapoints", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const filteredPoints = filterState === 'ALL' 
    ? datapoints 
    : datapoints.filter(dp => dp.state.toUpperCase() === filterState);

  // Group for Bar Chart: Burn rates per fuel
  const burnRateData = datapoints.map(dp => ({
    name: `${dp.fuel} (${dp.investigation})`,
    burn_rate: dp.burn_rate,
    velocity: dp.flow_velocity || 0,
    o2: dp.o2_pct || 21,
    unit: dp.unit,
    state: dp.state
  }));

  // Saffire & BASS Velocity Correlation Data
  const velocitySpreadData = datapoints
    .filter(dp => dp.flow_velocity !== null && dp.flow_velocity !== undefined)
    .map(dp => ({
      fuel: dp.fuel,
      investigation: dp.investigation,
      flow_velocity_cm_s: dp.flow_velocity,
      flame_speed_mm_s: dp.burn_rate,
      o2_pct: dp.o2_pct
    }))
    .sort((a, b) => a.flow_velocity_cm_s - b.flow_velocity_cm_s);

  return (
    <div className="space-y-6">
      {/* Header and Authenticity Disclaimer */}
      <div className="p-5 rounded-2xl bg-space-panel border border-space-border space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 text-white">
            <LineChartIcon className="text-cyan-400 w-5 h-5" />
            <h1 className="text-lg font-bold">Combustion Data Explorer</h1>
          </div>
          <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
            Local records · provenance unverified
          </span>
        </div>
        <p className="text-xs text-slate-300">
          Local database datapoints are shown for exploration. Their legacy measured-flight flag does not establish source provenance; no datapoint in this dataset is independently verified here as an original NASA flight measurement.
        </p>
      </div>

      {/* Primary Analytics Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Burn Rate / Flame Velocity by Fuel */}
        <div className="p-5 rounded-xl bg-space-panel border border-space-border space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Flame size={14} className="text-orange-400" />
              <span>Stored burn-rate and flame-speed values by fuel</span>
            </h2>
            <span className="text-[10px] font-mono text-amber-300">Unverified local values</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Comparison of droplet burning rate constant (K), solid fabric concurrent spread (mm/s), and gas extinction limits.
          </p>

          <div className="h-64 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={burnRateData} margin={{ top: 10, right: 10, left: -20, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--space-border)" />
                <XAxis 
                  dataKey="name" 
                  angle={-30} 
                  textAnchor="end" 
                  tick={{ fill: 'var(--space-text-secondary)', fontSize: 10 }}
                  interval={0}
                />
                <YAxis tick={{ fill: 'var(--space-text-secondary)', fontSize: 10 }} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--space-panel)', borderColor: 'var(--space-border)', borderRadius: '8px', fontSize: '11px', color: 'var(--space-text-primary)' }}
                />
                <Bar dataKey="burn_rate" fill="var(--space-primary)" radius={[4, 4, 0, 0]} name="Measured Speed / Rate" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Flame Spread vs Airflow Velocity */}
        <div className="p-5 rounded-xl bg-space-panel border border-space-border space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Wind size={14} className="text-cyan-400" />
              <span>Flame Spread Velocity vs Forced Cabin Airflow (Saffire / BASS)</span>
            </h2>
            <span className="text-[10px] font-mono text-cyan-400">0 – 20 cm/s</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Exploratory view of stored local datapoints. Values and units may not be comparable across investigations.
          </p>

          <div className="h-64 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={velocitySpreadData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--space-border)" />
                <XAxis 
                  dataKey="flow_velocity_cm_s" 
                  label={{ value: 'Forced Airflow (cm/s)', position: 'insideBottom', offset: -10, fill: 'var(--space-text-muted)', fontSize: 10 }}
                  tick={{ fill: 'var(--space-text-secondary)', fontSize: 10 }} 
                />
                <YAxis 
                  label={{ value: 'Spread Rate (mm/s)', angle: -90, position: 'insideLeft', offset: 10, fill: 'var(--space-text-muted)', fontSize: 10 }}
                  tick={{ fill: 'var(--space-text-secondary)', fontSize: 10 }} 
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--space-panel)', borderColor: 'var(--space-border)', borderRadius: '8px', fontSize: '11px', color: 'var(--space-text-primary)' }}
                />
                <Line type="monotone" dataKey="flame_speed_mm_s" stroke="var(--space-orange)" strokeWidth={2} dot={{ r: 5, fill: 'var(--space-orange)' }} name="Spread Rate (mm/s)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Raw Documented Telemetry Datasets Table */}
      <div className="p-5 rounded-xl bg-space-panel border border-space-border space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Database size={16} className="text-emerald-400" />
              <span>Local Datapoint Registry</span>
            </h2>
            <p className="text-xs text-slate-400">
              Stored parameters and values are labeled with their provenance status.
            </p>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 bg-space-panel p-1 rounded-lg border border-space-border text-xs">
            {['ALL', 'DROPLET', 'SOLID SHEET', 'GAS JET'].map((st) => (
              <button
                key={st}
                onClick={() => setFilterState(st)}
                className={`px-2.5 py-1 rounded text-[11px] font-mono transition-colors ${
                  filterState === st ? 'bg-cyan-900 text-cyan-300 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto border border-space-border rounded-lg">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-space-panel text-[10px] uppercase font-mono text-slate-400 border-b border-space-border">
              <tr>
                <th className="p-3">Investigation</th>
                <th className="p-3">Fuel Name</th>
                <th className="p-3">State</th>
                <th className="p-3">Ambient O2 %</th>
                <th className="p-3">Airflow Speed</th>
                <th className="p-3">Stored value / unit</th>
                <th className="p-3">Observed Phenomenon</th>
                <th className="p-3">Evidence status</th>
                <th className="p-3">NASA Citation Run</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-space-border">
              {filteredPoints.map((dp) => (
                <tr key={dp.id} className="hover:bg-slate-900/50">
                  <td className="p-3 font-bold font-mono text-cyan-400">{dp.investigation}</td>
                  <td className="p-3 font-semibold text-white">{dp.fuel}</td>
                  <td className="p-3 text-slate-400">{dp.state}</td>
                  <td className="p-3 font-mono">{dp.o2_pct ? `${dp.o2_pct}%` : 'N/A'}</td>
                  <td className="p-3 font-mono">{dp.flow_velocity !== null ? `${dp.flow_velocity} cm/s` : '0 (Quiescent)'}</td>
                  <td className="p-3 font-mono text-orange-400 font-semibold">{dp.burn_rate} {dp.unit}</td>
                  <td className="p-3 text-slate-300 max-w-xs">{dp.phenomenon}</td>
                  <td className="p-3 font-mono text-[10px]">
                    <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                      {dp.evidence_status || 'Local record — provenance unverified'}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-[10px] text-slate-400">{dp.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
