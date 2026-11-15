import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { after, before, test } from 'node:test';
import reactPlugin from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let api;
let StoredExperimentCard;
let ExperimentComparisonResult;
let ExperimentFeedback;
let ScenarioInputVisualization;
let MissionResults;
let downloadMissionAnalysisReport;
let isCompleteMissionAnalysis;
let downloadExperimentComparisonReport;
let isCompleteExperimentComparison;
let triggerPdfDownload;

before(async () => {
  vite = await createServer({
    configFile: false,
    root: process.cwd(),
    plugins: [reactPlugin()],
    server: { middlewareMode: true },
    appType: 'custom',
    logLevel: 'silent',
  });
  ({ api } = await vite.ssrLoadModule('/src/services/api.js'));
  ({ StoredExperimentCard, ExperimentComparisonResult, ExperimentFeedback } = await vite.ssrLoadModule('/src/components/explorer/StoredNasaExperiments.jsx'));
  ({ ScenarioInputVisualization, MissionResults } = await vite.ssrLoadModule('/src/components/mission/MissionIntelligenceView.jsx'));
  ({ downloadMissionAnalysisReport, isCompleteMissionAnalysis, downloadExperimentComparisonReport, isCompleteExperimentComparison, triggerPdfDownload } = await vite.ssrLoadModule('/src/services/pdfDownload.js'));
});

after(async () => {
  await vite?.close();
});

function withFetch(handler, action) {
  const previous = globalThis.fetch;
  globalThis.fetch = handler;
  return Promise.resolve().then(action).finally(() => { globalThis.fetch = previous; });
}

const record = {
  record_id: 21,
  source_record_id: 'PSI-69',
  source_name: 'NASA PSI',
  title: 'Flame Extinguishment Experiment',
  source_url: 'https://psi.nasa.gov/physci/repo/data/investigations/PSI-69',
  provenance_category: 'nasa_origin_source_link_verified',
  evidence_status: 'Source linkage is recorded; measurements are not independently validated.',
  experiment_type: 'Microgravity Investigation',
  experiment_context_type: 'flight_experiment',
  material: null,
  gravity_environment: null,
  environment: null,
};

test('stored NASA explorer renders provenance and missing structured conditions', () => {
  const html = renderToStaticMarkup(React.createElement(StoredExperimentCard, {
    record, selected: false, compareDisabled: false, onSelect: () => {}, onOpen: () => {},
  }));
  assert.ok(html.includes('NASA PSI source record'));
  assert.ok(html.includes('measurement provenance not independently validated'));
  assert.ok(html.includes('Gravity: not structured'));
  assert.ok(html.includes('Open original NASA source'));
});

test('comparison display reports when no compatible measured conditions are present', () => {
  const html = renderToStaticMarkup(React.createElement(ExperimentComparisonResult, {
    comparison: {
      left: { title: 'PSI record' }, right: { title: 'NTRS record' },
      categorical_comparisons: [], quantitative_comparisons: [],
      limitations: [
        'No shared structured numeric conditions with compatible, source-recorded units are available.',
        'This comparison does not establish scientific equivalence or show that the combined conditions were tested.',
      ],
    },
  }));
  assert.ok(html.includes('No shared quantitative conditions with compatible source-recorded units.'));
  assert.ok(html.includes('scientific equivalence'));
});

test('experiment explorer has visible loading, error, and empty states without sample data', () => {
  const loading = renderToStaticMarkup(React.createElement(ExperimentFeedback, { loading: true, error: '', hasRecords: false }));
  const error = renderToStaticMarkup(React.createElement(ExperimentFeedback, { loading: false, error: 'NASA source unavailable.', hasRecords: false }));
  const empty = renderToStaticMarkup(React.createElement(ExperimentFeedback, { loading: false, error: '', hasRecords: false }));
  assert.ok(loading.includes('role="status"'));
  assert.ok(error.includes('role="alert"'));
  assert.ok(error.includes('NASA source unavailable.'));
  assert.ok(empty.includes('No synthetic experiment records'));
});

test('scenario visual changes with the exact input and is labelled data-derived', () => {
  const base = { environment: 'Lunar Habitat', oxygen_percent: 21, pressure_atm: 0.56, airflow_cm_s: 15, gravity: 'lunar', material: 'pmma' };
  const changed = { ...base, oxygen_percent: 34 };
  const first = renderToStaticMarkup(React.createElement(ScenarioInputVisualization, { parameters: base }));
  const second = renderToStaticMarkup(React.createElement(ScenarioInputVisualization, { parameters: changed }));
  assert.ok(first.includes('Data-derived visualization'));
  assert.ok(first.includes('21 %'));
  assert.ok(second.includes('34 %'));
  assert.notEqual(first.match(/width:([0-9.]+)%/)?.[1], second.match(/width:([0-9.]+)%/)?.[1]);
  assert.ok(second.includes('not NASA observations, safety limits, or model output'));
});

