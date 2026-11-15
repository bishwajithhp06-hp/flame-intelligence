// API Service for FLAME INTELLIGENCE backend
const API_BASE = '/api';
const MISSION_SPECIALIST_ROLES = [
  'Combustion Analyst',
  'Atmosphere Analyst',
  'Material Safety Analyst',
  'Fire Suppression Analyst',
  'Mission Safety Synthesizer'
];

function formatApiError(detail, fallback) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const location = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : '';
      return `${location ? `${location}: ` : ''}${item.msg || 'Invalid input'}`;
    }).join('; ');
  }
  return fallback;
}

function isEvidenceValidationDiagnostic(item) {
  const isOptionalBoolean = (value) => value === null || typeof value === 'boolean';
  return item && typeof item === 'object'
    && MISSION_SPECIALIST_ROLES.includes(item.role)
    && Number.isInteger(item.claim_index) && item.claim_index >= 0
    && typeof item.claim_classification === 'string'
    && typeof item.reason_code === 'string'
    && typeof item.reason === 'string'
    && typeof item.evidence_references_supplied === 'boolean'
    && isOptionalBoolean(item.evidence_ids_valid)
    && typeof item.citation_ids_supplied === 'boolean'
    && isOptionalBoolean(item.citation_ids_valid)
    && isOptionalBoolean(item.citation_investigation_match)
    && typeof item.provenance_restriction_rejected === 'boolean'
    && isOptionalBoolean(item.historical_source_text_match);
}

function isMissionAnalysisResponse(body, expectedParameters) {
  if (!body || typeof body !== 'object') return false;
  const returnedParameters = body.scenario_parameters;
  const parametersMatch = returnedParameters && expectedParameters
    && Object.entries(expectedParameters).every(([key, value]) => Object.is(returnedParameters[key], value));
  const roles = Array.isArray(body.specialist_analyses)
    ? body.specialist_analyses.map((item) => item?.role)
    : [];
  const researchGaps = body.research_gaps;
  const synthesisDetails = body.synthesis_details;
  return typeof body.environment === 'string'
    && body.environment === expectedParameters?.environment
    && parametersMatch
    && roles.length === MISSION_SPECIALIST_ROLES.length
    && new Set(roles).size === MISSION_SPECIALIST_ROLES.length
    && MISSION_SPECIALIST_ROLES.every((role) => roles.includes(role))
    && body.specialist_analyses.every((item) => typeof item.analysis === 'string'
      && typeof item.evidence_status === 'string'
      && ['validated', 'partial', 'no_valid_claims'].includes(item.evidence_validation_status)
      && Array.isArray(item.evidence_validation_issues)
      && Array.isArray(item.evidence_validation_diagnostics)
      && item.evidence_validation_diagnostics.every(isEvidenceValidationDiagnostic)
      && Array.isArray(item.relevant_evidence)
      && Array.isArray(item.assumptions)
      && Array.isArray(item.uncertainties)
      && Array.isArray(item.citations))
    && typeof body.mission_synthesis === 'string'
    && Array.isArray(body.citations)
    && Array.isArray(body.evidence_matches)
    && researchGaps && Array.isArray(researchGaps.supported_parameters)
    && Array.isArray(researchGaps.partially_supported_parameters)
    && Array.isArray(researchGaps.unsupported_parameters)
    && Array.isArray(researchGaps.important_assumptions)
    && researchGaps.combined_scenario_status === 'not_documented'
    && typeof researchGaps.combined_scenario_explanation === 'string'
    && synthesisDetails && typeof synthesisDetails.combined_assessment === 'string'
    && typeof synthesisDetails.conflict_assessment === 'string'
    && Array.isArray(synthesisDetails.main_documented_findings)
    && Array.isArray(synthesisDetails.important_uncertainties)
    && Array.isArray(synthesisDetails.research_gaps)
    && Array.isArray(synthesisDetails.conflicting_claims)
    && Array.isArray(synthesisDetails.supporting_citations)
    && typeof body.evidence_status === 'string'
    && ['complete', 'partial'].includes(body.evidence_validation_status)
    && Array.isArray(body.evidence_validation_issues)
    && Array.isArray(body.evidence_validation_diagnostics)
    && body.evidence_validation_diagnostics.every(isEvidenceValidationDiagnostic)
    && typeof body.disclaimer === 'string';
}

