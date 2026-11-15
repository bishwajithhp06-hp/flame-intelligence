export const VISUAL_MODES = [
  { id: 'chamber', label: 'Chamber cutaway', type: 'Illustrative simulation' },
  { id: 'microgravity', label: 'Microgravity flame', type: 'Illustrative simulation' },
  { id: 'spherical', label: 'Spherical flame', type: 'Illustrative simulation' },
  { id: 'propagation', label: 'Flame propagation', type: 'Illustrative simulation' },
  { id: 'airflow', label: 'Airflow particles', type: 'Illustrative simulation' },
];

export const DEFAULT_VISUAL_SCENARIO = {
  environment: 'Lunar Habitat',
  oxygen_percent: 30,
  pressure_atm: 0.8,
  airflow_cm_s: 15,
  gravity: 'lunar',
  material: 'pmma',
};

const MATERIAL_SWATCHES = {
  'n-heptane': '#fb923c',
  pmma: '#fbbf24',
  'cotton-fabric': '#e2e8f0',
  'gas-jet': '#38bdf8',
  nomex: '#f97316',
};

const GRAVITY_ACCENTS = {
  microgravity: '#a78bfa',
  lunar: '#38bdf8',
  mars: '#fb923c',
  earth: '#34d399',
};

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || min));
}

/**
 * Maps user controls to purely illustrative display accents. This deliberately
 * does not calculate flame behavior, heat, speed, risk, or a safety result.
 */
export function getIllustrativeSettings(scenario) {
  const oxygen = clamp(scenario?.oxygen_percent, 10, 40);
  const pressure = clamp(scenario?.pressure_atm, 0.2, 1.5);
  const airflow = clamp(scenario?.airflow_cm_s, 0, 50);
  const gravity = scenario?.gravity || 'earth';
  const material = scenario?.material || 'pmma';

  return {
    accent: GRAVITY_ACCENTS[gravity] || GRAVITY_ACCENTS.earth,
    materialSwatch: MATERIAL_SWATCHES[material] || MATERIAL_SWATCHES.pmma,
    // These values only vary the visual appearance and particle animation.
    glowOpacity: 0.4 + ((oxygen - 10) / 30) * 0.4,
    chamberOpacity: 0.08 + ((pressure - 0.2) / 1.3) * 0.1,
    particleMotion: 0.15 + (airflow / 50) * 0.85,
    particleCount: Math.round(8 + (airflow / 50) * 16),
  };
}
