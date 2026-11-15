import React, { Component, lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Maximize2, Minus, Pause, Play, Plus, RotateCcw } from 'lucide-react';
import NasaMediaLibrary from './NasaMediaLibrary.jsx';
import { DEFAULT_VISUAL_SCENARIO, getIllustrativeSettings, VISUAL_MODES } from './visualModel.js';

const MissionScene3D = lazy(() => import('./MissionScene3D.jsx'));

const ENVIRONMENTS = ['ISS Cabin', 'Lunar Habitat', 'Mars Habitat', 'Pressurized Rover', 'Spacecraft Cabin', 'Spacesuit'];
const GRAVITY_OPTIONS = ['microgravity', 'lunar', 'mars', 'earth'];
const MATERIAL_OPTIONS = [
  { value: 'n-heptane', label: 'n-Heptane' },
  { value: 'pmma', label: 'PMMA' },
  { value: 'cotton-fabric', label: 'Cotton / fabric' },
  { value: 'gas-jet', label: 'Gaseous fuel jet' },
  { value: 'nomex', label: 'Nomex' },
];

class SceneErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function ParameterSlider({ label, value, unit, min, max, step, onChange }) {
  return (
    <label className="block space-y-1.5">
      <span className="flex items-center justify-between text-[10px] text-slate-300"><span>{label}</span><output className="font-mono text-cyan-200">{value} {unit}</output></span>
      <input type="range" aria-label={label} min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="w-full accent-cyan-400" />
      <span className="flex justify-between text-[9px] text-slate-600"><span>{min}</span><span>{max} {unit}</span></span>
    </label>
  );
}