export const api = {
  async analyzeMission(parameters, question = null) {
    const requestBody = { parameters, question };
    const res = await fetch(`${API_BASE}/mission/analyze`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(formatApiError(body.detail, `Mission analysis failed (HTTP ${res.status}).`));
    }
    if (!isMissionAnalysisResponse(body, parameters)) {
      throw new Error('Mission analysis returned an incomplete or scenario-inconsistent response. Please retry.');
    }
    return body;
  },

  async getStoredExperiments(filters = {}) {
    const params = new URLSearchParams();
    for (const key of ['search', 'source', 'material', 'gravity', 'environment']) {
      if (filters[key]) params.set(key, filters[key]);
    }
    const suffix = params.size ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/experiments${suffix}`);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(formatApiError(body.detail, `NASA experiment search failed (HTTP ${res.status}).`));
    }
    if (!body || !Array.isArray(body.records) || !body.available_filters || typeof body.conditions_notice !== 'string') {
      throw new Error('NASA experiment search returned an incomplete response.');
    }
    return body;
  },

  async getStoredExperiment(recordId) {
    const res = await fetch(`${API_BASE}/experiments/${encodeURIComponent(recordId)}`);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(formatApiError(body.detail, `NASA record detail failed (HTTP ${res.status}).`));
    }
    return body;
  },

  async compareStoredExperiments(recordIds) {
    const res = await fetch(`${API_BASE}/experiments/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ record_ids: recordIds }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(formatApiError(body.detail, `NASA record comparison failed (HTTP ${res.status}).`));
    }
    return body;
  },

  async createMissionReport(analysis, reportName = null) {
    const reportQuery = reportName ? `?report_name=${encodeURIComponent(reportName)}` : '';
    const res = await fetch(`${API_BASE}/reports/mission${reportQuery}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(analysis),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(formatApiError(body.detail, `Mission report generation failed (HTTP ${res.status}).`));
    }
    return res.blob();
  },

  async createExperimentComparisonReport(recordIds) {
    const res = await fetch(`${API_BASE}/reports/experiments/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ record_ids: recordIds }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(formatApiError(body.detail, `Experiment report generation failed (HTTP ${res.status}).`));
    }
    return res.blob();
  },

  // Dashboard endpoints
  async getDashboardStats() {
    try {
      const res = await fetch(`${API_BASE}/dashboard/stats`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn("Using offline fallback for dashboard stats", err);
      return {
        total_investigations: 5,
        total_publications: 7,
        total_findings: 7,
        total_datapoints: 12,
        categories_count: 5,
        data_authenticity_notice: "Offline fallback counts; local datapoint and provenance records have not been independently verified."
      };
    }
  },

  async getCategories() {
    try {
      const res = await fetch(`${API_BASE}/dashboard/categories`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return [
        { category: "Droplet Combustion & Cool Flames", count: 1, percentage: 20 },
        { category: "Large-Scale Material Flammability", count: 1, percentage: 20 },
        { category: "Soot Formation & Radiation", count: 1, percentage: 20 },
        { category: "Solid Fuel Extinguishment Limits", count: 1, percentage: 20 },
        { category: "Gaseous Flame Dynamics", count: 1, percentage: 20 }
      ];
    }
  },

  async getTimeline() {
    try {
      const res = await fetch(`${API_BASE}/dashboard/timeline`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return [];
    }
  },

  async getRecentInvestigations() {
    try {
      const res = await fetch(`${API_BASE}/dashboard/recent`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return [];
    }
  },

  // Investigations endpoints
  async getInvestigations(category = '', search = '') {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (search) params.append('search', search);

    try {
      const res = await fetch(`${API_BASE}/investigations?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn("Failed to fetch investigations", err);
      return [];
    }
  },

  async getInvestigationDetail(id) {
    try {
      const res = await fetch(`${API_BASE}/investigations/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn(`Failed to fetch investigation ${id}`, err);
      return null;
    }
  },

  // Analytics endpoints
  async getDatapoints(flightOnly = true) {
    try {
      const res = await fetch(`${API_BASE}/analytics/datapoints?flight_only=${flightOnly}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return [];
    }
  },

  async getComparisonMatrix() {
    try {
      const res = await fetch(`${API_BASE}/analytics/comparison`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return [];
    }
  },

  async getFireSafetyInsights() {
    try {
      const res = await fetch(`${API_BASE}/analytics/insights`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return [];
    }
  },

  // AI Assistant endpoint
  async queryAi(question, investigationFilter = null) {
    try {
      const res = await fetch(`${API_BASE}/ai/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          investigation_filter: investigationFilter
        })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error("AI Assistant request failed:", err);
      return {
        answer: "Unable to connect to the backend AI service. Please verify that the FastAPI backend is running at http://localhost:8000.",
        citations: [],
        investigations_referenced: [],
        has_sufficient_evidence: false,
        notice: "Connection error."
      };
    }
  },

  // Sources endpoints
  async getSources() {
    try {
      const res = await fetch(`${API_BASE}/sources`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return [];
    }
  },

  async verifySources() {
    try {
      const res = await fetch(`${API_BASE}/sources/check`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return {
        status_checks: [
          { provider: "NASA PSI", status_code: null, is_accessible: false, details: "Backend unreachable" },
          { provider: "NASA NTRS", status_code: null, is_accessible: false, details: "Backend unreachable" }
        ],
        message: "Check failed: Backend connection error"
      };
    }
  },

  // Global search
  async search(query) {
    if (!query || query.length < 2) return { investigations: [], publications: [], findings: [] };
    try {
      const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return { investigations: [], publications: [], findings: [] };
    }
  }
};
