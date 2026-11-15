import React, { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { downloadExperimentComparisonReport, isCompleteExperimentComparison } from '../../services/pdfDownload';

const emptyFilters = { source: [], material: [], gravity: [], environment: [] };

function ProvenanceLabel({ record }) {
  const label = record.provenance_category === 'publication_metadata_only'
    ? 'NASA NTRS publication metadata'
    : 'NASA PSI source record · measurement provenance not independently validated';
  return <span className="inline-flex rounded border border-amber-800 bg-amber-950/40 px-2 py-1 text-[10px] text-amber-200">{label}</span>;
}

export function StoredExperimentCard({ record, selected, compareDisabled, onSelect, onOpen }) {
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-space-border bg-space-panel p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-mono uppercase text-cyan-300">{record.source_name} · {record.source_record_id}</p>
          <h3 className="mt-1 text-sm font-semibold text-white">{record.title}</h3>
        </div>
        <label className="flex items-center gap-1 text-[10px] text-slate-400">
          <input
            aria-label={`Select ${record.title} for comparison`}
            type="checkbox"
            checked={selected}
            disabled={compareDisabled}
            onChange={() => onSelect(record.record_id)}
          />
          Compare
        </label>
      </div>
      <ProvenanceLabel record={record} />
      <p className="text-xs text-slate-400">{record.experiment_type || 'Experiment type unavailable'} · {record.experiment_context_type || 'Context unavailable'}</p>
      <p className="text-[11px] text-slate-500">
        Material: {record.material || 'not structured'} · Gravity: {record.gravity_environment || 'not structured'} · Environment: {record.environment || 'not structured'}
      </p>
      <div className="mt-auto flex items-center justify-between gap-3 border-t border-space-border pt-3">
        <a className="truncate text-[10px] text-cyan-300 hover:underline" href={record.source_url || undefined} target="_blank" rel="noreferrer">
          {record.source_url ? 'Open original NASA source' : 'No source URL supplied'}
        </a>
        <button type="button" onClick={() => onOpen(record.record_id)} className="shrink-0 rounded border border-cyan-900 px-2.5 py-1.5 text-[10px] text-cyan-200 hover:border-cyan-500">
          Record details
        </button>
      </div>
    </article>
  );
}