export default function VisualLabView() {
  const [scenario, setScenario] = useState(DEFAULT_VISUAL_SCENARIO);
  const [mode, setMode] = useState('chamber');
  const [playing, setPlaying] = useState(true);
  const [fullScreen, setFullScreen] = useState(false);
  const [fullScreenError, setFullScreenError] = useState('');
  const [sceneVersion, setSceneVersion] = useState(0);
  const viewRef = useRef(null);
  const sceneRef = useRef(null);
  const dragRef = useRef(null);
  const settings = useMemo(() => getIllustrativeSettings(scenario), [scenario]);
  const activeMode = VISUAL_MODES.find((item) => item.id === mode) || VISUAL_MODES[0];

  useEffect(() => {
    const updateFullScreen = () => setFullScreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', updateFullScreen);
    return () => document.removeEventListener('fullscreenchange', updateFullScreen);
  }, []);

  const setField = (field, value) => setScenario((current) => ({ ...current, [field]: value }));
  const resetCamera = () => sceneRef.current?.resetCamera();
  const changeZoom = (factor) => sceneRef.current?.zoom(factor);
  const toggleFullScreen = async () => {
    setFullScreenError('');
    try {
      if (!document.fullscreenElement) await viewRef.current?.requestFullscreen?.();
      else await document.exitFullscreen?.();
    } catch {
      setFullScreenError('Full-screen mode is unavailable in this browser or by its current permissions.');
    }
  };

  const handlePointerDown = (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY };
  };
  const handlePointerMove = (event) => {
    if (!dragRef.current) return;
    sceneRef.current?.rotateCamera(event.clientX - dragRef.current.x, event.clientY - dragRef.current.y);
    dragRef.current = { x: event.clientX, y: event.clientY };
  };
  const handlePointerUp = (event) => {
    dragRef.current = null;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  };

  const errorFallback = (
    <div role="alert" className="flex h-full min-h-64 flex-col items-center justify-center gap-3 rounded-xl border border-amber-900/60 bg-space-sidebar p-6 text-center">
      <div className="flex h-36 w-56 items-center justify-center rounded-2xl border border-cyan-900/70 bg-cyan-950/10"><div className="h-24 w-10 rounded-full bg-gradient-to-t from-orange-700/80 to-amber-200/70" /></div>
      <p className="text-xs text-amber-200">Interactive 3D could not initialize. This static view is illustrative.</p>
      <button type="button" onClick={() => setSceneVersion((version) => version + 1)} className="rounded-lg border border-cyan-800 px-3 py-2 text-[10px] text-cyan-200">Retry 3D view</button>
    </div>
  );

  return (
    <div className="space-y-5">
      <header>
        <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Mission Modules / Visual Lab</p>
        <h1 className="mt-1 text-xl font-bold text-white">Interactive Combustion Visual Lab</h1>
        <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-400">Explore an illustrative chamber scene and source-linked NASA research media. The 3D visualization is not a validated physical model and does not produce measured flame properties or operational guidance.</p>
      </header>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(260px,0.8fr)]" aria-label="Interactive 3D chamber">
        <div ref={viewRef} className={`min-w-0 rounded-2xl border border-space-border bg-space-panel p-3 sm:p-4 ${fullScreen ? 'min-h-screen' : ''}`}>
          <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
            <div><h2 className="text-sm font-semibold text-white">Illustrative combustion chamber</h2><p className="mt-1 text-[10px] text-slate-500">Scenario controls alter display accents only; no NASA values or validated flame physics are calculated.</p></div>
            <span className="rounded-md border border-amber-800/70 bg-amber-950/30 px-2 py-1 text-[9px] font-mono uppercase text-amber-200">{activeMode.type}</span>
          </div>

          <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Visualization mode">
            {VISUAL_MODES.map((item) => <button key={item.id} type="button" aria-pressed={mode === item.id} onClick={() => setMode(item.id)} className={`rounded-md border px-2.5 py-2 text-[9px] sm:text-[10px] ${mode === item.id ? 'border-cyan-500/70 bg-cyan-950/50 text-cyan-100' : 'border-space-border bg-space-panel text-slate-400 hover:text-white'}`}>{item.label}</button>)}
          </div>

          <div className={`relative overflow-hidden rounded-xl border border-space-border bg-space-sidebar ${fullScreen ? 'h-[calc(100vh-245px)] min-h-72' : 'h-[300px] sm:h-[390px]'}`}>
            <SceneErrorBoundary key={sceneVersion} fallback={errorFallback}>
              <Suspense fallback={<div role="status" className="flex h-full items-center justify-center text-xs text-cyan-200">Loading the 3D scene…</div>}>
                <MissionScene3D ref={sceneRef} settings={settings} mode={mode} playing={playing} />
              </Suspense>
            </SceneErrorBoundary>
            <div className="absolute inset-0 z-10 cursor-grab touch-none active:cursor-grabbing" aria-label="Drag to rotate the camera" onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerCancel={handlePointerUp} />
            <div className="absolute right-2 top-2 z-20 flex flex-wrap justify-end gap-1.5">
              <button type="button" aria-label={playing ? 'Pause animation' : 'Play animation'} onClick={() => setPlaying((value) => !value)} className="rounded-md border border-space-border-strong bg-space-panel-raised/90 p-2 text-cyan-100">{playing ? <Pause size={14} /> : <Play size={14} />}</button>
              <button type="button" aria-label="Zoom in" onClick={() => changeZoom(0.86)} className="rounded-md border border-space-border-strong bg-space-panel-raised/90 p-2 text-cyan-100"><Plus size={14} /></button>
              <button type="button" aria-label="Zoom out" onClick={() => changeZoom(1.16)} className="rounded-md border border-space-border-strong bg-space-panel-raised/90 p-2 text-cyan-100"><Minus size={14} /></button>
              <button type="button" aria-label="Reset camera view" onClick={resetCamera} className="rounded-md border border-space-border-strong bg-space-panel-raised/90 p-2 text-cyan-100"><RotateCcw size={14} /></button>
              <button type="button" aria-label={fullScreen ? 'Exit full screen' : 'Enter full screen'} onClick={toggleFullScreen} className="rounded-md border border-space-border-strong bg-space-panel-raised/90 p-2 text-cyan-100"><Maximize2 size={14} /></button>
            </div>
            <p className="pointer-events-none absolute bottom-2 left-2 z-20 rounded bg-space-panel-raised/85 px-2 py-1 text-[9px] text-slate-300">Drag to rotate · controls for zoom, animation and reset</p>
          </div>
          {fullScreenError && <p role="alert" className="mt-2 text-[10px] text-amber-300">{fullScreenError}</p>}

          <div className="mt-3 rounded-lg border border-amber-900/60 bg-amber-950/20 p-3 text-[10px] leading-relaxed text-amber-100">
            <p className="font-semibold">Interpretation: illustrative simulation</p>
            <p className="mt-1">This scene is not a photograph or a NASA experimental observation and is not derived from measured NASA data. Its appearance does not calculate flame speed, temperature, suppression limits, or risk. Selecting the microgravity view does not represent lunar gravity.</p>
          </div>
        </div>

        <aside className="space-y-3 rounded-2xl border border-space-border bg-space-panel p-4" aria-label="Visualization scenario controls">
          <div><h2 className="text-sm font-semibold text-white">Illustrative scenario inputs</h2><p className="mt-1 text-[10px] text-slate-500">Edit these hypothetical values to change visual accents.</p></div>
          <label className="block space-y-1 text-[10px] text-slate-300">Environment
            <select value={scenario.environment} onChange={(event) => setField('environment', event.target.value)} className="w-full rounded-lg border border-space-border bg-space-panel px-2.5 py-2 text-xs text-white">{ENVIRONMENTS.map((value) => <option key={value}>{value}</option>)}</select>
          </label>
          <ParameterSlider label="Oxygen concentration" value={scenario.oxygen_percent} unit="%" min={10} max={40} step={0.1} onChange={(value) => setField('oxygen_percent', value)} />
          <ParameterSlider label="Ambient pressure" value={scenario.pressure_atm} unit="atm" min={0.2} max={1.5} step={0.01} onChange={(value) => setField('pressure_atm', value)} />
          <ParameterSlider label="Airflow input" value={scenario.airflow_cm_s} unit="cm/s" min={0} max={50} step={0.5} onChange={(value) => setField('airflow_cm_s', value)} />
          <label className="block space-y-1 text-[10px] text-slate-300">Gravity scenario
            <select value={scenario.gravity} onChange={(event) => setField('gravity', event.target.value)} className="w-full rounded-lg border border-space-border bg-space-panel px-2.5 py-2 text-xs text-white">{GRAVITY_OPTIONS.map((value) => <option key={value} value={value}>{value}</option>)}</select>
          </label>
          <label className="block space-y-1 text-[10px] text-slate-300">Fuel / material scenario
            <select value={scenario.material} onChange={(event) => setField('material', event.target.value)} className="w-full rounded-lg border border-space-border bg-space-panel px-2.5 py-2 text-xs text-white">{MATERIAL_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
          </label>
          <div className="rounded-lg bg-space-panel p-3 text-[10px] text-slate-300">
            <p className="font-mono uppercase tracking-wider text-slate-500">Current hypothetical scenario</p>
            <p className="mt-1">{scenario.environment} · O₂ {scenario.oxygen_percent}% · {scenario.pressure_atm} atm · {scenario.airflow_cm_s} cm/s · {scenario.gravity} · {scenario.material}</p>
            <p className="mt-2 text-[9px] text-slate-500">Control range values are display inputs only; no experiment or safety threshold is inferred.</p>
          </div>
        </aside>
      </section>

      <section className="grid gap-3 md:grid-cols-2" aria-label="Visualization evidence distinctions">
        <article className="rounded-xl border border-cyan-900/60 bg-cyan-950/15 p-4">
          <h2 className="text-xs font-semibold text-cyan-100">Experimental observation vs. hypothetical visualization</h2>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-400">NASA catalog photographs and videos below are linked to the source records returned by NASA’s media service. The 3D chamber is an illustrative simulation; it is not reconstructed from those media records and does not establish behavior for this selected scenario.</p>
        </article>
        <article className="rounded-xl border border-amber-900/60 bg-amber-950/15 p-4">
          <h2 className="text-xs font-semibold text-amber-100">Gravity limitation</h2>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-400">The selected gravity value is shown as scenario metadata. No physical gravity model is encoded. A microgravity visualization must not be interpreted as a lunar-gravity result.</p>
        </article>
      </section>

      <NasaMediaLibrary />
    </div>
  );
}
