import React, { useState } from 'react';
import { api } from '../../services/api';
import { downloadMissionAnalysisReport, isCompleteMissionAnalysis } from '../../services/pdfDownload';
import {
  Radar,
  AlertTriangle,
  FlaskConical,
  Wind,
  Layers,
  ShieldAlert,
  Scale,
  BookOpen,
  Info
} from 'lucide-react';

const ENVIRONMENTS = [
  {
    id: 'iss-cabin',
    name: 'ISS Cabin',
    setting: 'Pressurized orbital cabin',
    note: 'Scenario only. Not a measured ISS atmosphere record.'
  },
  {
    id: 'lunar-habitat',
    name: 'Lunar Habitat',
    setting: 'Surface habitat module',
    note: 'Scenario only. Not a measured lunar habitat record.'
  },
  {
    id: 'mars-habitat',
    name: 'Mars Habitat',
    setting: 'Surface habitat module',
    note: 'Scenario only. Not a measured Mars habitat record.'
  },
  {
    id: 'pressurized-rover',
    name: 'Pressurized Rover',
    setting: 'Crewed rover cabin',
    note: 'Scenario only. Not a measured rover atmosphere record.'
  },
  {
    id: 'spacecraft-cabin',
    name: 'Spacecraft Cabin',
    setting: 'Transit vehicle cabin',
    note: 'Scenario only. Not a measured vehicle atmosphere record.'
  },
  {
    id: 'spacesuit',
    name: 'Spacesuit',
    setting: 'Pressurized suit volume',
    note: 'Scenario only. Not a measured suit atmosphere record.'
  }
];

const GRAVITY_OPTIONS = [
  { id: 'microgravity', label: 'Microgravity scenario' },
  { id: 'lunar', label: 'Lunar gravity scenario' },
  { id: 'mars', label: 'Mars gravity scenario' },
  { id: 'earth', label: 'Earth gravity scenario' }
];

const MATERIAL_OPTIONS = [
  { id: 'n-heptane', label: 'n-Heptane droplet (scenario choice)' },
  { id: 'pmma', label: 'PMMA solid sheet (scenario choice)' },
  { id: 'cotton-fabric', label: 'Cotton / fabric sheet (scenario choice)' },
  { id: 'gas-jet', label: 'Gaseous fuel jet (scenario choice)' },
  { id: 'nomex', label: 'Nomex textile (scenario choice)' }
];

const RESULT_SECTIONS = [
  {
    id: 'combustion',
    title: 'Combustion analysis',
    role: 'Combustion Analyst',
    icon: FlaskConical
  },
  {
    id: 'atmosphere',
    title: 'Atmosphere analysis',
    role: 'Atmosphere Analyst',
    icon: Wind
  },
  {
    id: 'material',
    title: 'Material safety analysis',
    role: 'Material Safety Analyst',
    icon: Layers
  },
  {
    id: 'suppression',
    title: 'Fire suppression analysis',
    role: 'Fire Suppression Analyst',
    icon: ShieldAlert
  },
  {
    id: 'synthesis',
    title: 'Mission safety synthesis',
    role: 'Mission Safety Synthesizer',
    icon: Scale
  },
  {
    id: 'evidence',
    title: 'Evidence matching and research gaps',
    role: 'Condition comparison · source records',
    icon: BookOpen
  }
];

const EVIDENCE_CLASS_LABELS = {
  verified_nasa_source: 'Verified NASA source evidence',
  local_provenance_unverified: 'Local provenance unverified',
  publication_metadata_only: 'Publication metadata only; measurements not verified',
};

function DetailList({ title, items }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="mb-1 text-[10px] font-mono uppercase text-slate-500">{title}</p>
      <ul className="list-disc pl-4 space-y-1 text-xs text-slate-300">
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{typeof item === 'string' ? item : item.explanation || item.finding}</li>
        ))}
      </ul>
    </div>
  );
}

