import { useCallback, useEffect, useState } from 'react'
import {
  ExternalLink,
  Loader2,
  Plus,
  RefreshCw,
  Rss,
  Search,
  Trash2,
  X,
  ChevronDown,
  ChevronUp,
  AlertCircle,
} from 'lucide-react'
import { useDialog } from '../context/useDialog'

const CATEGORY_COLORS = {
  news:      { bg: 'bg-blue-500/15',   text: 'text-blue-300',   border: 'border-blue-500/30' },
  sport:     { bg: 'bg-green-500/15',  text: 'text-green-300',  border: 'border-green-500/30' },
  meteo:     { bg: 'bg-sky-500/15',    text: 'text-sky-300',    border: 'border-sky-500/30' },
  wellness:  { bg: 'bg-teal-500/15',   text: 'text-teal-300',   border: 'border-teal-500/30' },
  motori:    { bg: 'bg-orange-500/15', text: 'text-orange-300', border: 'border-orange-500/30' },
  tech:      { bg: 'bg-purple-500/15', text: 'text-purple-300', border: 'border-purple-500/30' },
  cultura:   { bg: 'bg-pink-500/15',   text: 'text-pink-300',   border: 'border-pink-500/30' },
  economia:  { bg: 'bg-yellow-500/15', text: 'text-yellow-300', border: 'border-yellow-500/30' },
  breaking:  { bg: 'bg-red-500/15',    text: 'text-red-300',    border: 'border-red-500/30' },
  general:   { bg: 'bg-slate-500/15',  text: 'text-slate-300',  border: 'border-slate-500/30' },
}

