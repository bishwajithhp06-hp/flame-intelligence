import { api } from './api';

const REQUIRED_MISSION_SPECIALISTS = [
  'Combustion Analyst',
  'Atmosphere Analyst',
  'Material Safety Analyst',
  'Fire Suppression Analyst',
  'Mission Safety Synthesizer',
];

export function triggerPdfDownload(pdf, filename, browser = {}) {
  if (!pdf || pdf.type !== 'application/pdf') {
    throw new Error('The report service returned an invalid PDF file.');
  }

  const documentRef = browser.documentRef ?? globalThis.document;
  const urlApi = browser.urlApi ?? globalThis.URL;
  const schedule = browser.setTimeoutFn ?? globalThis.setTimeout;
  if (!documentRef?.createElement || !documentRef?.body || !urlApi?.createObjectURL) {
    throw new Error('This browser cannot download the report.');
  }

  const objectUrl = urlApi.createObjectURL(pdf);
  const link = documentRef.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  link.style.display = 'none';

  try {
    documentRef.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    schedule(() => urlApi.revokeObjectURL(objectUrl), 1000);
  }
}

export function reportFilename(value, suffix = 'report') {
  const safeValue = String(value || 'flame')
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/[\s_-]+/g, '-')
    .toLowerCase() || 'flame';
  return `flame-${safeValue}-${suffix}.pdf`;
}

export function isCompleteMissionAnalysis(analysis) {
  if (!analysis || typeof analysis.environment !== 'string' || !analysis.scenario_parameters) return false;
  if (analysis.evidence_validation_status && analysis.evidence_validation_status !== 'complete') return false;
  const parameters = analysis.scenario_parameters;
  if (parameters.environment !== analysis.environment
    || !Number.isFinite(parameters.oxygen_percent)
    || !Number.isFinite(parameters.pressure_atm)
    || !Number.isFinite(parameters.airflow_cm_s)
    || typeof parameters.gravity !== 'string'
    || typeof parameters.material !== 'string') return false;
  if (typeof analysis.mission_synthesis !== 'string' || !analysis.mission_synthesis.trim()) return false;
  if (!analysis.synthesis_details || !analysis.research_gaps || typeof analysis.evidence_status !== 'string') return false;
  if (typeof analysis.disclaimer !== 'string' || !Array.isArray(analysis.citations) || !Array.isArray(analysis.evidence_matches)) return false;
  if (!Array.isArray(analysis.specialist_analyses) || analysis.specialist_analyses.length !== REQUIRED_MISSION_SPECIALISTS.length) return false;
  const roles = analysis.specialist_analyses.map((item) => item?.role);
  return REQUIRED_MISSION_SPECIALISTS.every((role) => roles.includes(role))
    && analysis.specialist_analyses.every((item) => typeof item.analysis === 'string' && item.analysis.trim()
      && (!item.evidence_validation_status || item.evidence_validation_status === 'validated'));
}

export async function downloadMissionAnalysisReport(analysis, browser = {}) {
  if (!isCompleteMissionAnalysis(analysis)) {
    throw new Error('A complete Mission Intelligence result is required before downloading its report.');
  }
  const reportName = `${analysis.environment} Mission Intelligence Report`;
  const pdf = await api.createMissionReport(analysis, reportName);
  triggerPdfDownload(pdf, reportFilename(analysis.environment, 'mission-experiment-report'), browser);
}

export function isCompleteExperimentComparison(comparison) {
  return Number.isInteger(comparison?.left?.record_id)
    && Number.isInteger(comparison?.right?.record_id)
    && comparison.left.record_id !== comparison.right.record_id
    && typeof comparison.left.title === 'string'
    && typeof comparison.right.title === 'string'
    && Array.isArray(comparison.categorical_comparisons)
    && Array.isArray(comparison.quantitative_comparisons)
    && Array.isArray(comparison.limitations);
}

export async function downloadExperimentComparisonReport(comparison, browser = {}) {
  if (!isCompleteExperimentComparison(comparison)) {
    throw new Error('A complete comparison of two stored records is required before downloading its report.');
  }
  const pdf = await api.createExperimentComparisonReport([comparison.left.record_id, comparison.right.record_id]);
  triggerPdfDownload(
    pdf,
    reportFilename(`${comparison.left.title}-vs-${comparison.right.title}`, 'experiment-comparison-report'),
    browser,
  );
}