function formatValidationDiagnostic(item) {
  const value = (flag) => flag === null || flag === undefined ? 'not checked' : flag ? 'yes' : 'no';
  return `Claim ${item.claim_index + 1} (${item.claim_classification}) · ${item.reason_code}: ${item.reason} `
    + `Evidence refs ${item.evidence_references_supplied ? 'supplied' : 'missing'}; evidence IDs valid ${value(item.evidence_ids_valid)}; `
    + `citation IDs valid ${value(item.citation_ids_valid)}; investigation match ${value(item.citation_investigation_match)}; `
    + `provenance restriction ${item.provenance_restriction_rejected ? 'applied' : 'not applied'}; `
    + `historical source-text match ${value(item.historical_source_text_match)}.`;
}

function CitationList({ citations }) {
  if (!citations?.length) return <p className="text-xs text-slate-400">No citations were retrieved.</p>;
  return (
    <div className="space-y-2">
      {citations.map((citation, index) => (
        <div key={citation.citation_id || `${citation.identifier || citation.title}-${index}`} className="rounded-lg bg-space-panel p-3 text-xs">
          {citation.url ? (
            <a href={citation.url} target="_blank" rel="noreferrer" className="font-semibold text-cyan-300 hover:underline">{citation.title}</a>
          ) : <p className="font-semibold text-slate-200">{citation.title}</p>}
          <p className="mt-1 text-slate-400">
            {citation.source}{citation.year ? ` · ${citation.year}` : ''}{citation.authors ? ` · ${citation.authors}` : ''}{citation.identifier ? ` · NTRS ${citation.identifier}` : ''}{citation.doi ? ` · DOI ${citation.doi}` : ''}
          </p>
          <p className="mt-1 text-[10px] text-amber-300">{EVIDENCE_CLASS_LABELS[citation.evidence_class] || citation.evidence_status}</p>
          <p className="text-[10px] text-slate-400">{citation.evidence_status}</p>
          {citation.relevance_explanation && <p className="mt-1 text-slate-400">{citation.relevance_explanation}</p>}
          {citation.relevance_snippet && <p className="mt-2 text-slate-300">{citation.relevance_snippet}</p>}
        </div>
      ))}
    </div>
  );
}

function EvidenceRecordCard({ record }) {
  return (
    <article key={record.evidence_id} className="rounded-lg bg-space-panel p-3 space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="font-semibold text-slate-100">{record.investigation_title} ({record.investigation_acronym})</h4>
          <p className="text-[10px] text-amber-300">{record.evidence_status}</p>
          <p className="text-[10px] text-slate-400">{EVIDENCE_CLASS_LABELS[record.evidence_class] || 'Related research context · local provenance unverified'}</p>
        </div>
        {record.original_source_url && <a href={record.original_source_url} target="_blank" rel="noreferrer" className="text-[10px] text-cyan-300 hover:underline">Original source record</a>}
      </div>
      <p className="text-xs text-slate-300">{record.relevance_explanation}</p>
      <p className="text-[10px] text-slate-500">Experiment type: {record.experiment_type || 'Not stated'} · Facility: {record.facility || 'Not stated'} · Mission: {record.flight_mission || 'Not stated'}</p>
      <div>
        <p className="mb-1 text-[10px] font-mono uppercase text-slate-500">Scenario condition comparisons</p>
        <ul className="space-y-1">
          {record.parameter_matches?.map((match) => (
            <li key={match.parameter} className="text-[11px] text-slate-300">
              <span className="font-mono text-cyan-300">{match.parameter}: {match.status.toUpperCase()}</span> · {match.explanation}
            </li>
          ))}
        </ul>
      </div>
      {record.publications?.length > 0 && (
        <div>
          <p className="mb-1 text-[10px] font-mono uppercase text-slate-500">Associated publications</p>
          <CitationList citations={record.publications} />
        </div>
      )}
    </article>
  );
}