export function ExperimentComparisonResult({ comparison }) {
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState('');
  if (!comparison) return null;
  const reportReady = isCompleteExperimentComparison(comparison);

  const downloadReport = async () => {
    if (!reportReady || reportLoading) return;
    setReportLoading(true);
    setReportError('');
    try {
      await downloadExperimentComparisonReport(comparison);
    } catch (error) {
      setReportError(error.message || 'The experiment comparison report could not be generated.');
    } finally {
      setReportLoading(false);
    }
  };

  return (
    <section className="space-y-3 rounded-xl border border-cyan-900/70 bg-cyan-950/20 p-4" aria-label="NASA record comparison">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-sm font-semibold text-white">Structured record comparison</h3>
        <button type="button" onClick={downloadReport} disabled={!reportReady || reportLoading} aria-busy={reportLoading} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-cyan-700 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-900/40 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto">
          {reportLoading && <span aria-hidden="true" className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-cyan-200/40 border-t-cyan-100" />}
          {reportLoading ? 'Generating PDF…' : 'Download Experiment Report (PDF)'}
        </button>
      </div>
      {!reportReady && <p role="status" className="text-[10px] text-amber-200">A complete comparison of two stored records is required before creating the PDF.</p>}
      {reportError && <p role="alert" className="text-xs text-red-300">{reportError}</p>}
      <p className="text-xs text-slate-300">{comparison.left.title} ↔ {comparison.right.title}</p>
      {comparison.categorical_comparisons?.length > 0 && (
        <ul className="space-y-1 text-xs text-slate-300">
          {comparison.categorical_comparisons.map((item) => <li key={item.field}>{item.field}: {item.left_value} / {item.right_value} ({item.relationship})</li>)}
        </ul>
      )}
      {comparison.quantitative_comparisons?.length > 0 ? (
        <ul className="space-y-1 text-xs text-slate-300">
          {comparison.quantitative_comparisons.map((item) => <li key={item.field}>{item.field}: {item.left_value} / {item.right_value} {item.unit} ({item.relationship})</li>)}
        </ul>
      ) : <p className="text-xs text-amber-200">No shared quantitative conditions with compatible source-recorded units.</p>}
      <ul className="list-disc space-y-1 pl-4 text-[11px] text-slate-400">
        {comparison.limitations?.map((item, index) => <li key={index}>{item}</li>)}
      </ul>
    </section>
  );
}

export function ExperimentFeedback({ loading, error, hasRecords }) {
  if (loading) return <p role="status" className="rounded-lg border border-cyan-900 bg-cyan-950/20 p-3 text-xs text-cyan-200">Loading stored NASA records…</p>;
  if (error) return <p role="alert" className="rounded-lg border border-red-900 bg-red-950/20 p-3 text-xs text-red-200">{error}</p>;
  if (!hasRecords) return <p className="rounded-lg border border-space-border bg-space-panel p-4 text-xs text-slate-400">No stored NASA records match these filters. No synthetic experiment records are added to empty results.</p>;
  return null;
}

function ExperimentDetail({ record, onClose }) {
  if (!record) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="stored-record-title" className="max-h-[85vh] w-full max-w-3xl space-y-4 overflow-y-auto rounded-2xl border border-space-border bg-space-panel p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-mono text-cyan-300">{record.source_name} · {record.source_record_id}</p>
            <h2 id="stored-record-title" className="mt-1 text-base font-bold text-white">{record.title}</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300">Close</button>
        </div>
        <ProvenanceLabel record={record} />
        <p className="text-xs leading-relaxed text-slate-300">{record.description || 'No description or abstract is stored for this record.'}</p>
        <div className="grid gap-2 rounded-lg bg-space-panel p-3 text-[11px] text-slate-300 sm:grid-cols-2">
          <p>Experiment type: {record.experiment_type || 'unavailable'}</p>
          <p>Context: {record.experiment_context_type || 'unavailable'}</p>
          <p>Material: {record.material || 'unavailable'}</p>
          <p>Gravity: {record.gravity_environment || 'unavailable'}</p>
          <p>Environment: {record.environment || 'unavailable'}</p>
          <p>Retrieved: {record.retrieved_at || 'timestamp unavailable'}</p>
          <p>Source register: {record.retrieval_status} · HTTP {record.retrieval_http_status ?? 'not recorded'}</p>
        </div>
        <div>
          <h3 className="mb-2 text-xs font-bold uppercase text-slate-400">Missing structured conditions</h3>
          <p className="text-xs text-amber-200">{record.missing_data?.length ? record.missing_data.join(' · ') : 'No listed condition gaps.'}</p>
        </div>
        <div>
          <h3 className="mb-2 text-xs font-bold uppercase text-slate-400">NASA source and publication references</h3>
          <ul className="space-y-2">
            {record.citations?.map((citation, index) => (
              <li key={`${citation.identifier || citation.title}-${index}`} className="rounded-lg bg-space-panel p-3 text-xs">
                {citation.url ? <a href={citation.url} target="_blank" rel="noreferrer" className="font-semibold text-cyan-300 hover:underline">{citation.title}</a> : <p className="font-semibold text-slate-200">{citation.title}</p>}
                <p className="mt-1 text-[10px] text-slate-400">{citation.evidence_type}{citation.identifier ? ` · ${citation.identifier}` : ''}{citation.doi ? ` · DOI ${citation.doi}` : ''}{citation.year ? ` · ${citation.year}` : ''}</p>
              </li>
            ))}
          </ul>
        </div>
        {record.dataset_files?.length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-bold uppercase text-slate-400">PSI dataset files</h3>
            <ul className="space-y-2">
              {record.dataset_files.map((file) => (
                <li key={file.file_name} className="rounded-lg bg-space-panel p-3 text-xs">
                  {file.source_url ? <a href={file.source_url} target="_blank" rel="noreferrer" className="text-cyan-300 hover:underline">{file.file_name}</a> : <span>{file.file_name}</span>}
                  <p className="mt-1 text-[10px] text-slate-300">{file.retrieval_status === 'retrieved' ? `Raw file stored (${file.raw_size_bytes} bytes)` : 'Source link present; raw file not stored'} · measurements parsed: {file.measurements_parsed ? 'yes' : 'no'}</p>
                  <p className="mt-1 text-[10px] text-slate-500">{file.note}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="border-t border-space-border pt-3 text-[10px] text-slate-500">{record.evidence_status}</p>
      </section>
    </div>
  );
}

export default function StoredNasaExperiments() {
  const [search, setSearch] = useState('');
  const [source, setSource] = useState('');
  const [material, setMaterial] = useState('');
  const [gravity, setGravity] = useState('');
  const [environment, setEnvironment] = useState('');
  const queryKey = JSON.stringify({ search, source, material, gravity, environment });
  const [recordState, setRecordState] = useState({ key: null, response: null, error: '' });
  const [selectedIds, setSelectedIds] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

  const loading = recordState.key !== queryKey;
  const error = loading ? '' : recordState.error;
  const records = loading ? [] : recordState.response?.records || [];
  const filters = loading ? emptyFilters : recordState.response?.available_filters || emptyFilters;
  const conditionsNotice = recordState.response?.conditions_notice || 'Filters and comparisons use structured values saved with NASA records.';

  useEffect(() => {
    let active = true;
    api.getStoredExperiments({ search, source, material, gravity, environment })
      .then((response) => { if (active) setRecordState({ key: queryKey, response, error: '' }); })
      .catch((requestError) => { if (active) setRecordState({ key: queryKey, response: null, error: requestError.message || 'NASA records could not be loaded.' }); });
    return () => { active = false; };
  }, [search, source, material, gravity, environment, queryKey]);

  const toggleRecord = (recordId) => {
    setSelectedIds((current) => current.includes(recordId)
      ? current.filter((id) => id !== recordId)
      : current.length < 2 ? [...current, recordId] : current);
    setComparison(null);
    setComparisonError('');
  };

  const openDetail = async (recordId) => {
    setDetailLoading(true);
    setDetail(null);
    setDetailError('');
    try {
      setDetail(await api.getStoredExperiment(recordId));
    } catch (requestError) {
      setDetailError(requestError.message || 'NASA record detail could not be loaded.');
    } finally {
      setDetailLoading(false);
    }
  };

  const compareSelected = async () => {
    setComparisonLoading(true);
    setComparisonError('');
    try {
      setComparison(await api.compareStoredExperiments(selectedIds));
    } catch (requestError) {
      setComparisonError(requestError.message || 'The selected records could not be compared.');
    } finally {
      setComparisonLoading(false);
    }
  };

  const filterSelect = (label, value, values, setValue) => (
    <label className="space-y-1 text-[10px] text-slate-400">
      <span className="block">{label}</span>
      <select value={value} onChange={(event) => setValue(event.target.value)} disabled={!values.length} className="w-full rounded-lg border border-space-border bg-space-panel px-2 py-2 text-xs text-slate-200 disabled:opacity-60">
        <option value="">All / unavailable</option>
        {values.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
    </label>
  );

  return (
    <section className="space-y-4" aria-label="Stored NASA experiment explorer">
      <div className="rounded-xl border border-space-border bg-space-panel p-4">
        <h2 className="text-sm font-bold text-white">Retrieved NASA PSI and NTRS records</h2>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-400">Searches actual stored source snapshots and normalized metadata. NASA NTRS results are publication metadata; NASA PSI source linkage does not independently validate measurements.</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <label className="space-y-1 text-[10px] text-slate-400 lg:col-span-1"><span className="block">Search</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Title, identifier, abstract" className="w-full rounded-lg border border-space-border bg-space-panel px-2 py-2 text-xs text-slate-200" /></label>
          {filterSelect('Source', source, filters.source, setSource)}
          {filterSelect('Material (structured)', material, filters.material, setMaterial)}
          {filterSelect('Gravity (structured)', gravity, filters.gravity, setGravity)}
          {filterSelect('Environment (structured)', environment, filters.environment, setEnvironment)}
        </div>
        {(!filters.material.length || !filters.gravity.length || !filters.environment.length) && <p className="mt-3 text-[10px] text-amber-200">Some condition filters have no options because the stored records do not contain those structured values; narrative text is not guessed into filter values.</p>}
        <p className="mt-2 text-[10px] text-slate-500">{records.length} stored records · {selectedIds.length}/2 selected for comparison</p>
        <p className="mt-1 text-[10px] text-slate-500">Structured condition matching only; no numeric similarity score. {conditionsNotice}</p>
        <button type="button" disabled={selectedIds.length !== 2 || comparisonLoading} onClick={compareSelected} className="mt-3 rounded-lg border border-cyan-800 px-3 py-2 text-[11px] font-semibold text-cyan-200 disabled:opacity-50">{comparisonLoading ? 'Comparing…' : 'Compare selected records'}</button>
        {comparisonError && <p role="alert" className="mt-2 text-xs text-red-300">{comparisonError}</p>}
      </div>

      <ExperimentFeedback loading={loading} error={error} hasRecords={records.length > 0} />
      {detailError && <p role="alert" className="rounded-lg border border-red-900 bg-red-950/20 p-3 text-xs text-red-200">{detailError}</p>}
      {!loading && records.length > 0 && <div className="grid gap-3 md:grid-cols-2">{records.map((record) => <StoredExperimentCard key={record.record_id} record={record} selected={selectedIds.includes(record.record_id)} compareDisabled={selectedIds.length >= 2 && !selectedIds.includes(record.record_id)} onSelect={toggleRecord} onOpen={openDetail} />)}</div>}
      <ExperimentComparisonResult comparison={comparison} />
      {detailLoading && <p role="status" className="text-xs text-slate-400">Loading source-linked record details…</p>}
      <ExperimentDetail record={detail} onClose={() => setDetail(null)} />
    </section>
  );
}
