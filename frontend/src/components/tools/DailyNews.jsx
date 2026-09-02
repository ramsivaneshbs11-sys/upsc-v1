import React, { useState, useEffect, useCallback } from 'react';
import { useApp } from '../../context/AppContext';
import { Calendar, ChevronRight, Search, BookOpen, Globe, TrendingUp, Cpu, Leaf, Shield, Landmark, ExternalLink, X, Plus, Check, Star, Zap, Filter, RefreshCw, AlertCircle, Copy } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = '/api/v1';

const CATEGORIES = [
  { key: 'all', label: 'All Topics', icon: null },
  { key: 'Polity', label: 'Polity', icon: <Landmark size={14} />, color: 'orange' },
  { key: 'Economy', label: 'Economy', icon: <TrendingUp size={14} />, color: 'green' },
  { key: 'International', label: 'International', icon: <Globe size={14} />, color: 'blue' },
  { key: 'Science', label: 'Science & Tech', icon: <Cpu size={14} />, color: 'purple' },
  { key: 'Environment', label: 'Environment', icon: <Leaf size={14} />, color: 'emerald' },
  { key: 'Defense', label: 'Defense', icon: <Shield size={14} />, color: 'red' },
  { key: 'Schemes', label: 'Schemes', icon: <BookOpen size={14} />, color: 'indigo' },
];

const CAT_ICONS = {
  polity_governance: <Landmark size={18} className="text-orange-500" />,
  international_relations: <Globe size={18} className="text-blue-500" />,
  economy: <TrendingUp size={18} className="text-green-500" />,
  science_technology: <Cpu size={18} className="text-purple-500" />,
  environment_ecology: <Leaf size={18} className="text-emerald-500" />,
  defense_security: <Shield size={18} className="text-red-500" />,
  government_schemes: <BookOpen size={18} className="text-indigo-500" />,
};

const CAT_LABELS = {
  polity_governance: 'Polity & Governance',
  international_relations: 'International Relations',
  economy: 'Economy',
  science_technology: 'Science & Technology',
  environment_ecology: 'Environment & Ecology',
  defense_security: 'Defense & Security',
  government_schemes: 'Govt. Schemes & Policies',
};

const TAG_STYLE = {
  Polity: 'bg-orange-100 text-orange-600',
  Economy: 'bg-green-100 text-green-600',
  International: 'bg-blue-100 text-blue-600',
  IR: 'bg-blue-100 text-blue-600',
  Science: 'bg-purple-100 text-purple-600',
  Environment: 'bg-emerald-100 text-emerald-600',
  Defense: 'bg-red-100 text-red-600',
  Schemes: 'bg-indigo-100 text-indigo-600',
};

const PRIORITY_STYLE = {
  high: 'bg-red-500 text-white',
  medium: 'bg-amber-400 text-white',
  low: 'bg-gray-300 text-gray-600',
};

function getLast5Days() {
  return Array.from({ length: 5 }, (_, i) => {
    const d = new Date(); d.setDate(d.getDate() - i);
    return d.toISOString().split('T')[0];
  });
}

function fmtDate(dateStr) {
  const today = new Date().toISOString().split('T')[0];
  const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];
  if (dateStr === today) return 'Today';
  if (dateStr === yesterday) return 'Yesterday';
  return new Date(dateStr).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