function ResearchGapGroups({ report }) {
  const groups = [
    { title: 'Supported by provenance-established evidence', items: report?.supported_parameters || [] },
    { title: 'Partial support from unverified local records', items: report?.partially_supported_parameters || [] },
    { title: 'Unsupported by currently available conditions', items: report?.unsupported_parameters || [] },
  ];
  return (
    <div className="space-y-3">
      <p className="rounded-lg border border-amber-800/70 bg-amber-950/30 p-3 text-xs text-amber-200">Combined scenario: {report?.combined_scenario_status || 'not documented'} — {report?.combined_scenario_explanation || 'No retrieved source establishes that the full scenario was tested.'}</p>
      {groups.map((group) => (
        <div key={group.title}>
          <p className="mb-1 text-[10px] font-mono uppercase text-slate-500">{group.title}</p>
          {group.items.length ? (
            <ul className="space-y-2">
              {group.items.map((item) => (
                <li key={item.parameter} className="rounded-lg bg-space-panel p-3">
                  <p className="text-xs font-semibold text-slate-200">{item.parameter}: {item.scenario_value}</p>
                  <p className="mt-1 text-xs text-slate-300">{item.explanation}</p>
                  {item.available_evidence?.length > 0 && <p className="mt-1 text-[10px] text-slate-500">Available records: {item.available_evidence.join(' · ')}</p>}
                </li>
              ))}
            </ul>
          ) : <p className="text-xs text-slate-500">No parameters in this category.</p>}
        </div>
      ))}
      <DetailList title="Matching assumptions" items={report?.important_assumptions} />
    </div>
  );
}

