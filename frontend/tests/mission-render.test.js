import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { after, before, test } from 'node:test';
import reactPlugin from '@vitejs/plugin-react';
import { createServer } from 'vite';

const roles = [
  'Combustion Analyst',
  'Atmosphere Analyst',
  'Material Safety Analyst',
  'Fire Suppression Analyst',
  'Mission Safety Synthesizer',
];

let vite;
let MissionResults;

before(async () => {
  vite = await createServer({
    configFile: false,
    root: process.cwd(),
    plugins: [reactPlugin()],
    server: { middlewareMode: true },
    appType: 'custom',
    logLevel: 'silent',
  });
  ({ MissionResults } = await vite.ssrLoadModule('/src/components/mission/MissionIntelligenceView.jsx'));
});

after(async () => {
  await vite?.close();
});

function analysisFixture() {
  return {
    environment: 'Lunar Habitat',
    scenario_parameters: {
      environment: 'Lunar Habitat',
      oxygen_percent: 34,
      pressure_atm: 0.56,
      airflow_cm_s: 15,
      gravity: 'lunar',
      material: 'pmma',
    },
    specialist_analyses: roles.map((role) => ({
      role,
      analysis: `${role} rendered analysis`,
      evidence_status: 'Local record — provenance unverified',
      evidence_validation_status: 'validated',
      evidence_validation_issues: [],
      evidence_validation_diagnostics: [],
      relevant_evidence: [{
        evidence_id: 'LOCAL-SAFFIRE',
        investigation_title: 'PMMA fixture record',
        investigation_acronym: 'SAFFIRE',
        original_source_url: 'https://example.test/source',
        evidence_status: 'Local record — provenance unverified',
        relevance_explanation: 'PMMA is mentioned; gravity differs.',
      }],
      assumptions: [`${role} assumption`],
      uncertainties: [`${role} uncertainty`],
      citations: [{
        citation_id: 'SAFFIRE:TEST-1',
        title: 'Fixture publication',
        source: 'Local publication record — provenance unverified',
        identifier: 'TEST-1',
        doi: '10.5555/fixture',
        url: 'https://example.test/paper',
        evidence_status: 'Local record — provenance unverified',
        relevance_explanation: 'Linked to the fixture investigation.',
      }],
    })),
    mission_synthesis: 'Combined mission assessment rendered.',
    synthesis_details: {
      combined_assessment: 'Combined mission assessment rendered.',
      conflict_assessment: 'No conflicts identified among the four specialist outputs.',
      main_documented_findings: [{ finding: 'Local record finding rendered.', citations: [] }],
      important_uncertainties: ['Uncertainty rendered.'],
      research_gaps: ['Gravity comparison is unsupported.'],
      conflicting_claims: ['Atmosphere Analyst and Combustion Analyst disagree about evidence coverage.'],
      supporting_citations: [],
    },
    evidence_matches: [{
      evidence_id: 'LOCAL-SAFFIRE',
      investigation_title: 'PMMA fixture record',
      investigation_acronym: 'SAFFIRE',
      original_source_url: 'https://example.test/source',
      experiment_type: 'Flammability',
      facility: 'Fixture',
      flight_mission: 'Test only',
      evidence_status: 'Local record — provenance unverified',
      evidence_class: 'local_provenance_unverified',
      relevance_explanation: 'Retrieved for material context.',
      parameter_matches: [{
        parameter: 'gravity',
        scenario_value: 'lunar',
        recorded_value: 'microgravity',
        status: 'different',
        explanation: 'Recorded gravity differs from the scenario.',
      }],
      publications: [],
      findings: [],
    }],
    research_gaps: {
      supported_parameters: [],
      partially_supported_parameters: [],
      unsupported_parameters: [{
        parameter: 'gravity',
        scenario_value: 'lunar',
        status: 'unsupported',
        available_evidence: [],
        explanation: 'No lunar-gravity condition is documented.',
      }],
      important_assumptions: ['Scenario values are hypothetical.'],
      combined_scenario_status: 'not_documented',
      combined_scenario_explanation: 'No source documents the combined scenario as tested.',
    },
    citations: [],
    evidence_status: 'Local evidence is provenance-unverified.',
    evidence_validation_status: 'complete',
    evidence_validation_issues: [],
    evidence_validation_diagnostics: [],
    evidence_limitations: ['No NASA PSI datasets were retrieved.'],
    disclaimer: 'Research support only.',
  };
}

