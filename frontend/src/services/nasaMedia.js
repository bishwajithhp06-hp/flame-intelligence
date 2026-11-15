export const NASA_MEDIA_SEARCH = 'https://images-api.nasa.gov/search';
export const NASA_MEDIA_ASSET = 'https://images-api.nasa.gov/asset';
export const NASA_MEDIA_TOPICS = [
  { id: 'saffire', label: 'Saffire experiments', query: 'Saffire spacecraft fire experiment' },
  { id: 'flex', label: 'FLEX combustion research', query: 'FLEX microgravity combustion' },
  { id: 'microgravity', label: 'Microgravity combustion', query: 'microgravity combustion flame' },
  { id: 'spacecraft', label: 'Spacecraft fire safety', query: 'spacecraft fire safety combustion' },
];

function isNasaHttpsUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && (url.hostname === 'nasa.gov' || url.hostname.endsWith('.nasa.gov'));
  } catch {
    return false;
  }
}

function secureNasaAssetUrl(value) {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || !(url.hostname === 'nasa.gov' || url.hostname.endsWith('.nasa.gov'))) return null;
    url.protocol = 'https:';
    return url.toString();
  } catch {
    return null;
  }
}

export function normalizeNasaMediaItem(item, expectedType) {
  const metadata = item?.data?.[0];
  const preview = item?.links?.find((link) => link.rel === 'preview')?.href;
  const sourceUrl = item?.href;
  if (!metadata?.nasa_id || metadata.media_type !== expectedType || !isNasaHttpsUrl(sourceUrl)) return null;

  return {
    nasaId: metadata.nasa_id,
    title: metadata.title || 'Untitled NASA media item',
    description: metadata.description || 'No description was supplied in the NASA media record.',
    mediaType: metadata.media_type,
    dateCreated: metadata.date_created || null,
    center: metadata.center || null,
    attribution: metadata.photographer || metadata.secondary_creator || metadata.center || 'Creator not listed in NASA metadata',
    previewUrl: isNasaHttpsUrl(preview) ? preview : null,
    sourceUrl,
  };
}

export async function searchNasaMedia(query, mediaType, { fetchImpl = globalThis.fetch, signal } = {}) {
  if (!['image', 'video'].includes(mediaType)) throw new TypeError('NASA media search supports image or video records.');
  const url = new URL(NASA_MEDIA_SEARCH);
  url.searchParams.set('q', query);
  url.searchParams.set('media_type', mediaType);
  url.searchParams.set('page_size', '12');

  const response = await fetchImpl(url, { signal, headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`NASA media search returned HTTP ${response.status}.`);
  const payload = await response.json();
  return (payload?.collection?.items || [])
    .map((item) => normalizeNasaMediaItem(item, mediaType))
    .filter((item) => item && (mediaType !== 'image' || item.previewUrl));
}

export async function resolveNasaVideoPlayback(nasaId, { fetchImpl = globalThis.fetch, signal } = {}) {
  const hasPathSeparator = typeof nasaId === 'string' && /[\\/]/.test(nasaId);
  const hasControlCharacter = typeof nasaId === 'string' && [...nasaId].some((character) => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127);
  if (typeof nasaId !== 'string' || !nasaId.trim() || nasaId.length > 200 || hasPathSeparator || hasControlCharacter) {
    throw new TypeError('A valid NASA media identifier is required.');
  }
  const response = await fetchImpl(`${NASA_MEDIA_ASSET}/${encodeURIComponent(nasaId)}`, {
    signal,
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error(`NASA video assets returned HTTP ${response.status}.`);
  const payload = await response.json();
  const videoUrls = (payload?.collection?.items || [])
    .map((asset) => secureNasaAssetUrl(asset.href))
    .filter((href) => href && /\.mp4(?:\?|$)/i.test(href));
  const preferred = videoUrls.find((href) => /~small\.mp4(?:\?|$)/i.test(href))
    || videoUrls.find((href) => /~medium\.mp4(?:\?|$)/i.test(href))
    || videoUrls.find((href) => !/~orig\.mp4(?:\?|$)/i.test(href))
    || videoUrls[0];
  if (!preferred) throw new Error('No NASA-hosted MP4 playback file is listed for this video. Open the source record instead.');
  return preferred;
}