export function ScenarioInputVisualization({ parameters }) {
  if (!parameters) return null;
  const measures = [
    { label: 'Oxygen concentration', value: parameters.oxygen_percent, unit: '%', min: 10, max: 40 },
    { label: 'Pressure', value: parameters.pressure_atm, unit: 'atm', min: 0.2, max: 1.5 },
    { label: 'Airflow', value: parameters.airflow_cm_s, unit: 'cm/s', min: 0, max: 50 },
  ];
  return (
    <section className="rounded-xl border border-space-border bg-space-panel p-4 space-y-3" aria-label="Scenario input visualization">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><h3 className="text-xs font-bold text-white">Scenario parameter view</h3><p className="text-[10px] text-slate-500">Environment: {parameters.environment} · {parameters.gravity} gravity · {parameters.material}</p></div>
        <span className="rounded border border-cyan-900 bg-cyan-950/30 px-2 py-1 text-[9px] font-mono uppercase text-cyan-200">Data-derived visualization</span>
      </div>
      <div className="space-y-3">
        {measures.map((item) => {
          const width = Math.max(0, Math.min(100, ((item.value - item.min) / (item.max - item.min)) * 100));
          return (
            <div key={item.label}>
              <div className="mb-1 flex items-center justify-between text-[11px]"><span className="text-slate-300">{item.label}</span><span className="font-mono text-cyan-200">{item.value} {item.unit}</span></div>
              <div className="h-2 overflow-hidden rounded bg-slate-900" role="img" aria-label={`${item.label}: ${item.value} ${item.unit}`}><div className="h-full rounded bg-cyan-500" style={{ width: `${width}%` }} /></div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] leading-relaxed text-slate-500">Bars map the user-entered values to the input control ranges shown above. They are not NASA observations, safety limits, or model output; no flame behavior is simulated.</p>
    </section>
  );
}

export function MissionResults({ analysis, loading, error, onRetry }) {
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState('');
  const reportReady = isCompleteMissionAnalysis(analysis);

  const downloadReport = async () => {
    if (!reportReady || reportLoading) return;
    setReportLoading(true);
    setReportError('');
    try {
      await downloadMissionAnalysisReport(analysis);
    } catch (downloadError) {
      setReportError(downloadError.message || 'The mission report could not be generated.');
    } finally {
      setReportLoading(false);
    }
  };

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-bold text-white">Mission-control results</h2>
        <p className="text-[11px] text-slate-500 font-mono uppercase tracking-wider">Five specialist roles and evidence gaps</p>
      </div>

      {loading && <p role="status" className="rounded-xl border border-cyan-800 bg-cyan-950/30 p-4 text-xs text-cyan-200">Retrieving research evidence and generating analyses…</p>}
      {error && <div role="alert" className="rounded-xl border border-red-800 bg-red-950/30 p-4 text-xs text-red-200"><p>{error}</p><button type="button" onClick={onRetry} className="mt-2 underline">Retry analysis</button></div>}
      {analysis && <div className="rounded-xl border border-amber-700/50 bg-amber-950/30 p-4 text-xs text-amber-100 space-y-1"><p className="font-semibold text-amber-200">{analysis.evidence_status}</p><p>Scenario values are hypothetical user inputs.</p>{analysis.evidence_limitations?.map((item, index) => <p key={index}>Limitation: {item}</p>)}</div>}
      {analysis?.evidence_validation_status === 'partial' && <div role="status" className="rounded-xl border border-orange-700 bg-orange-950/40 p-4 text-xs text-orange-100"><p className="font-semibold">Partial evidence validation — omitted claims are not included in the analysis.</p><ul className="mt-2 list-disc space-y-1 pl-4">{analysis.evidence_validation_issues?.map((item, index) => <li key={`validation-issue-${index}`}>{item}</li>)}</ul></div>}
      {analysis?.scenario_parameters && <p className="rounded-lg border border-space-border bg-space-panel px-3 py-2 text-[11px] text-slate-300">Submitted scenario: {analysis.scenario_parameters.environment} · O₂ {analysis.scenario_parameters.oxygen_percent}% · {analysis.scenario_parameters.pressure_atm} atm · {analysis.scenario_parameters.airflow_cm_s} cm/s · {analysis.scenario_parameters.gravity} gravity · {analysis.scenario_parameters.material}</p>}

      {analysis && <section className="rounded-xl border border-cyan-900/70 bg-space-panel p-4 space-y-3" aria-label="Mission control summary">
        <div><h3 className="text-xs font-bold uppercase text-cyan-200">Mission Control summary</h3><p className="mt-1 text-[10px] text-slate-400">{analysis.specialist_analyses?.length || 0}/5 specialist outputs · {analysis.evidence_matches?.length || 0} matched source records · {analysis.citations?.length || 0} citations</p></div>
        <p className="text-[10px] text-slate-400">Evidence coverage: {analysis.research_gaps?.supported_parameters?.length || 0} supported · {analysis.research_gaps?.partially_supported_parameters?.length || 0} partial · {analysis.research_gaps?.unsupported_parameters?.length || 0} unsupported parameters.</p>
        <p className="text-[10px] text-slate-500">Mission analysis history is not retained; this project has no mission-history storage.</p>
        <p className="text-[10px] text-slate-400">Retrieved NASA source references:</p>
        {analysis.citations?.length ? <ul className="flex flex-wrap gap-x-4 gap-y-1">{analysis.citations.map((citation) => <li key={citation.citation_id}><a href={citation.url || undefined} target="_blank" rel="noreferrer" className="text-[10px] text-cyan-300 hover:underline">{citation.title}</a></li>)}</ul> : <p className="text-[10px] text-slate-500">No source citations were retrieved for this scenario.</p>}
      </section>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {RESULT_SECTIONS.map((section) => {
          const Icon = section.icon;
          const specialist = analysis?.specialist_analyses?.find((item) => item.role === section.role);
          return (
            <article
              key={section.id}
              className={`rounded-xl border border-space-border bg-space-panel p-4 space-y-3 ${
                section.id === 'evidence' || section.id === 'synthesis' ? 'lg:col-span-2' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-cyan-950 border border-cyan-800 text-cyan-400"><Icon size={16} /></div>
                  <div><h3 className="text-sm font-semibold text-white">{section.title}</h3><p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{section.role}</p></div>
                </div>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">{loading ? 'RUNNING' : error && !analysis ? 'ERROR' : specialist?.evidence_validation_status === 'partial' ? 'PARTIAL' : specialist?.evidence_validation_status === 'no_valid_claims' ? 'NO VALID CLAIMS' : analysis ? 'COMPLETE' : 'STANDBY'}</span>
              </div>

              {analysis ? section.id === 'evidence' ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <p className="text-[10px] font-mono uppercase text-slate-500">Retrieved investigation records and condition matches</p>
                    {analysis.evidence_matches?.length ? analysis.evidence_matches.map((record) => <EvidenceRecordCard key={record.evidence_id} record={record} />) : <p className="text-xs text-slate-400">No relevant local investigation records were retrieved.</p>}
                  </div>
                  <div className="space-y-2"><p className="text-[10px] font-mono uppercase text-slate-500">Research gaps</p><ResearchGapGroups report={analysis.research_gaps} /></div>
                  <div className="space-y-2"><p className="text-[10px] font-mono uppercase text-slate-500">Retrieved citations and source metadata</p><CitationList citations={analysis.citations} /></div>
                </div>
              ) : section.id === 'synthesis' ? (
                <div className="space-y-4">
                  {specialist ? <div className="space-y-2"><p className="text-[10px] font-mono uppercase text-slate-500">Synthesizer analysis</p><p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">{specialist.analysis}</p><p className="text-[10px] font-mono text-amber-300">{specialist.evidence_status}</p><DetailList title="Synthesizer assumptions" items={specialist.assumptions} /><DetailList title="Synthesizer uncertainties" items={specialist.uncertainties} /><DetailList title="Synthesizer validation diagnostics" items={specialist.evidence_validation_diagnostics?.map(formatValidationDiagnostic)} /><CitationList citations={specialist.citations} /></div> : <p className="text-xs text-slate-400">The synthesizer result was not returned.</p>}
                  <div><p className="mb-1 text-[10px] font-mono uppercase text-slate-500">Combined mission assessment</p><p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">{analysis.mission_synthesis}</p></div>
                  <DetailList title="Main findings from retrieved records" items={analysis.synthesis_details?.main_documented_findings?.map((item) => item.finding)} />
                  <p className="text-xs text-slate-300">Conflict assessment: {analysis.synthesis_details?.conflict_assessment}</p>
                  <DetailList title="Conflicting specialist claims" items={analysis.synthesis_details?.conflicting_claims} />
                  <DetailList title="Important uncertainties" items={analysis.synthesis_details?.important_uncertainties} />
                  <DetailList title="Research gaps" items={analysis.synthesis_details?.research_gaps} />
                  <div><p className="mb-1 text-[10px] font-mono uppercase text-slate-500">Supporting citations</p><CitationList citations={analysis.synthesis_details?.supporting_citations} /></div>
                </div>
              ) : specialist ? (
                <div className="space-y-3">
                  <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">{specialist.analysis}</p>
                  <p className="text-[10px] font-mono text-amber-300">{specialist.evidence_status}</p>
                  {specialist.evidence_validation_issues?.length > 0 && <DetailList title="Omitted claims" items={specialist.evidence_validation_issues} />}
                  <DetailList title="Validation diagnostics" items={specialist.evidence_validation_diagnostics?.map(formatValidationDiagnostic)} />
                  <DetailList title="Relevant evidence" items={specialist.relevant_evidence?.map((item) => `${item.investigation_title} (${item.investigation_acronym}): ${item.relevance_explanation}`)} />
                  <DetailList title="Assumptions" items={specialist.assumptions} />
                  <DetailList title="Uncertainties" items={specialist.uncertainties} />
                  <div><p className="mb-1 text-[10px] font-mono uppercase text-slate-500">Citations</p><CitationList citations={specialist.citations} /></div>
                </div>
              ) : <p className="text-xs text-slate-400">This specialist result was not returned.</p> : (
                <p className="text-xs text-slate-500 leading-relaxed">{loading ? 'Analysis is in progress.' : 'Waiting for a generation request. No result is shown until the backend responds.'}</p>
              )}
            </article>
          );
        })}
      </div>
      {analysis && <section className="rounded-lg border border-slate-800 bg-space-panel p-3" aria-label="Earth impact information">
        <h3 className="text-[10px] font-bold uppercase text-slate-300">Earth impact · informational</h3>
        <p className="mt-1 text-[11px] text-slate-400">The retrieved combustion records do not provide validated Earth-impact factors for this mission scenario. No impact estimate is calculated.</p>
      </section>}
      {analysis?.disclaimer && <p className="text-[11px] text-slate-500">{analysis.disclaimer}</p>}
      {analysis && <section className="flex flex-col gap-3 rounded-xl border border-cyan-700/70 bg-cyan-950/30 p-4 sm:flex-row sm:items-center sm:justify-between" aria-label="Download current experiment report">
        <div>
          <h3 className="text-xs font-bold text-cyan-100">Report for the results shown above</h3>
          <p className="mt-1 text-[10px] text-slate-400">Includes this mission’s scenario, specialists, evidence, citations, research gaps, assumptions, and limitations.</p>
          {!reportReady && <p role="status" className="mt-1 text-[10px] text-amber-200">A complete, fully validated five-specialist result is required before creating the PDF.</p>}
          {reportError && <p role="alert" className="mt-1 text-xs text-red-300">{reportError}</p>}
        </div>
        <button type="button" onClick={downloadReport} disabled={reportLoading || !reportReady} aria-busy={reportLoading} className="inline-flex min-h-11 w-full shrink-0 items-center justify-center gap-2 rounded-lg border border-space-primary bg-space-primary px-4 py-2 text-xs font-semibold text-white hover:bg-space-primary-hover disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto">
          {reportLoading && <span aria-hidden="true" className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-cyan-200/40 border-t-cyan-100" />}
          {reportLoading ? 'Generating PDF…' : 'Download Experiment Report (PDF)'}
        </button>
      </section>}
    </section>
  );
}

export default function MissionIntelligenceView() {
  const [environmentId, setEnvironmentId] = useState(ENVIRONMENTS[0].id);
  const [oxygen, setOxygen] = useState(21);
  const [pressure, setPressure] = useState(1);
  const [airflow, setAirflow] = useState(10);
  const [gravity, setGravity] = useState(GRAVITY_OPTIONS[0].id);
  const [material, setMaterial] = useState(MATERIAL_OPTIONS[0].id);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const environment = ENVIRONMENTS.find((item) => item.id === environmentId);

  const handleGenerate = async (event) => {
    event?.preventDefault();
    setAnalysis(null);
    setError('');
    setLoading(true);
    try {
      const question = `Analyze hypothetical combustion behavior for ${material} in the ${environment.name} scenario at ${oxygen}% oxygen, ${pressure} atm pressure, and ${airflow} cm/s airflow under ${gravity} gravity.`;
      const response = await api.analyzeMission({
        environment: environment.name,
        oxygen_percent: Number(oxygen),
        pressure_atm: Number(pressure),
        airflow_cm_s: Number(airflow),
        gravity,
        material
      }, question);
      setAnalysis(response);
    } catch (err) {
      setError(err.message || 'Unable to connect to the mission analysis service.');
    } finally {
      setLoading(false);
    }
  };

  const clearAnalysis = () => { setAnalysis(null); setError(''); };

  return (
    <div className="space-y-6">
      <div className="bg-space-panel border border-space-border rounded-xl p-3.5 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs">
        <div className="flex items-start gap-2.5">
          <div className="p-1.5 rounded-lg bg-orange-950/80 border border-orange-800 text-orange-400 shrink-0">
            <AlertTriangle size={18} />
          </div>
          <div>
            <span className="font-semibold text-slate-200">Research guidance only. </span>
            <span className="text-slate-400">
              Parameter values below are hypothetical user inputs. They are not NASA experimental conditions, flight measurements, or certified spacecraft safety advice.
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 self-end md:self-auto shrink-0 font-mono text-[11px] text-orange-300 bg-orange-950/40 px-2.5 py-1 rounded border border-orange-900/60">
          <Info size={13} />
          <span>NOT A FLIGHT CLEARANCE</span>
        </div>
      </div>

      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-space-panel via-space-panel-raised to-space-panel border border-space-border p-6 lg:p-8 nasa-grid">
        <div className="max-w-3xl space-y-3 relative z-10">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cyan-950/60 border border-cyan-800 text-cyan-300 text-xs font-mono">
            <Radar className="w-3.5 h-3.5 text-orange-400" />
            <span>MISSION INTELLIGENCE ENGINE</span>
          </div>
          <h1 className="text-xl lg:text-2xl font-bold text-white tracking-tight">
            Mission-control research workspace
          </h1>
          <p className="text-sm text-slate-400 leading-relaxed">
            Set hypothetical research parameters to request a five-role analysis grounded in available local records and retrieved NASA publication metadata.
          </p>
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-white">Mission environments</h2>
            <p className="text-[11px] text-slate-500 font-mono uppercase tracking-wider">
              Hypothetical scenario selection
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {ENVIRONMENTS.map((item) => {
            const selected = item.id === environmentId;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setEnvironmentId(item.id);
                  clearAnalysis();
                }}
                className={`text-left rounded-xl p-4 border transition-colors ${
                  selected
                    ? 'bg-blue-600/15 border-cyan-500/40 glow-blue'
                    : 'bg-space-panel border-space-border hover:border-cyan-500/30 hover:bg-space-panel-raised'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-white">{item.name}</span>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                    selected ? 'bg-cyan-900/60 text-cyan-300' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {selected ? 'SELECTED' : 'SCENARIO'}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-300">{item.setting}</p>
                <p className="mt-1 text-[11px] text-slate-500">{item.note}</p>
              </button>
            );
          })}
        </div>
      </section>

      <form onSubmit={handleGenerate} className="rounded-2xl bg-space-panel border border-space-border p-4 lg:p-6 space-y-5">
        <div>
          <h2 className="text-sm font-bold text-white">Interactive research parameters</h2>
          <p className="text-[11px] text-slate-500 mt-1">
            Slider and menu limits are interface bounds for a hypothetical case. They are not documented NASA test envelopes.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <label className="block space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300">Oxygen concentration</span>
              <span className="font-mono text-cyan-300">{oxygen}%</span>
            </div>
            <input
              type="range"
              min="10"
              max="40"
              step="1"
              value={oxygen}
              onChange={(event) => {
                setOxygen(Number(event.target.value));
                clearAnalysis();
              }}
              className="w-full accent-cyan-400"
            />
            <span className="block text-[10px] font-mono text-slate-500">User input · percent · not a flight measurement</span>
          </label>

          <label className="block space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300">Ambient pressure</span>
              <span className="font-mono text-cyan-300">{pressure.toFixed(2)} atm</span>
            </div>
            <input
              type="range"
              min="0.2"
              max="1.5"
              step="0.05"
              value={pressure}
              onChange={(event) => {
                setPressure(Number(event.target.value));
                clearAnalysis();
              }}
              className="w-full accent-cyan-400"
            />
            <span className="block text-[10px] font-mono text-slate-500">User input · atmospheres · not a flight measurement</span>
          </label>

          <label className="block space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300">Ventilation airflow</span>
              <span className="font-mono text-cyan-300">{airflow} cm/s</span>
            </div>
            <input
              type="range"
              min="0"
              max="50"
              step="1"
              value={airflow}
              onChange={(event) => {
                setAirflow(Number(event.target.value));
                clearAnalysis();
              }}
              className="w-full accent-cyan-400"
            />
            <span className="block text-[10px] font-mono text-slate-500">User input · cm/s · not a flight measurement</span>
          </label>

          <label className="block space-y-2">
            <span className="text-xs text-slate-300">Gravity environment</span>
            <select
              value={gravity}
              onChange={(event) => {
                setGravity(event.target.value);
                clearAnalysis();
              }}
              className="w-full bg-space-panel border border-space-border rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              {GRAVITY_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </select>
            <span className="block text-[10px] font-mono text-slate-500">Scenario label · no numeric g-level is asserted</span>
          </label>

          <label className="block space-y-2 lg:col-span-2">
            <span className="text-xs text-slate-300">Fuel / material selection</span>
            <select
              value={material}
              onChange={(event) => {
                setMaterial(event.target.value);
                clearAnalysis();
              }}
              className="w-full bg-space-panel border border-space-border rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              {MATERIAL_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </select>
            <span className="block text-[10px] font-mono text-slate-500">
              Names match investigation families already in this project. Selecting one does not load a measured burn rate.
            </span>
          </label>
        </div>

        <ScenarioInputVisualization parameters={{
          environment: environment.name,
          oxygen_percent: oxygen,
          pressure_atm: pressure,
          airflow_cm_s: airflow,
          gravity,
          material,
        }} />

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-2 border-t border-space-border">
          <p className="text-[11px] text-slate-500 max-w-xl">
            Values are hypothetical scenario inputs. Returned analysis depends on available evidence and Gemini configuration.
          </p>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-space-primary hover:bg-space-primary-hover disabled:opacity-60 text-white text-xs font-semibold shadow-md transition-colors"
          >
            {loading ? 'Generating analysis…' : 'Generate Mission Intelligence'}
          </button>
        </div>
      </form>

      <MissionResults analysis={analysis} loading={loading} error={error} onRetry={handleGenerate} />
    </div>
  );
}
