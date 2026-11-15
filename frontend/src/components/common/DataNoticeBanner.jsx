import React from 'react';
import { ShieldCheck, Info } from 'lucide-react';

export default function DataNoticeBanner() {
  return (
    <div className="bg-space-panel border border-space-border rounded-xl p-3.5 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs">
      <div className="flex items-center gap-2.5">
        <div className="p-1.5 rounded-lg bg-cyan-950/80 border border-cyan-800 text-cyan-400">
          <ShieldCheck size={18} />
        </div>
        <div>
          <span className="font-semibold text-slate-200">NASA Scientific Integrity Notice: </span>
          <span className="text-slate-400">
            Local investigation and datapoint records are not independently provenance-verified. The legacy measured-flight flag is not proof of NASA flight origin; live NTRS results provide publication metadata only.
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 self-end md:self-auto shrink-0 font-mono text-[11px] text-cyan-400 bg-cyan-950/40 px-2.5 py-1 rounded border border-cyan-900/60">
        <Info size={13} />
        <span>PROVENANCE LIMITS APPLY</span>
      </div>
    </div>
  );
}
