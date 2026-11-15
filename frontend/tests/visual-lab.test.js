import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { after, before, test } from 'node:test';
import reactPlugin from '@vitejs/plugin-react';
import { createServer } from 'vite';
import { getIllustrativeSettings, VISUAL_MODES } from '../src/components/visual-lab/visualModel.js';
import { normalizeNasaMediaItem, resolveNasaVideoPlayback, searchNasaMedia } from '../src/services/nasaMedia.js';

let vite;
let VisualLabView;
let NasaImageCard;
let NasaVideoCard;
let StaticChamberFallback;
let Sidebar;

before(async () => {
  vite = await createServer({
    configFile: false,
    root: process.cwd(),
    plugins: [reactPlugin()],
    server: { middlewareMode: true },
    // Transform the ESM-only Three.js graph through Vite in the test SSR loader.
    // This keeps test behavior compatible with the project's supported Node
    // versions without changing the production browser bundle.
    ssr: { noExternal: ['@react-three/fiber', 'three'] },
    appType: 'custom',
    logLevel: 'silent',
  });
  ({ default: VisualLabView } = await vite.ssrLoadModule('/src/components/visual-lab/VisualLabView.jsx'));
  ({ NasaImageCard, NasaVideoCard } = await vite.ssrLoadModule('/src/components/visual-lab/NasaMediaLibrary.jsx'));
  ({ StaticChamberFallback } = await vite.ssrLoadModule('/src/components/visual-lab/MissionScene3D.jsx'));
  ({ default: Sidebar } = await vite.ssrLoadModule('/src/components/common/Sidebar.jsx'));
});

after(async () => {
  await vite?.close();
});

function mediaItem(mediaType = 'image', overrides = {}) {
  return {
    data: [{
      nasa_id: 'NASA-TEST-01',
      media_type: mediaType,
      title: 'NASA combustion research media',
      description: 'A NASA catalog description for a combustion research media item.',
      photographer: 'NASA / Test Center',
      center: 'GRC',
      ...overrides,
    }],
    href: `https://images-assets.nasa.gov/${mediaType}/NASA-TEST-01/collection.json`,
    links: [{ rel: 'preview', href: 'https://images-assets.nasa.gov/image/NASA-TEST-01/preview.jpg' }],
  };
}

test('scenario inputs update display accents without implying physical model output', () => {
  const base = { oxygen_percent: 30, pressure_atm: 0.8, airflow_cm_s: 15, gravity: 'lunar', material: 'pmma' };
  const settings = getIllustrativeSettings(base);
  assert.notEqual(settings.glowOpacity, getIllustrativeSettings({ ...base, oxygen_percent: 34 }).glowOpacity);
  assert.notEqual(settings.chamberOpacity, getIllustrativeSettings({ ...base, pressure_atm: 1.2 }).chamberOpacity);
  assert.notEqual(settings.particleMotion, getIllustrativeSettings({ ...base, airflow_cm_s: 30 }).particleMotion);
  assert.notEqual(settings.accent, getIllustrativeSettings({ ...base, gravity: 'microgravity' }).accent);
  assert.notEqual(settings.materialSwatch, getIllustrativeSettings({ ...base, material: 'nomex' }).materialSwatch);
  assert.equal(VISUAL_MODES.length, 5);
});

test('NASA media normalizer preserves returned source links and rejects unrelated sources', () => {
  const image = normalizeNasaMediaItem(mediaItem(), 'image');
  assert.equal(image.nasaId, 'NASA-TEST-01');
  assert.equal(image.title, 'NASA combustion research media');
  assert.equal(image.attribution, 'NASA / Test Center');
  assert.equal(image.sourceUrl, 'https://images-assets.nasa.gov/image/NASA-TEST-01/collection.json');
  assert.equal(image.previewUrl, 'https://images-assets.nasa.gov/image/NASA-TEST-01/preview.jpg');
  assert.equal(normalizeNasaMediaItem({ ...mediaItem(), href: 'https://example.invalid/not-nasa' }, 'image'), null);
  assert.equal(normalizeNasaMediaItem(mediaItem('video'), 'image'), null);
});

test('NASA media search requests source catalog and uses API metadata only', async () => {
  let requestedUrl;
  const items = await searchNasaMedia('Saffire spacecraft fire', 'image', {
    fetchImpl: async (url) => {
      requestedUrl = new URL(url);
      return new Response(JSON.stringify({ collection: { items: [mediaItem(), { data: [] }] } }), { status: 200 });
    },
  });
  assert.equal(requestedUrl.origin, 'https://images-api.nasa.gov');
  assert.equal(requestedUrl.searchParams.get('q'), 'Saffire spacecraft fire');
  assert.equal(requestedUrl.searchParams.get('media_type'), 'image');
  assert.equal(items.length, 1);
  assert.equal(items[0].nasaId, 'NASA-TEST-01');
});

