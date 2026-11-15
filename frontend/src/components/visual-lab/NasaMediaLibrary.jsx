import React, { useEffect, useState } from 'react';
import { ExternalLink, Image, Play, RefreshCw } from 'lucide-react';
import { NASA_MEDIA_TOPICS, resolveNasaVideoPlayback, searchNasaMedia } from '../../services/nasaMedia';

export function NasaImageCard({ item, topicLabel }) {
  return (
    <article className="overflow-hidden rounded-xl border border-space-border bg-space-panel">
      {item.previewUrl ? (
        <a href={item.sourceUrl} target="_blank" rel="noreferrer" aria-label={`Open original NASA source for ${item.title}`}>
          <img src={item.previewUrl} alt={item.title} loading="lazy" className="h-44 w-full bg-slate-950 object-cover" />
        </a>
      ) : (
        <div className="flex h-44 items-center justify-center bg-slate-950 text-slate-600"><Image size={28} /></div>
      )}
      <div className="space-y-2 p-3">
        <p className="text-[9px] font-mono uppercase tracking-wider text-cyan-300">NASA media search · {topicLabel}</p>
        <h4 className="text-xs font-semibold leading-relaxed text-white">{item.title}</h4>
        <p className="line-clamp-3 text-[10px] leading-relaxed text-slate-400">{item.description}</p>
        <p className="text-[10px] text-slate-500">Attribution: {item.attribution}{item.center ? ` · NASA ${item.center}` : ''}</p>
        <p className="break-all text-[9px] text-slate-600">NASA ID: {item.nasaId}</p>
        <a href={item.sourceUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[10px] text-cyan-300 hover:underline">
          Original NASA source record <ExternalLink size={11} />
        </a>
      </div>
    </article>
  );
}

export function NasaVideoCard({ item, topicLabel }) {
  const [loading, setLoading] = useState(false);
  const [videoUrl, setVideoUrl] = useState('');
  const [error, setError] = useState('');

  const loadVideo = async () => {
    setLoading(true);
    setError('');
    try {
      const source = await resolveNasaVideoPlayback(item.nasaId);
      setVideoUrl(source);
    } catch (videoError) {
      setError(videoError.message || 'NASA playback is unavailable; use the source record link.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <article className="rounded-xl border border-space-border bg-space-panel p-3">
      {videoUrl ? (
        <video controls preload="none" src={videoUrl} poster={item.previewUrl || undefined} className="mb-3 max-h-64 w-full rounded-lg bg-black">
          Your browser cannot play this NASA-hosted video. Open the original NASA source record.
        </video>
      ) : item.previewUrl ? (
        <a href={item.sourceUrl} target="_blank" rel="noreferrer" aria-label={`Open original NASA video source for ${item.title}`}>
          <img src={item.previewUrl} alt={item.title} loading="lazy" className="mb-3 h-36 w-full rounded-lg bg-black object-cover" />
        </a>
      ) : (
        <div className="mb-3 flex h-36 items-center justify-center rounded-lg bg-black text-slate-500"><Play size={28} /></div>
      )}
      <p className="text-[9px] font-mono uppercase tracking-wider text-cyan-300">NASA video library · {topicLabel}</p>
      <h4 className="mt-1 text-xs font-semibold text-white">{item.title}</h4>
      <p className="mt-2 line-clamp-3 text-[10px] leading-relaxed text-slate-400">{item.description}</p>
      <p className="mt-2 text-[10px] text-slate-500">Attribution: {item.attribution}{item.center ? ` · NASA ${item.center}` : ''}</p>
      <p className="mt-1 break-all text-[9px] text-slate-600">NASA ID: {item.nasaId}</p>
      {error && <p role="alert" className="mt-2 text-[10px] text-amber-300">{error}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {!videoUrl && <button type="button" onClick={loadVideo} disabled={loading} className="inline-flex items-center gap-1 rounded-md border border-cyan-800 px-2 py-1.5 text-[10px] text-cyan-200 hover:bg-cyan-950/50 disabled:opacity-50">
          {loading ? <><RefreshCw size={11} className="animate-spin" /> Loading NASA video…</> : <><Play size={11} /> Load NASA-hosted player</>}
        </button>}
        <a href={item.sourceUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[10px] text-cyan-300 hover:underline">
          Original NASA video source <ExternalLink size={11} />
        </a>
      </div>
    </article>
  );
}

function MediaFeedback({ loading, error, items, kind, onRetry }) {
  if (loading) return <p role="status" className="rounded-lg border border-cyan-900/60 p-4 text-xs text-cyan-200">Searching NASA’s media catalog for {kind}…</p>;
  if (error) return <div role="alert" className="rounded-lg border border-amber-900/60 p-4 text-xs text-amber-200"><p>{error}</p><button type="button" onClick={onRetry} className="mt-2 underline">Retry NASA search</button></div>;
  if (!items.length) return <p className="rounded-lg border border-slate-800 p-4 text-xs text-slate-400">No {kind} results were returned by the NASA media search. No sample media is substituted.</p>;
  return null;
}

export default function NasaMediaLibrary() {
  const [topicId, setTopicId] = useState(NASA_MEDIA_TOPICS[0].id);
  const [imageResult, setImageResult] = useState(null);
  const [videoResult, setVideoResult] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
  const topic = NASA_MEDIA_TOPICS.find((item) => item.id === topicId) || NASA_MEDIA_TOPICS[0];
  const requestKey = `${topic.id}:${retryKey}`;
  const imageState = imageResult?.key === requestKey ? imageResult : null;
  const videoState = videoResult?.key === requestKey ? videoResult : null;
  const images = imageState?.items || [];
  const videos = videoState?.items || [];
  const imageLoading = !imageState;
  const videoLoading = !videoState;
  const imageError = imageState?.error || '';
  const videoError = videoState?.error || '';

  useEffect(() => {
    const controller = new AbortController();
    searchNasaMedia(topic.query, 'image', { signal: controller.signal }).then((items) => {
      setImageResult({ key: requestKey, items, error: '' });
    }).catch((error) => {
      if (error.name !== 'AbortError') setImageResult({ key: requestKey, items: [], error: 'NASA image search is temporarily unavailable.' });
    });
    searchNasaMedia(topic.query, 'video', { signal: controller.signal }).then((items) => {
      setVideoResult({ key: requestKey, items, error: '' });
    }).catch((error) => {
      if (error.name !== 'AbortError') setVideoResult({ key: requestKey, items: [], error: 'NASA video search is temporarily unavailable.' });
    });
    return () => controller.abort();
  }, [topic, requestKey]);

  const retrySearch = () => setRetryKey((value) => value + 1);
  const topicCards = (
    <div className="flex flex-wrap gap-2" role="group" aria-label="NASA media topic filters">
      {NASA_MEDIA_TOPICS.map((item) => <button
        type="button"
        key={item.id}
        onClick={() => setTopicId(item.id)}
        aria-pressed={topic.id === item.id}
        className={`rounded-lg border px-3 py-2 text-[10px] font-medium transition-colors ${topic.id === item.id ? 'border-cyan-500/70 bg-cyan-950/40 text-cyan-200' : 'border-space-border bg-space-panel text-slate-400 hover:text-slate-200'}`}
      >{item.label}</button>)}
    </div>
  );

  return (
    <section className="space-y-4" aria-label="NASA research media library">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-bold text-white">NASA research photo gallery and video library</h2>
          <a href="https://images.nasa.gov/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[10px] text-cyan-300 hover:underline">NASA Image and Video Library <ExternalLink size={11} /></a>
        </div>
        <p className="mt-1 text-[10px] leading-relaxed text-slate-400">Live records are retrieved from NASA’s public media API. Titles, descriptions, creator attribution, IDs, and source links come from each returned catalog record. Search topic does not certify that a media item shows a specific experiment.</p>
      </div>
      {topicCards}

      <div className="space-y-3">
        <div className="flex items-center justify-between"><h3 className="text-xs font-semibold text-cyan-100">NASA photographs</h3><span className="text-[9px] text-slate-500">Source-linked catalog images</span></div>
        <MediaFeedback loading={imageLoading} error={imageError} items={images} kind="images" onRetry={retrySearch} />
        {!imageLoading && !imageError && images.length > 0 && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{images.map((item) => <NasaImageCard key={item.nasaId} item={item} topicLabel={topic.label} />)}</div>}
      </div>

      <div className="space-y-3 border-t border-space-border pt-4">
        <div className="flex items-center justify-between"><h3 className="text-xs font-semibold text-cyan-100">NASA educational and research videos</h3><span className="text-[9px] text-slate-500">Playback loads only after selection</span></div>
        <MediaFeedback loading={videoLoading} error={videoError} items={videos} kind="videos" onRetry={retrySearch} />
        {!videoLoading && !videoError && videos.length > 0 && <div className="grid gap-3 lg:grid-cols-2">{videos.map((item) => <NasaVideoCard key={item.nasaId} item={item} topicLabel={topic.label} />)}</div>}
      </div>
    </section>
  );
}