test('NASA record API serializes search and source filters and comparison IDs', async () => {
  const calls = [];
  await withFetch(async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return new Response(JSON.stringify({ records: [], available_filters: { source: [] }, conditions_notice: 'Structured source data only.' }), { status: 200 });
  }, async () => {
    await api.getStoredExperiments({ search: 'PSI 69', source: 'NASA PSI', gravity: '' });
    await api.compareStoredExperiments([21, 22]);
  });
  assert.ok(calls[0].url.includes('/api/experiments?'));
  assert.ok(calls[0].url.includes('search=PSI+69'));
  assert.ok(calls[0].url.includes('source=NASA+PSI'));
  assert.equal(calls[1].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls[1].options.body), { record_ids: [21, 22] });
});

test('mission report client downloads a backend-generated PDF and exposes errors', async () => {
  const analysis = { environment: 'Lunar Habitat', scenario_parameters: { pressure_atm: 0.56 } };
  const pdf = await withFetch(async (url, options) => {
    assert.ok(String(url).includes('/api/reports/mission'));
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), analysis);
    return new Response(new Blob(['%PDF-1.4\n']), { status: 200, headers: { 'Content-Type': 'application/pdf' } });
  }, () => api.createMissionReport(analysis));
  assert.equal(pdf.type, 'application/pdf');
  assert.equal(await pdf.text(), '%PDF-1.4\n');

  await withFetch(async () => new Response(JSON.stringify({ detail: 'Invalid mission report.' }), { status: 422 }), async () => {
    await assert.rejects(api.createMissionReport(analysis), /Invalid mission report/);
  });
});

const completeMissionResult = {
  environment: 'Lunar Habitat',
  scenario_parameters: { environment: 'Lunar Habitat', oxygen_percent: 34, pressure_atm: 0.56, airflow_cm_s: 15, gravity: 'lunar', material: 'pmma' },
  specialist_analyses: [
    'Combustion Analyst', 'Atmosphere Analyst', 'Material Safety Analyst', 'Fire Suppression Analyst', 'Mission Safety Synthesizer',
  ].map((role) => ({ role, analysis: `${role}: insufficient evidence.`, assumptions: ['Scenario is hypothetical.'], uncertainties: ['No combined experimental evidence.'], citations: [] })),
  citations: [], evidence_matches: [],
  research_gaps: { supported_parameters: [], partially_supported_parameters: [], unsupported_parameters: [], important_assumptions: ['Scenario is hypothetical.'] },
  evidence_status: 'Insufficient evidence', evidence_limitations: ['No retrieved source documents this combined scenario.'],
  mission_synthesis: 'No source documented this scenario.',
  synthesis_details: { combined_assessment: 'Insufficient evidence.', main_documented_findings: [], conflicting_claims: [], important_uncertainties: [], research_gaps: [], supporting_citations: [], conflict_assessment: 'No conflicts identified.' },
  disclaimer: 'Research only.',
};

const experimentComparison = {
  left: { record_id: 21, source_record_id: 'PSI-69', title: 'FLEX PSI Record' },
  right: { record_id: 22, source_record_id: 'NTRS-123', title: 'Combustion Publication' },
  categorical_comparisons: [], quantitative_comparisons: [], limitations: ['No compatible measured conditions are available.'],
};

function fakeBrowserDownload() {
  const calls = { created: [], appended: [], clicked: 0, removed: 0, revoked: [], scheduled: [] };
  const browser = {
    documentRef: {
      body: { appendChild: (link) => calls.appended.push(link) },
      createElement: () => ({ style: {}, click: () => { calls.clicked += 1; }, remove: () => { calls.removed += 1; } }),
    },
    urlApi: {
      createObjectURL: (pdf) => { calls.created.push(pdf); return 'blob:test-report'; },
      revokeObjectURL: (url) => calls.revoked.push(url),
    },
    setTimeoutFn: (callback, delay) => { calls.scheduled.push(delay); callback(); },
  };
  return { browser, calls };
}