test('NASA video playback selects a source MP4 and reports when playback is absent', async () => {
  const result = await resolveNasaVideoPlayback('NASA-TEST-01', {
    fetchImpl: async () => new Response(JSON.stringify({ collection: { items: [
      { href: 'https://images-assets.nasa.gov/video/NASA-TEST-01/~orig.mp4' },
      { href: 'http://images-assets.nasa.gov/video/NASA-TEST-01/~small.mp4' },
    ] } }), { status: 200 }),
  });
  assert.equal(result, 'https://images-assets.nasa.gov/video/NASA-TEST-01/~small.mp4');
  const realStyleId = 'Saf-VI S8C3+C4 1-sided PMMA';
  let assetRequestUrl;
  await resolveNasaVideoPlayback(realStyleId, {
    fetchImpl: async (url) => {
      assetRequestUrl = String(url);
      return new Response(JSON.stringify({ collection: { items: [{ href: 'https://images-assets.nasa.gov/video/test/clip.mp4' }] } }), { status: 200 });
    },
  });
  assert.ok(assetRequestUrl.includes('Saf-VI%20S8C3%2BC4%201-sided%20PMMA'));
  await assert.rejects(() => resolveNasaVideoPlayback('../not-an-id'), TypeError);
  await assert.rejects(() => resolveNasaVideoPlayback('NASA-TEST-02', {
    fetchImpl: async () => new Response(JSON.stringify({ collection: { items: [] } }), { status: 200 }),
  }), /No NASA-hosted MP4/);
});

test('Visual Lab renders 3D controls, scenario controls and explicit scientific limits', () => {
  const html = renderToStaticMarkup(React.createElement(VisualLabView));
  assert.ok(html.includes('Interactive Combustion Visual Lab'));
  assert.ok(html.includes('Chamber cutaway'));
  assert.ok(html.includes('Microgravity flame'));
  assert.ok(html.includes('Spherical flame'));
  assert.ok(html.includes('Flame propagation'));
  assert.ok(html.includes('Airflow particles'));
  assert.ok(html.includes('Zoom in'));
  assert.ok(html.includes('Reset camera view'));
  assert.ok(html.includes('Ambient pressure'));
  assert.ok(html.includes('Gravity scenario'));
  assert.ok(html.includes('not a validated physical model'));
  assert.ok(html.includes('NASA’s media catalog for images'));
});

test('NASA gallery cards show source and attribution; videos defer playback and retain external fallback', () => {
  const imageHtml = renderToStaticMarkup(React.createElement(NasaImageCard, { item: normalizeNasaMediaItem(mediaItem(), 'image'), topicLabel: 'FLEX' }));
  assert.ok(imageHtml.includes('NASA combustion research media'));
  assert.ok(imageHtml.includes('Attribution: NASA / Test Center'));
  assert.ok(imageHtml.includes('Original NASA source record'));
  assert.ok(imageHtml.includes('loading="lazy"'));

  const videoHtml = renderToStaticMarkup(React.createElement(NasaVideoCard, { item: normalizeNasaMediaItem(mediaItem('video'), 'video'), topicLabel: 'Saffire' }));
  assert.ok(videoHtml.includes('Load NASA-hosted player'));
  assert.ok(videoHtml.includes('Original NASA video source'));
  assert.ok(!videoHtml.includes('<video'));
});

test('3D scene has a WebGL fallback and dashboard keeps the Visual Lab navigation alongside existing modules', async () => {
  const fallback = renderToStaticMarkup(React.createElement(StaticChamberFallback));
  const nav = renderToStaticMarkup(React.createElement(Sidebar, { activeTab: 'visual-lab', setActiveTab: () => {}, mobileMenuOpen: false, setMobileMenuOpen: () => {} }));
  const appSource = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
  assert.ok(fallback.includes('WebGL is unavailable'));
  assert.ok(nav.includes('Visual Lab &amp; NASA Media'));
  for (const existingModule of ['Dashboard', 'NASA Research Explorer', 'AI Research Assistant', 'Mission Intelligence', 'Combustion Analytics', 'Experiment Comparison', 'Fire Safety Insights', 'NASA Sources &amp; Collector']) {
    assert.ok(nav.includes(existingModule), `existing navigation module missing: ${existingModule}`);
  }
  assert.ok(appSource.includes("activeTab === 'visual-lab'"));
  assert.ok(appSource.includes('lazy(() => import'));
});
