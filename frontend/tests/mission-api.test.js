import assert from 'node:assert/strict';
import test from 'node:test';

import { api } from '../src/services/api.js';

const specialistRoles = [
  'Combustion Analyst',
  'Atmosphere Analyst',
  'Material Safety Analyst',
  'Fire Suppression Analyst',
  'Mission Safety Synthesizer',
];

const parameters = {
  environment: 'Lunar Habitat',
  oxygen_percent: 34.0,
  pressure_atm: 0.56,
  airflow_cm_s: 15.0,
  gravity: 'lunar',
  material: 'pmma',
};
const question = 'How does 34% oxygen affect PMMA combustion in a lunar habitat?';

function mockMissionResponse() {
  return {
    environment: 'Lunar Habitat',
    scenario_parameters: { ...parameters },
    specialist_analyses: specialistRoles.map((role) => ({
      role,
      analysis: 'Insufficient evidence for a scientific conclusion.',
      evidence_status: 'Insufficient evidence',
      evidence_validation_status: 'validated',
      evidence_validation_issues: [],
      evidence_validation_diagnostics: [],
      relevant_evidence: [],
      assumptions: ['Scenario values are hypothetical.'],
      uncertainties: ['No verified measurements were retrieved.'],
      citations: [],
    })),
    mission_synthesis: 'Insufficient evidence for a scientific conclusion.',
    synthesis_details: {
      combined_assessment: 'Insufficient evidence for a scientific conclusion.',
      conflict_assessment: 'No conflicts identified among the four specialist outputs.',
      main_documented_findings: [],
      important_uncertainties: ['No verified measurements were retrieved.'],
      research_gaps: ['No local records were retrieved.'],
      conflicting_claims: [],
      supporting_citations: [],
    },
    citations: [],
    evidence_matches: [],
    research_gaps: {
      supported_parameters: [],
      partially_supported_parameters: [],
      unsupported_parameters: [],
      important_assumptions: ['Scenario values are hypothetical.'],
      combined_scenario_status: 'not_documented',
      combined_scenario_explanation: 'The combined scenario is not documented as tested.',
    },
    evidence_status: 'Insufficient evidence',
    evidence_validation_status: 'complete',
    evidence_validation_issues: [],
    evidence_validation_diagnostics: [],
    evidence_limitations: ['No verified measurements were retrieved.'],
    disclaimer: 'Research guidance only.',
  };
}

test('mission client sends the nested request and accepts the five-role response contract', async () => {
  const previousFetch = globalThis.fetch;
  let requestedUrl;
  let requestedOptions;
  const responseBody = mockMissionResponse();
  globalThis.fetch = async (url, options) => {
    requestedUrl = url;
    requestedOptions = options;
    return { ok: true, json: async () => responseBody };
  };

  try {
    const response = await api.analyzeMission(parameters, question);
    assert.equal(requestedUrl, '/api/mission/analyze');
    assert.deepEqual(JSON.parse(requestedOptions.body), { parameters, question });
    assert.deepEqual(response, responseBody);
    assert.deepEqual(
      response.specialist_analyses.map((item) => item.role),
      specialistRoles,
    );
    assert.equal(typeof response.mission_synthesis, 'string');
    assert.ok(Array.isArray(response.citations));
    assert.equal(typeof response.evidence_status, 'string');
    assert.equal(response.evidence_validation_status, 'complete');
    assert.equal(typeof response.disclaimer, 'string');
    assert.ok(Array.isArray(response.evidence_matches));
    assert.ok(Array.isArray(response.research_gaps.unsupported_parameters));
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('mission client accepts an explicitly partial result without treating it as complete', async () => {
  const previousFetch = globalThis.fetch;
  const partialResponse = mockMissionResponse();
  partialResponse.evidence_validation_status = 'partial';
  partialResponse.evidence_validation_issues = ['Combustion Analyst: one claim was omitted.'];
  partialResponse.specialist_analyses[0].evidence_validation_status = 'partial';
  partialResponse.specialist_analyses[0].evidence_validation_issues = ['Evidence link missing.'];
  const diagnostic = {
    role: 'Combustion Analyst',
    claim_index: 0,
    claim_classification: 'evidence_summary',
    reason_code: 'missing_source_reference',
    reason: 'source-backed claim has no record citations',
    evidence_references_supplied: false,
    evidence_ids_valid: false,
    citation_ids_supplied: false,
    citation_ids_valid: false,
    citation_investigation_match: null,
    provenance_restriction_rejected: false,
    historical_source_text_match: null,
  };
  partialResponse.specialist_analyses[0].evidence_validation_diagnostics = [diagnostic];
  partialResponse.evidence_validation_diagnostics = [diagnostic];
  globalThis.fetch = async () => ({ ok: true, json: async () => partialResponse });

  try {
    const response = await api.analyzeMission(parameters, question);
    assert.equal(response.evidence_validation_status, 'partial');
    assert.equal(response.specialist_analyses[0].evidence_validation_status, 'partial');
    assert.equal(response.specialist_analyses[0].evidence_validation_diagnostics[0].reason_code, 'missing_source_reference');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('mission client displays backend validation details as a useful error', async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: false,
    status: 422,
    json: async () => ({
      detail: [{
        loc: ['body', 'parameters', 'oxygen_percent'],
        msg: 'Input should be less than or equal to 40',
      }],
    }),
  });

  try {
    await assert.rejects(
      api.analyzeMission(parameters, question),
      /parameters\.oxygen_percent: Input should be less than or equal to 40/,
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('mission client rejects scenario metadata that changes a submitted value', async () => {
  const previousFetch = globalThis.fetch;
  const mismatchedResponse = mockMissionResponse();
  mismatchedResponse.scenario_parameters.pressure_atm = 0.55;
  globalThis.fetch = async () => ({ ok: true, json: async () => mismatchedResponse });

  try {
    await assert.rejects(
      api.analyzeMission(parameters, question),
      /scenario-inconsistent response/,
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});