// ── Article Detail Modal ─────────────────────────────────────────────────────
function ArticleModal({ article, onClose }) {
  const { addNote } = useApp();
  const [noted, setNoted] = useState(false);

  const handleNote = () => {
    let fullNote = `[${article.tag}] ${article.title}\n\n`;
    if (article.summary) fullNote += `Summary:\n${article.summary}\n\n`;
    if (article.keyPoints?.length > 0) fullNote += `Key Points:\n${article.keyPoints.map(p => '- ' + p).join('\n')}\n\n`;
    if (article.whyImportant) fullNote += `Why Important for UPSC:\n${article.whyImportant}\n\n`;
    if (article.syllabusLinks?.length > 0) fullNote += `Syllabus Linkage:\n${article.syllabusLinks.join(', ')}\n\n`;
    if (article.prelimsQuestions?.length > 0) fullNote += `Prelims Questions:\n${article.prelimsQuestions.map((q, i) => `Q${i+1}. ${q}`).join('\n')}\n\n`;
    if (article.mainsAnswer) fullNote += `Mains Answer Framework:\n${article.mainsAnswer}\n`;

    addNote(fullNote.trim());
    setNoted(true);
    setTimeout(() => setNoted(false), 2000);
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col justify-end md:justify-center p-0 md:p-8">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
        className="relative z-10 bg-white w-full md:max-w-3xl h-[92vh] md:h-auto md:max-h-[92vh] rounded-t-3xl md:rounded-3xl shadow-2xl overflow-hidden flex flex-col mt-auto md:mt-0">
        
        {/* Header */}
        <div className="bg-gradient-to-br from-[#0f2242] to-[#1a3a6b] p-5 md:p-8 pb-6 text-white flex-shrink-0">
          <button onClick={onClose} className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full transition-all">
            <X size={16} />
          </button>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest ${TAG_STYLE[article.tag] || 'bg-gray-100 text-gray-600'}`}>
              {article.tag}
            </span>
            {article.isImportant && (
              <span className="flex items-center gap-1 px-2.5 py-0.5 bg-amber-400 text-white rounded-full text-[10px] font-bold uppercase">
                <Star size={10} /> Important
              </span>
            )}
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${PRIORITY_STYLE[article.priority]}`}>
              {article.priority} priority
            </span>
            <span className="text-white/60 text-[10px] flex items-center gap-1">
              <Calendar size={10} /> {article.date}
            </span>
          </div>
          <h2 className="text-xl md:text-2xl font-black leading-tight">{article.title}</h2>
          <div className="mt-2 text-white/60 text-xs">Source: {article.source}</div>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 p-5 md:p-8 space-y-6 pb-8 md:pb-8">

          {/* Summary */}
          <div className="border-l-4 border-amber-400 pl-4 bg-amber-50 py-3 rounded-r-xl">
            <div className="text-[10px] font-bold uppercase text-amber-600 mb-1 tracking-widest">Summary</div>
            <p className="text-sm text-gray-700 leading-relaxed">{article.summary}</p>
          </div>

          {/* Key Points */}
          {article.keyPoints?.length > 0 && (
            <div>
              <div className="text-[11px] font-bold uppercase text-[#0f2242] tracking-widest mb-2">Key Points</div>
              <ul className="space-y-2">
                {article.keyPoints.map((pt, i) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-600">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                    {pt}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Why Important */}
          {article.whyImportant && (
            <div className="bg-blue-50 rounded-2xl p-4">
              <div className="text-[11px] font-bold uppercase text-blue-600 tracking-widest mb-1.5">
                <Zap size={12} className="inline mr-1" />Why This Matters for UPSC
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">{article.whyImportant}</p>
            </div>
          )}

          {/* Syllabus Links */}
          {article.syllabusLinks?.length > 0 && (
            <div>
              <div className="text-[11px] font-bold uppercase text-[#0f2242] tracking-widest mb-2">Syllabus Linkage</div>
              <div className="flex flex-wrap gap-2">
                {article.syllabusLinks.map((s, i) => (
                  <span key={i} className="px-3 py-1 bg-[#0f2242]/5 text-[#0f2242] rounded-full text-xs font-medium">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Prelims Qs */}
          {article.prelimsQuestions?.length > 0 && (
            <div>
              <div className="text-[11px] font-bold uppercase text-orange-600 tracking-widest mb-2">Possible Prelims Questions</div>
              <ul className="space-y-2">
                {article.prelimsQuestions.map((q, i) => (
                  <li key={i} className="flex gap-2 text-sm bg-orange-50 rounded-xl px-4 py-2.5 text-gray-700">
                    <span className="font-bold text-orange-500 shrink-0">Q{i + 1}.</span> {q}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Mains Answer */}
          {article.mainsAnswer && (
            <div>
              <div className="text-[11px] font-bold uppercase text-green-700 tracking-widest mb-2">Mains Answer Framework</div>
              <div className="bg-green-50 rounded-2xl p-4 text-sm text-gray-700 leading-relaxed whitespace-pre-line border border-green-100">
                {article.mainsAnswer}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 p-4 md:p-6 border-t border-gray-100 flex flex-col sm:flex-row gap-3 bg-gray-50/50">
          <button onClick={handleNote}
            className={`flex-1 flex justify-center items-center gap-2 px-5 py-3.5 md:py-2.5 rounded-xl font-bold text-sm transition-all ${noted ? 'bg-green-500 text-white' : 'bg-[#0f2242] text-white hover:opacity-90 shadow-md'}`}>
            {noted ? <><Check size={16} /> Added to Notes!</> : <><Plus size={16} /> Add to Notes</>}
          </button>
          {article.url && (
            <a href={article.url} target="_blank" rel="noreferrer"
              className="flex-1 flex justify-center items-center gap-2 px-5 py-3.5 md:py-2.5 rounded-xl font-bold text-sm border border-gray-200 hover:bg-gray-50 bg-white text-gray-600 transition-all">
              <ExternalLink size={14} /> Read Original
            </a>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
const DailyNews = () => {
  const { addNote } = useApp();
  const last5 = getLast5Days();
  const [selectedDate, setSelectedDate] = useState(last5[0]);
  const [selectionMenu, setSelectionMenu] = useState(null);
  const [activeCategory, setActiveCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [fetchError, setFetchError] = useState(null);
  const [showAnalysis, setShowAnalysis] = useState(true);
  const [isDateDropdownOpen, setIsDateDropdownOpen] = useState(false);
  const [allArticles, setAllArticles] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [availableDates, setAvailableDates] = useState(last5);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [nextRefreshIn, setNextRefreshIn] = useState(300); // seconds

  const AUTO_REFRESH_INTERVAL = 5 * 60; // 5 minutes in seconds

  const fetchAvailableDates = useCallback(async () => {
    try {
      const statsRes = await fetch(`${API_BASE}/daily-news/stats`);
      if (statsRes.ok) {
        const stats = await statsRes.json();
        if (stats.dates_available?.length > 0) {
          setAvailableDates(stats.dates_available);
          return stats.dates_available;
        }
      }
    } catch (err) {
      console.error('Failed to fetch available dates:', err);
    }
    return null;
  }, []);

  // Fetch available dates on mount and default to latest available if current selection isn't present
  useEffect(() => {
    const initDates = async () => {
      const dates = await fetchAvailableDates();
      if (dates && dates.length > 0) {
        // If today has no data, default to the latest date that actually has data
        const today = last5[0];
        if (!dates.includes(selectedDate)) {
          setSelectedDate(dates[0]);
        }
      }
    };
    initDates();
  }, [fetchAvailableDates]);

  // ── Fetch articles for selected date from backend ──
  const fetchNews = useCallback(async (date) => {
    setLoading(true);
    setFetchError(null);
    try {
      // Use the richer day endpoint to get articles + overview + categories in one call
      const res = await fetch(`${API_BASE}/daily-news/day/${date}`);
      if (!res.ok) {
        if (res.status === 404) {
          // No data for this date yet
          setAllArticles([]);
          setAnalysis(null);
          setLoading(false);
          return;
        }
        throw new Error(`Server error: ${res.status}`);
      }
      const data = await res.json();

      // Normalize articles to ensure consistent field names
      const normalized = (data.articles || []).map(a => ({
        ...a,
        title: a.title || a.headline || 'Untitled',
        tag: a.tag || a.category || 'Polity',
        summary: a.summary || (a.analysis && a.analysis.summary) || '',
        keyPoints: a.keyPoints || (a.analysis && a.analysis.key_points) || [],
        whyImportant: a.whyImportant || (a.analysis && a.analysis.exam_relevance) || 'Relevant for UPSC GS preparation.',
        syllabusLinks: a.syllabusLinks || (a.analysis && a.analysis.syllabus_linkage) || [],
        prelimsQuestions: a.prelimsQuestions || (a.analysis && a.analysis.prelims_questions) || [],
        mainsAnswer: a.mainsAnswer || 'Analysis pending.',
        isImportant: a.isImportant || a.is_most_important || false,
        priority: a.priority || 'medium',
      }));
      setAllArticles(normalized);

      // Set analysis panel data
      setAnalysis({
        title: data.title || `UPSC Daily Briefing — ${fmtDate(date)}`,
        overview: typeof data.overview === 'string'
          ? data.overview
          : `${normalized.length} articles collected for ${date}.`,
        categories: data.categories || {},
      });

      // Update available dates from stats
      fetchAvailableDates();

    } catch (err) {
      console.error('News fetch failed:', err);
      setFetchError(err.message);
      setAllArticles([]);
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  }, [fetchAvailableDates]);

  useEffect(() => { fetchNews(selectedDate); }, [selectedDate, fetchNews]);

  // ── Auto-poll: silently refresh every 5 minutes ──
  useEffect(() => {
    const selectedDateRef = { current: selectedDate };
    selectedDateRef.current = selectedDate;

    // Countdown timer (ticks every second)
    let countdown = AUTO_REFRESH_INTERVAL;
    setNextRefreshIn(countdown);
    const tickInterval = setInterval(() => {
      countdown -= 1;
      setNextRefreshIn(countdown);
      if (countdown <= 0) {
        countdown = AUTO_REFRESH_INTERVAL;
        setNextRefreshIn(countdown);
        // Silent background refresh — no full loading spinner
        setIsRefreshing(true);
        fetch(`${API_BASE}/daily-news/day/${selectedDateRef.current}`)
          .then(r => r.ok ? r.json() : null)
          .then(data => {
            if (!data) return;
            const normalized = (data.articles || []).map(a => ({
              ...a,
              title: a.title || a.headline || 'Untitled',
              tag: a.tag || a.category || 'Polity',
              summary: a.summary || (a.analysis && a.analysis.summary) || '',
              keyPoints: a.keyPoints || (a.analysis && a.analysis.key_points) || [],
              whyImportant: a.whyImportant || (a.analysis && a.analysis.exam_relevance) || 'Relevant for UPSC GS preparation.',
              syllabusLinks: a.syllabusLinks || (a.analysis && a.analysis.syllabus_linkage) || [],
              prelimsQuestions: a.prelimsQuestions || (a.analysis && a.analysis.prelims_questions) || [],
              mainsAnswer: a.mainsAnswer || 'Analysis pending.',
              isImportant: a.isImportant || a.is_most_important || false,
              priority: a.priority || 'medium',
            }));
            setAllArticles(normalized);
            setAnalysis({
              title: data.title || `UPSC Daily Briefing — ${fmtDate(selectedDateRef.current)}`,
              overview: typeof data.overview === 'string' ? data.overview : `${normalized.length} articles collected.`,
              categories: data.categories || {},
            });
            setLastUpdated(new Date());
          })
          .catch(() => {})
          .finally(() => setIsRefreshing(false));
      }
    }, 1000);

    return () => clearInterval(tickInterval);
  }, [selectedDate, AUTO_REFRESH_INTERVAL]);

  // Track last updated time on initial load
  useEffect(() => {
    if (allArticles.length > 0 && !lastUpdated) setLastUpdated(new Date());
  }, [allArticles]);

  useEffect(() => {
    const handleScroll = () => setSelectionMenu(null);
    window.addEventListener('scroll', handleScroll, true);
    return () => window.removeEventListener('scroll', handleScroll, true);
  }, []);

  const handleMouseUp = (e) => {
    if (e.target.closest('.selection-popup')) return;
    
    setTimeout(() => {
      const selection = window.getSelection();
      const text = selection.toString().trim();
      if (text) {
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        setSelectionMenu({
          text,
          top: Math.max(10, rect.top - 55),
          left: Math.max(120, Math.min(window.innerWidth - 120, rect.left + (rect.width / 2))),
        });
      } else {
        setSelectionMenu(null);
      }
    }, 10);
  };

  const handleDateChange = (date) => {
    setSelectedDate(date);
    setActiveCategory('all');
    setSearchQuery('');
  };

  const allForDate = allArticles;
  const important = allForDate.filter(n => n.isImportant);

  const filtered = allForDate.filter(n => {
    const matchCat = activeCategory === 'all' || n.tag === activeCategory;
    const matchSearch = !searchQuery || n.title.toLowerCase().includes(searchQuery.toLowerCase()) || n.summary?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchCat && matchSearch;
  });

  return (
    <div 
      className="p-4 md:p-8 w-full flex-1 mx-auto pb-32 md:pb-24 flex flex-col"
      onMouseUp={handleMouseUp}
      onPointerDown={(e) => { if (!e.target.closest('.selection-popup')) setSelectionMenu(null); }}
    >
      <AnimatePresence>
        {selectionMenu && (
          <motion.div 
            initial={{ opacity: 0, y: 10, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="selection-popup fixed z-[100] flex items-center gap-1 bg-[#0f2242] text-white p-1.5 rounded-xl shadow-2xl border border-white/10"
            style={{ top: selectionMenu.top, left: selectionMenu.left, transform: 'translateX(-50%)' }}
          >
            <button 
              onClick={() => {
                navigator.clipboard.writeText(selectionMenu.text);
                setSelectionMenu(null);
                window.getSelection().removeAllRanges();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 hover:bg-white/10 rounded-lg text-xs font-bold transition-colors"
            >
              <Copy size={14} /> Copy
            </button>
            <div className="w-px h-4 bg-white/20" />
            <button 
              onClick={() => {
                addNote(`From News: "${selectionMenu.text}"`);
                setSelectionMenu(null);
                window.getSelection().removeAllRanges();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 hover:bg-white/10 rounded-lg text-xs font-bold text-amber-400 transition-colors"
            >
              <Plus size={14} /> Add to notes
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>{selectedArticle && <ArticleModal article={selectedArticle} onClose={() => setSelectedArticle(null)} />}</AnimatePresence>

      {/* ── Live Status Bar ── */}
      <div className="flex items-center gap-3 mb-4 px-3 py-2 bg-gray-50 rounded-xl border border-gray-100 text-[10px] font-medium text-gray-400">
        {/* Pipeline status */}
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span>Pipeline: <span className="text-green-600 font-bold">LIVE</span> — collects 2x daily</span>
        </div>
        <div className="w-px h-3 bg-gray-200" />
        {/* Last updated */}
        {lastUpdated && (
          <div className="flex items-center gap-1">
            <RefreshCw size={9} />
            Last updated: <span className="text-gray-600">{lastUpdated.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
        )}
        {lastUpdated && <div className="w-px h-3 bg-gray-200" />}
        {/* Auto-refresh countdown */}
        <div className="flex items-center gap-1 ml-auto">
          {isRefreshing ? (
            <><RefreshCw size={9} className="animate-spin text-amber-500" /><span className="text-amber-600 font-bold">Refreshing...</span></>
          ) : (
            <><span>Auto-refresh in:</span>
            <span className="text-[#0f2242] font-bold tabular-nums">
              {`${Math.floor(nextRefreshIn / 60)}:${String(nextRefreshIn % 60).padStart(2, '0')}`}
            </span></>
          )}
        </div>
      </div>

      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-3">
        <div>
          <h2 className="text-2xl md:text-3xl font-black text-[#0f2242]">Daily News Intelligence</h2>
          <p className="text-xs text-gray-400 mt-0.5">Live current affairs from The Hindu &amp; PIB — collected 2 times a day</p>
        </div>
        <div className="flex items-center gap-2">
        {/* Refresh Button */}
        <button onClick={() => fetchNews(selectedDate)} disabled={loading || isRefreshing}
          className="flex items-center gap-1.5 px-3 py-2.5 rounded-2xl bg-amber-50 hover:bg-amber-100 text-amber-700 text-xs font-bold transition-colors disabled:opacity-50">
          <RefreshCw size={13} className={(loading || isRefreshing) ? 'animate-spin' : ''} /> Refresh
        </button>
        {/* Date Dropdown */}
        <div className="relative">
          <button 
            onClick={() => setIsDateDropdownOpen(!isDateDropdownOpen)}
            className="flex items-center gap-2 bg-gray-100 hover:bg-gray-200 px-4 py-2.5 rounded-2xl text-sm font-bold text-[#0f2242] transition-colors"
          >
            <Calendar size={16} className="text-gray-500" />
            {fmtDate(selectedDate)}
            <ChevronRight size={14} className={`text-gray-500 transition-transform ${isDateDropdownOpen ? 'rotate-[-90deg]' : 'rotate-90'}`} />
          </button>
          
          <AnimatePresence>
            {isDateDropdownOpen && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="absolute right-0 top-full mt-2 w-48 bg-white border border-gray-100 rounded-2xl shadow-xl z-20 overflow-hidden"
              >
                {availableDates.map(d => (
                  <button 
                    key={d} 
                    onClick={() => { handleDateChange(d); setIsDateDropdownOpen(false); }}
                    className={`w-full text-left px-4 py-3 text-sm font-bold hover:bg-gray-50 transition-colors flex justify-between items-center ${selectedDate === d ? 'text-[#0f2242] bg-gray-50/50' : 'text-gray-500'}`}
                  >
                    {fmtDate(d)}
                    {selectedDate === d && <Check size={14} className="text-amber-500" />}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        </div>
      </div>

      {/* ── Search ── */}
      <div className="relative mb-4">
        <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text" placeholder="Search news, topics, keywords..."
          value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-3 bg-white border border-gray-200 rounded-2xl text-sm outline-none focus:border-[#0f2242] transition-all shadow-sm"
        />
        {searchQuery && (
          <button onClick={() => setSearchQuery('')} className="absolute right-4 top-1/2 -translate-y-1/2">
            <X size={14} className="text-gray-400" />
          </button>
        )}
      </div>

      {/* ── Category Chips ── */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-6 no-scrollbar">
        {CATEGORIES.map(cat => (
          <button key={cat.key} onClick={() => setActiveCategory(cat.key)}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all border ${
              activeCategory === cat.key
                ? 'bg-[#0f2242] text-white border-[#0f2242] shadow-md'
                : 'bg-white text-gray-500 border-gray-200 hover:border-gray-300'
            }`}>
            {cat.icon}{cat.label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {loading ? (
          <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center py-24">
            <div className="w-10 h-10 border-4 border-[#0f2242]/10 border-t-[#0f2242] rounded-full animate-spin mb-4" />
            <p className="text-sm text-gray-400">Fetching intelligence...</p>
          </motion.div>
        ) : fetchError ? (
          <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-24 bg-red-50 rounded-3xl border-2 border-dashed border-red-200">
            <AlertCircle size={36} className="text-red-300 mb-3" />
            <p className="text-red-600 font-bold mb-1">Could not load news</p>
            <p className="text-red-400 text-sm mb-4">{fetchError}</p>
            <p className="text-gray-400 text-xs mb-4">Make sure the backend server is running on port 8000</p>
            <button onClick={() => fetchNews(selectedDate)}
              className="px-5 py-2 bg-red-500 text-white rounded-xl text-sm font-bold hover:bg-red-600 transition-colors">
              Try Again
            </button>
          </motion.div>
        ) : (
          <motion.div key={selectedDate} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">

            {/* ── Today's Analysis Overview ── */}
            {analysis && !searchQuery && activeCategory === 'all' && (
              <div>
                <motion.div className="bg-gradient-to-br from-[#0f2242] to-[#1e3f7a] rounded-3xl p-6 md:p-8 text-white shadow-xl relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -mr-20 -mt-20 blur-3xl pointer-events-none" />
                  <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-5 h-0.5 bg-amber-400 rounded-full" />
                      <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-400">Daily Overview — {fmtDate(selectedDate)}</span>
                    </div>
                    <h3 className="text-lg md:text-xl font-bold mb-3 leading-snug">{analysis.title}</h3>
                    <p className="text-white/75 text-sm leading-relaxed">{analysis.overview}</p>
                    <button onClick={() => setShowAnalysis(v => !v)}
                      className="mt-4 flex items-center gap-1.5 text-amber-400 text-xs font-bold hover:underline">
                      {showAnalysis ? 'Hide' : 'Show'} Category Breakdown <ChevronRight size={12} className={`transition-transform ${showAnalysis ? 'rotate-90' : ''}`} />
                    </button>
                  </div>
                </motion.div>

                {/* Category Breakdown Grid */}
                {showAnalysis && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                    {Object.entries(analysis.categories).map(([key, points]) =>
                      points.length > 0 && (
                        <motion.div key={key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                          className="bg-white border border-gray-100 rounded-2xl p-5 hover:shadow-md transition-shadow">
                          <div className="flex items-center gap-2.5 mb-3 pb-2 border-b border-gray-50">
                            <div className="p-1.5 bg-gray-50 rounded-lg">{CAT_ICONS[key]}</div>
                            <span className="text-sm font-bold text-[#0f2242]">{CAT_LABELS[key]}</span>
                          </div>
                          <ul className="space-y-2">
                            {points.map((pt, i) => (
                              <li key={i} className="flex gap-2 text-xs text-gray-500 leading-relaxed">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />{pt}
                              </li>
                            ))}
                          </ul>
                        </motion.div>
                      )
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── Most Important Banner ── */}
            {important.length > 0 && !searchQuery && activeCategory === 'all' && (
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <Star size={16} className="text-amber-500" />
                  <h3 className="text-base font-bold text-[#0f2242]">Must-Read Today</h3>
                  <div className="h-px flex-1 bg-gray-100" />
                </div>
                <div className="grid gap-3">
                  {important.map((art, i) => (
                    <motion.div key={art.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                      onClick={() => setSelectedArticle(art)}
                      className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl p-4 flex items-center gap-4 cursor-pointer hover:shadow-md transition-all group">
                      <div className="w-10 h-10 bg-amber-400 rounded-xl flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                        <Star size={18} className="text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded-full ${TAG_STYLE[art.tag] || 'bg-gray-100 text-gray-600'}`}>{art.tag}</span>
                          <span className="text-[9px] font-bold text-red-500 uppercase">High Priority</span>
                        </div>
                        <p className="text-sm md:text-base font-bold text-[#0f2242] leading-tight line-clamp-2 md:line-clamp-1">{art.title}</p>
                      </div>
                      <ChevronRight size={16} className="text-amber-500 shrink-0 group-hover:translate-x-1 transition-transform" />
                    </motion.div>
                  ))}
                </div>
              </div>
            )}

            {/* ── All Articles ── */}
            <div>
              <div className="flex items-center gap-3 mb-3">
                <Filter size={15} className="text-gray-400" />
                <h3 className="text-base font-bold text-[#0f2242]">
                  {searchQuery ? `Search: "${searchQuery}"` : activeCategory === 'all' ? 'All Articles' : activeCategory}
                </h3>
                <span className="text-xs text-gray-400 font-medium">{filtered.length} items</span>
                <div className="h-px flex-1 bg-gray-100" />
              </div>

              {filtered.length === 0 ? (
                <div className="text-center py-16 bg-gray-50 rounded-3xl border-2 border-dashed border-gray-200">
                  <Search size={36} className="text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 font-medium">No articles found</p>
                  <p className="text-gray-400 text-sm mt-1">Try a different date or category</p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {filtered.map((art, i) => (
                    <motion.div key={art.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
                      onClick={() => setSelectedArticle(art)}
                      className="bg-white border border-gray-100 rounded-2xl overflow-hidden group cursor-pointer hover:shadow-lg hover:border-[#0f2242]/20 transition-all">
                      <div className="p-5 md:p-6">
                        <div className="flex items-start justify-between gap-3 mb-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-widest ${TAG_STYLE[art.tag] || 'bg-gray-100 text-gray-600'}`}>
                              {art.tag}
                            </span>
                            {art.isImportant && (
                              <span className="flex items-center gap-0.5 px-2 py-0.5 bg-amber-100 text-amber-600 rounded-full text-[9px] font-bold uppercase">
                                <Star size={8} /> Important
                              </span>
                            )}
                            <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${PRIORITY_STYLE[art.priority]}`}>
                              {art.priority}
                            </span>
                          </div>
                          <span className="text-[9px] text-gray-400 font-medium whitespace-nowrap shrink-0 flex items-center gap-1">
                            <Calendar size={9} />{art.date}
                          </span>
                        </div>

                        <h3 className="text-base font-bold text-[#0f2242] mb-2 leading-snug group-hover:text-amber-600 transition-colors">
                          {art.title}
                        </h3>
                        <p className="text-xs text-gray-400 mb-3 leading-relaxed line-clamp-2">{art.summary}</p>

                        <div className="flex items-center justify-between pt-3 border-t border-gray-50">
                          <div className="flex items-center gap-3">
                            <span className="text-[10px] font-bold text-gray-400">{art.source}</span>
                            <button 
                              onClick={(e) => { e.stopPropagation(); window.open(art.url, '_blank'); }}
                              className="text-xs font-bold text-amber-500 flex items-center gap-1 hover:gap-2 transition-all"
                            >
                              Read Original Article <ExternalLink size={11} />
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Key points preview */}
                      {art.keyPoints?.length > 0 && (
                        <div className="px-5 md:px-6 pb-4 border-t border-gray-50 pt-3 grid grid-cols-1 gap-1">
                          {art.keyPoints.slice(0, 2).map((kp, ki) => (
                            <div key={ki} className="flex gap-2 text-[11px] text-gray-400">
                              <span className="w-1 h-1 rounded-full bg-amber-400 mt-1.5 shrink-0" />{kp}
                            </div>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default DailyNews;