test('mission results render all five specialists, synthesis, evidence, gaps, citations, and status', () => {
  const html = renderToStaticMarkup(React.createElement(MissionResults, {
    analysis: analysisFixture(),
    loading: false,
    error: '',
    onRetry: () => {},
  }));

  for (const role of roles) {
    assert.ok(html.includes(role), `missing role ${role}`);
    assert.ok(html.includes(`${role} rendered analysis`), `missing analysis for ${role}`);
  }
  assert.ok(html.includes('Combined mission assessment rendered.'));
  assert.ok(html.includes('O₂ 34% · 0.56 atm · 15 cm/s'));
  assert.ok(html.includes('Atmosphere Analyst and Combustion Analyst disagree'));
  assert.ok(html.includes('Conflict assessment: No conflicts identified'));
  assert.ok(html.includes('No source documents the combined scenario as tested.'));
  assert.ok(html.includes('PMMA fixture record'));
  assert.ok(html.includes('Recorded gravity differs from the scenario.'));
  assert.ok(html.includes('No lunar-gravity condition is documented.'));
  assert.ok(html.includes('Local evidence is provenance-unverified.'));
  assert.ok(html.includes('No NASA PSI datasets were retrieved.'));
});

test('mission results disclose partial claim validation and disable a complete-report download', () => {
  const partial = analysisFixture();
  partial.evidence_validation_status = 'partial';
  partial.evidence_validation_issues = ['Combustion Analyst: one claim was omitted.'];
  partial.specialist_analyses[0].evidence_validation_status = 'partial';
  partial.specialist_analyses[0].evidence_validation_issues = ['Source citation did not match.'];
  partial.specialist_analyses[0].evidence_validation_diagnostics = [{
    role: 'Combustion Analyst',
    claim_index: 0,
    claim_classification: 'evidence_summary',
    reason_code: 'mismatched_investigation',
    reason: 'claim citation belongs to another investigation',
    evidence_references_supplied: true,
    evidence_ids_valid: true,
    citation_ids_supplied: true,
    citation_ids_valid: true,
    citation_investigation_match: false,
    provenance_restriction_rejected: false,
    historical_source_text_match: null,
  }];
  const html = renderToStaticMarkup(React.createElement(MissionResults, {
    analysis: partial,
    loading: false,
    error: '',
    onRetry: () => {},
  }));

  assert.ok(html.includes('Partial evidence validation'));
  assert.ok(html.includes('Source citation did not match.'));
  assert.ok(html.includes('mismatched_investigation'));
  assert.ok(html.includes('investigation match no'));
  assert.ok(html.includes('PARTIAL'));
  assert.ok(html.includes('A complete, fully validated five-specialist result is required'));
  assert.match(html, /Download Experiment Report \(PDF\)<\/button>/);
  assert.match(html, /disabled=""/);
});

test('mission results render loading and error states without fallback analysis', () => {
  const loading = renderToStaticMarkup(React.createElement(MissionResults, {
    analysis: null,
    loading: true,
    error: '',
    onRetry: () => {},
  }));
  assert.ok(loading.includes('role="status"'));
  assert.ok(loading.includes('Retrieving research evidence'));
  assert.ok(!loading.includes('Combustion Analyst rendered analysis'));

  const error = renderToStaticMarkup(React.createElement(MissionResults, {
    analysis: null,
    loading: false,
    error: 'Gemini is not configured.',
    onRetry: () => {},
  }));
  assert.ok(error.includes('role="alert"'));
  assert.ok(error.includes('Gemini is not configured.'));
  assert.ok(!error.includes('fabricated fallback'));
});