function CategoryBadge({ category }) {
  const c = CATEGORY_COLORS[category] || CATEGORY_COLORS.general
  return (
    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded border ${c.bg} ${c.text} ${c.border}`}>
      {category}
    </span>
  )
}

function PreviewPanel({ feedId, url, onClose }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true

    Promise.resolve().then(() => {
      setLoading(true)
      setError(null)
      return fetch(`/api/sources/${encodeURIComponent(feedId)}/preview`)
        .then(r => r.json())
        .then(d => {
          if (!active) return
          if (d.error) setError(d.error)
          else setData(d)
        })
        .catch((err) => {
          console.error('Errore anteprima fonte:', err)
          if (active) setError('Errore di rete')
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    })

    return () => {
      active = false
    }
  }, [feedId, url])

  return (
    <div className="mt-3 rounded-lg border border-slate-700 bg-slate-950/80 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
          <Rss size={12} /> Anteprima Feed
        </span>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition">
          <X size={14} />
        </button>
      </div>
      <div className="p-3 space-y-2 max-h-64 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center py-6 gap-2 text-slate-500 text-sm">
            <Loader2 size={16} className="animate-spin" /> Caricamento feed...
          </div>
        )}
        {error && !loading && (
          <div className="flex items-center gap-2 text-red-400 text-sm py-4">
            <AlertCircle size={14} /> {error}
          </div>
        )}
        {data && !loading && (
          <>
            <p className="text-[11px] font-semibold text-slate-400 mb-2">{data.feed_title}</p>
            {(data.items || []).map((item, i) => (
              <a
                key={i}
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 transition group"
              >
                <div className="text-xs font-semibold text-slate-200 group-hover:text-white flex items-start justify-between gap-2">
                  <span className="flex-1 leading-snug">{item.title}</span>
                  <ExternalLink size={11} className="shrink-0 mt-0.5 text-slate-500 group-hover:text-slate-300" />
                </div>
                {item.published && (
                  <div className="text-[10px] text-slate-500 mt-1">{item.published}</div>
                )}
              </a>
            ))}
            {(!data.items || data.items.length === 0) && (
              <p className="text-xs text-slate-500 text-center py-3">Nessun articolo trovato.</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function SourceCard({ source, onDelete, onPreview, previewOpenId }) {
  const isPreviewOpen = previewOpenId === source.id

  return (
    <div className="rounded-xl border transition-all bg-slate-900/60 border-slate-700">
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          {/* Sinistra: info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-sm font-bold text-slate-100 font-mono">{source.id}</span>
              <CategoryBadge category={source.category} />
            </div>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-slate-400 hover:text-slate-200 truncate block transition flex items-center gap-1"
            >
              {source.url}
              <ExternalLink size={10} className="shrink-0" />
            </a>
            <div className="text-[10px] text-slate-600 mt-1">
              Fonte attiva caricata da <span className="font-mono">registry.py</span>
            </div>
          </div>

          {/* Destra: azioni */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => onPreview(source.id)}
              title="Anteprima feed"
              className="p-2 rounded-lg text-slate-400 hover:text-indigo-300 hover:bg-indigo-500/10 transition border border-transparent hover:border-indigo-500/30"
            >
              {isPreviewOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>
            <button
              onClick={() => onDelete(source.id)}
              title="Rimuovi fonte"
              className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition border border-transparent hover:border-red-500/30"
            >
              <Trash2 size={15} />
            </button>
          </div>
        </div>

        {isPreviewOpen && (
          <PreviewPanel
            feedId={source.id}
            url={source.url}
            onClose={() => onPreview(null)}
          />
        )}
      </div>
    </div>
  )
}

const CATEGORIES = ['all', 'news', 'sport', 'meteo', 'wellness', 'motori', 'tech', 'cultura', 'economia', 'breaking', 'general']

export default function Sources() {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterCategory, setFilterCategory] = useState('all')
  const [previewOpenId, setPreviewOpenId] = useState(null)
  const [addOpen, setAddOpen] = useState(false)
  const [addForm, setAddForm] = useState({ id: '', url: '', category: 'news' })
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError] = useState('')
  const { showAlert, showConfirm } = useDialog()

  const fetchSources = useCallback(async () => {
    try {
      const res = await fetch('/api/sources')
      if (res.ok) {
        const data = await res.json()
        setSources(data.sources || [])
      }
    } catch (e) {
      console.error('Errore caricamento fonti:', e)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { Promise.resolve().then(fetchSources) }, [fetchSources])

  const handleDelete = async (feedId) => {
    if (!await showConfirm(
      `Rimuovere la fonte "${feedId}"? Verrà eliminata direttamente da registry.py.`,
      'Rimuovi Fonte'
    )) return
    try {
      const res = await fetch(`/api/sources/${encodeURIComponent(feedId)}`, { method: 'DELETE' })
      const d = await res.json()
      if (!res.ok) { await showAlert(d.error || 'Errore.', 'Errore'); return }
      setSources(prev => prev.filter(s => s.id !== feedId))
      if (previewOpenId === feedId) setPreviewOpenId(null)
    } catch (e) {
      console.error('Errore eliminazione fonte:', e)
      await showAlert('Errore di rete.', 'Errore')
    }
  }

  const handlePreview = (feedId) => {
    setPreviewOpenId(prev => prev === feedId ? null : feedId)
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    setAddError('')
    if (!addForm.id.trim() || !addForm.url.trim()) {
      setAddError('ID e URL sono obbligatori.')
      return
    }
    setAddLoading(true)
    try {
      const res = await fetch('/api/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(addForm),
      })
      const d = await res.json()
      if (!res.ok) { setAddError(d.error || 'Errore.'); return }
      await fetchSources()
      setAddForm({ id: '', url: '', category: 'news' })
      setAddOpen(false)
      await showAlert(`Fonte "${addForm.id}" aggiunta con successo.`, 'Fonte Aggiunta')
    } catch (e) {
      console.error('Errore aggiunta fonte:', e)
      setAddError('Errore di rete.')
    } finally { setAddLoading(false) }
  }

  const filtered = sources.filter(s => {
    const matchSearch = !search ||
      s.id.toLowerCase().includes(search.toLowerCase()) ||
      s.url.toLowerCase().includes(search.toLowerCase())
    const matchCat = filterCategory === 'all' || s.category === filterCategory
    return matchSearch && matchCat
  })

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-black text-slate-100 flex items-center gap-2">
            <Rss size={22} className="text-indigo-400" /> Fonti RSS
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {sources.length} fonti attive - modifiche scritte su <span className="font-mono">registry.py</span> e visibili alla regia al giro successivo
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchSources}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition border border-slate-700"
          >
            <RefreshCw size={16} />
          </button>
          <button
            onClick={() => { setAddOpen(v => !v); setAddError('') }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-sm transition border ${
              addOpen
                ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/50'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white border-transparent shadow-[0_0_12px_rgba(99,102,241,0.35)]'
            }`}
          >
            {addOpen ? <X size={15} /> : <Plus size={15} />}
            {addOpen ? 'Annulla' : 'Aggiungi Fonte'}
          </button>
        </div>
      </div>

      {/* Add Form */}
      {addOpen && (
        <form
          onSubmit={handleAdd}
          className="glass rounded-xl border border-indigo-500/30 p-5 space-y-4"
        >
          <h2 className="text-sm font-bold uppercase tracking-widest text-indigo-400 flex items-center gap-2">
            <Plus size={14} /> Nuova Fonte RSS
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">
                ID Fonte *
              </label>
              <input
                id="source-id-input"
                value={addForm.id}
                onChange={e => setAddForm(f => ({ ...f, id: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '') }))}
                placeholder="es. corriere_cronaca"
                className="w-full bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none transition font-mono"
              />
              <p className="text-[10px] text-slate-600 mt-1">Solo minuscole, numeri, underscore</p>
            </div>
            <div className="md:col-span-1">
              <label className="block text-[11px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">
                Categoria
              </label>
              <select
                value={addForm.category}
                onChange={e => setAddForm(f => ({ ...f, category: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:outline-none transition"
              >
                {CATEGORIES.filter(c => c !== 'all').map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="md:col-span-1 flex items-end">
              <button
                type="submit"
                disabled={addLoading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold text-sm py-2.5 px-4 rounded-lg transition flex items-center justify-center gap-2"
              >
                {addLoading ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                {addLoading ? 'Salvataggio...' : 'Aggiungi'}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">
              URL Feed RSS *
            </label>
            <input
              id="source-url-input"
              value={addForm.url}
              onChange={e => setAddForm(f => ({ ...f, url: e.target.value }))}
              placeholder="https://www.esempio.it/feed.xml"
              className="w-full bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none transition font-mono"
            />
          </div>
          {addError && (
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle size={14} /> {addError}
            </div>
          )}
        </form>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Cerca per ID o URL..."
            className="w-full bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-lg pl-9 pr-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none transition"
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition border ${
                filterCategory === cat
                  ? 'bg-indigo-600 border-indigo-500 text-white'
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600'
              }`}
            >
              {cat === 'all' ? 'Tutte' : cat}
            </button>
          ))}
        </div>
      </div>

      {/* Sources Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-16 gap-3 text-slate-500">
          <Loader2 size={20} className="animate-spin" /> Caricamento fonti...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Rss size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nessuna fonte trovata.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          {filtered.map(source => (
            <SourceCard
              key={source.id}
              source={source}
              onDelete={handleDelete}
              onPreview={handlePreview}
              previewOpenId={previewOpenId}
            />
          ))}
        </div>
      )}

      {/* Footer stats */}
      {!loading && sources.length > 0 && (
        <div className="text-center text-[11px] text-slate-600">
          Mostrando {filtered.length} di {sources.length} fonti •{' '}
          Modifiche salvate in <span className="font-mono">src/newsica/sources/registry.py</span>
        </div>
      )}
    </div>
  )
}