test('mission control exposes the report action only for complete current results', () => {
  const html = renderToStaticMarkup(React.createElement(MissionResults, {
    analysis: completeMissionResult,
    loading: false, error: '', onRetry: () => {},
  }));
  assert.ok(html.includes('Download Experiment Report (PDF)'));
  assert.ok(html.includes('Mission analysis history is not retained'));
  assert.ok(html.includes('Earth impact · informational'));
  assert.ok(isCompleteMissionAnalysis(completeMissionResult));

  const incompleteHtml = renderToStaticMarkup(React.createElement(MissionResults, {
    analysis: { ...completeMissionResult, specialist_analyses: [] },
    loading: false, error: '', onRetry: () => {},
  }));
  assert.ok(incompleteHtml.includes('Download Experiment Report (PDF)'));
  assert.ok(incompleteHtml.includes('disabled=""'));
  assert.ok(incompleteHtml.includes('complete, fully validated five-specialist result is required'));

  const missingParameterHtml = renderToStaticMarkup(React.createElement(MissionResults, {
    analysis: { ...completeMissionResult, scenario_parameters: { environment: 'Lunar Habitat' } },
    loading: false, error: '', onRetry: () => {},
  }));
  assert.ok(missingParameterHtml.includes('disabled=""'));

  const emptyHtml = renderToStaticMarkup(React.createElement(MissionResults, {
    analysis: null, loading: false, error: '', onRetry: () => {},
  }));
  assert.ok(!emptyHtml.includes('Download Experiment Report (PDF)'));
});

test('completed current mission result is sent to PDF endpoint and downloaded', async () => {
  const { browser, calls } = fakeBrowserDownload();
  const pdf = new Blob(['%PDF-1.4\ncurrent mission'], { type: 'application/pdf' });
  await withFetch(async (url, options) => {
    assert.ok(String(url).includes('/api/reports/mission?report_name=Lunar%20Habitat%20Mission%20Intelligence%20Report'));
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), completeMissionResult);
    return new Response(pdf, { status: 200, headers: { 'Content-Type': 'application/pdf' } });
  }, async () => downloadMissionAnalysisReport(completeMissionResult, browser));

  assert.equal(calls.created[0].type, 'application/pdf');
  assert.equal(calls.appended[0].download, 'flame-lunar-habitat-mission-experiment-report.pdf');
  assert.equal(calls.clicked, 1);
  assert.equal(calls.removed, 1);
  assert.deepEqual(calls.revoked, ['blob:test-report']);
  assert.deepEqual(calls.scheduled, [1000]);
});

test('experiment comparison result downloads a PDF for its two displayed stored records', async () => {
  const { browser, calls } = fakeBrowserDownload();
  const html = renderToStaticMarkup(React.createElement(ExperimentComparisonResult, { comparison: experimentComparison }));
  assert.ok(html.includes('Download Experiment Report (PDF)'));
  assert.ok(html.includes('FLEX PSI Record ↔ Combustion Publication'));
  assert.ok(isCompleteExperimentComparison(experimentComparison));

  await withFetch(async (url, options) => {
    assert.ok(String(url).includes('/api/reports/experiments/compare'));
    assert.deepEqual(JSON.parse(options.body), { record_ids: [21, 22] });
    return new Response(new Blob(['%PDF-1.4\ncomparison'], { type: 'application/pdf' }), {
      status: 200, headers: { 'Content-Type': 'application/pdf' },
    });
  }, async () => downloadExperimentComparisonReport(experimentComparison, browser));

  assert.equal(calls.appended[0].download, 'flame-flex-psi-record-vs-combustion-publication-experiment-comparison-report.pdf');
  assert.equal(calls.clicked, 1);
  assert.equal(calls.removed, 1);

  const incompleteHtml = renderToStaticMarkup(React.createElement(ExperimentComparisonResult, {
    comparison: { ...experimentComparison, right: { title: 'No stored ID' } },
  }));
  assert.ok(incompleteHtml.includes('Download Experiment Report (PDF)'));
  assert.ok(incompleteHtml.includes('disabled=""'));
  assert.ok(incompleteHtml.includes('complete comparison of two stored records is required'));
  await assert.rejects(downloadExperimentComparisonReport(null, browser), /complete comparison/);
});

test('PDF download helper reports unavailable browser capabilities and non-PDF responses', () => {
  assert.throws(() => triggerPdfDownload(new Blob(['not pdf'], { type: 'text/plain' }), 'bad.pdf', {}), /invalid PDF/);
  assert.throws(() => triggerPdfDownload(new Blob(['%PDF'], { type: 'application/pdf' }), 'report.pdf', {
    documentRef: null,
    urlApi: { createObjectURL: () => 'blob:test' },
  }), /cannot download/);
});
