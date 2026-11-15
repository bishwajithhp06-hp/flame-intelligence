import React, { useState } from 'react';
import { Bot, Send, Sparkles, BookOpen, ExternalLink, ShieldAlert, AlertCircle, CheckCircle2 } from 'lucide-react';
import { api } from '../../services/api';

export default function AiAssistantView() {
  const [question, setQuestion] = useState('');
  const [investigationFilter, setInvestigationFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Welcome to **FLAME INTELLIGENCE AI Research Assistant**. I use the local microgravity combustion research records available to this project. Local provenance may be unverified; I will identify evidence gaps and only return citations retrieved from the records.",
      citations: []
    }
  ]);

  const promptSuggestions = [
    { label: "Cool Flames in FLEX", text: "Explain the cool flame discovery in FLEX and why it poses an invisible fire hazard for spacecraft." },
    { label: "Saffire Ventilation Spread", text: "How does cabin ventilation airflow velocity affect flame spread rates on large fabrics in the Saffire experiments?" },
    { label: "SPICE Soot & Smoke Limits", text: "Why do gas diffusion flames in SPICE produce soot and reach smoke points at lower fuel flow rates than on Earth?" },
    { label: "BASS Solid Extinction", text: "What is the critical low-flow velocity 'sweet spot' in BASS where solid fuels are hardest to extinguish?" },
    { label: "ACME Electric Field Control", text: "How can electric fields extinguish or deflect microgravity diffusion flames in the ACME project?" }
  ];

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!question.trim() || loading) return;

    const userQ = question;
    setQuestion('');
    setMessages((prev) => [...prev, { role: 'user', content: userQ }]);
    setLoading(true);

    try {
      const res = await api.queryAi(userQ, investigationFilter || null);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          citations: res.citations || [],
          investigations: res.investigations_referenced || [],
          notice: res.notice
        }
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: "An error occurred while querying the research assistant. Please ensure the backend server is running.",
          citations: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestionClick = (text) => {
    setQuestion(text);
  };

  return (
    <div className="space-y-6">
      {/* Scientific Integrity Assurance Header */}
      <div className="p-4 rounded-xl bg-space-panel border border-space-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-cyan-950 border border-cyan-800 text-cyan-400">
            <Bot size={18} />
          </div>
          <div>
            <h2 className="font-bold text-white text-sm">NASA Grounded RAG Research Assistant</h2>
            <p className="text-slate-400">
              Responses use available local research records; datapoint provenance is not independently verified.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400">Filter Context:</span>
          <select
            value={investigationFilter}
            onChange={(e) => setInvestigationFilter(e.target.value)}
            className="bg-space-panel border border-space-border rounded-md px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="">All Investigations</option>
            <option value="FLEX">FLEX Only</option>
            <option value="SAFFIRE">SAFFIRE Only</option>
            <option value="SPICE">SPICE Only</option>
            <option value="BASS">BASS Only</option>
            <option value="ACME">ACME Only</option>
          </select>
        </div>
      </div>

      {/* Suggested Prompts */}
      <div className="space-y-2">
        <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 font-semibold block">
          Key Research Inquiries
        </span>
        <div className="flex flex-wrap gap-2">
          {promptSuggestions.map((s, idx) => (
            <button
              key={idx}
              onClick={() => handleSuggestionClick(s.text)}
              className="px-3 py-1.5 rounded-lg bg-space-panel border border-space-border hover:border-cyan-500/50 hover:bg-space-panel-raised text-xs text-slate-300 transition-colors cursor-pointer text-left"
            >
              <Sparkles size={11} className="inline mr-1.5 text-cyan-400" />
              <span>{s.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Chat Messages Log */}
      <div className="rounded-2xl bg-space-panel border border-space-border p-4 lg:p-6 min-h-[420px] max-h-[600px] overflow-y-auto space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div
              className={`max-w-3xl rounded-xl p-4 text-xs leading-relaxed space-y-3 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-space-panel border border-space-border text-slate-200 rounded-bl-none'
              }`}
            >
              {/* Message Header */}
              <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400 pb-1 border-b border-slate-700/40">
                {msg.role === 'user' ? (
                  <span>RESEARCHER</span>
                ) : (
                  <span className="text-cyan-400 flex items-center gap-1">
                    <Bot size={12} /> FLAME INTELLIGENCE AI
                  </span>
                )}
              </div>

              {/* Render formatted message content */}
              <div className="space-y-2 whitespace-pre-wrap font-sans">
                {msg.content}
              </div>

              {/* Citations and References */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="pt-3 border-t border-slate-700/60 space-y-2">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 flex items-center gap-1">
                    <BookOpen size={12} />
                    <span>Supporting Grounded References ({msg.citations.length})</span>
                  </div>
                  <div className="grid grid-cols-1 gap-1.5">
                    {msg.citations.map((c, ci) => (
                      <div key={ci} className="p-2 rounded bg-space-panel border border-space-border text-[11px] flex items-center justify-between gap-2">
                        <div className="truncate">
                          <span className="font-semibold text-white">{c.title}</span>
                          <span className="text-slate-400 ml-1.5 font-mono text-[10px]">
                            {c.doi ? `DOI: ${c.doi}` : c.identifier}
                          </span>
                        </div>
                        {c.url && (
                          <a
                            href={c.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-cyan-400 hover:text-cyan-300 shrink-0"
                          >
                            <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Spacecraft Safety Notice */}
              {msg.notice && (
                <div className="text-[10px] text-slate-400 italic font-mono pt-1">
                  * {msg.notice}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-space-panel border border-space-border text-xs text-slate-400 max-w-sm">
            <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
            <span>Grounding research query in available local records...</span>
          </div>
        )}
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="relative">
        <textarea
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a scientific research question (e.g. 'How does oxygen concentration affect flame spread in Saffire?')..."
          className="w-full p-3.5 pr-28 text-xs bg-space-panel border border-space-border rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />

        <div className="absolute right-3 bottom-3 flex items-center gap-2">
          <button
            type="submit"
            disabled={!question.trim() || loading}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-space-primary hover:bg-space-primary-hover text-white text-xs font-semibold shadow-md disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            <span>Analyze</span>
            <Send size={12} />
          </button>
        </div>
      </form>
    </div>
  );
}
