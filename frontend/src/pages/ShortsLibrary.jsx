import React, { useEffect, useState } from 'react'
import { Video, Calendar, Download, Play, RefreshCw, Copy, Trash2, Share2, CheckCircle2 } from 'lucide-react'
import { useDialog } from '../context/DialogContext'

export default function ShortsLibrary() {
  const shortModes = [
    { value: 'random', label: 'Casuale' },
    { value: 'news', label: 'News' },
    { value: 'breaking', label: 'Breaking News' },
    { value: 'sport', label: 'Sport' },
    { value: 'meteo', label: 'Meteo' },
    { value: 'tech', label: 'Tech' },
    { value: 'wellness', label: 'Wellness' },
    { value: 'funfact', label: 'Curiosità / Fun Fact' },
  ]
  const [shorts, setShorts] = useState([])
  const [loading, setLoading] = useState(true)
  const [playingShort, setPlayingShort] = useState(null)
  const [shortsLoading, setShortsLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [planLoading, setPlanLoading] = useState(false)
  const [planState, setPlanState] = useState({ date: '', summary: {}, items: [] })
  const [selectedMode, setSelectedMode] = useState('random')
  const [selectedShorts, setSelectedShorts] = useState([])
  const { showAlert, showConfirm } = useDialog()

  const themeTagByValue = {
    news: { label: 'News', className: 'bg-slate-900/85 text-slate-100 border-slate-600/70' },
    breaking: { label: 'Breaking', className: 'bg-red-600/90 text-white border-red-300/30' },
    sport: { label: 'Sport', className: 'bg-emerald-500/90 text-slate-950 border-emerald-200/30' },
    meteo: { label: 'Meteo', className: 'bg-sky-500/90 text-slate-950 border-sky-200/30' },
    tech: { label: 'Tech', className: 'bg-cyan-400/90 text-slate-950 border-cyan-200/30' },
    wellness: { label: 'Wellness', className: 'bg-teal-400/90 text-slate-950 border-teal-200/30' },
    funfact: { label: 'Fun Fact', className: 'bg-amber-400/95 text-slate-950 border-amber-100/40' },
  }

  const socialPlatformMeta = {
    youtube: { label: 'YouTube Shorts' },
    instagram: { label: 'Instagram Reels' },
    tiktok: { label: 'TikTok' },
  }

  const formatPostedAt = (value) => {
    if (!value) return ''
    try {
      return new Intl.DateTimeFormat('it-IT', {
        dateStyle: 'short',
        timeStyle: 'short',
      }).format(new Date(value))
    } catch (e) {
      return value
    }
  }

  const getPostedHint = (short) => {
    const socialPosts = short?.social_posts || {}
    const entries = Object.entries(socialPosts)
    if (entries.length === 0) return 'Non ancora pubblicato sui social.'
    return entries
      .map(([platform, payload]) => `${socialPlatformMeta[platform]?.label || platform}: ${formatPostedAt(payload.posted_at)}`)
      .join(' | ')
  }

  const fetchShorts = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/shorts_library')
      if (res.ok) {
        const data = await res.json()
        const nextShorts = data.shorts || []
        setShorts(nextShorts)
        setSelectedShorts((current) =>
          current.filter((filename) => nextShorts.some((short) => short.filename === filename))
        )
        setPlayingShort((current) => {
          if (!current) return current
          return nextShorts.find((short) => short.filename === current.filename) || current
        })
        return nextShorts
      }
    } catch (e) {
      console.error("Errore caricamento libreria shorts:", e)
    } finally {
      setLoading(false)
    }
  }

  const fetchPlanStatus = async () => {
    try {
      const res = await fetch('/api/shorts_plan_today')
      if (!res.ok) return
      const data = await res.json()
      setPlanState({
        date: data.date || '',
        summary: data.summary || {},
        items: data.items || [],
      })
    } catch (e) {
      console.error('Errore caricamento piano shorts:', e)
    }
  }

  useEffect(() => {
    fetchShorts()
    fetchPlanStatus()
  }, [])

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setPlayingShort(null)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const generateShort = async (mode = 'news') => {
    setShortsLoading(true)
    try {
      const res = await fetch('/api/generate_short', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      })
      const data = await res.json()
      if (res.ok) {
        const alertByMode = {
          random: 'Short generato in modalità casuale.',
          news: 'Short news generato con successo.',
          breaking: 'Short breaking news generato con successo.',
          sport: 'Short sport generato con successo.',
          meteo: 'Short meteo generato con successo.',
          tech: 'Short tech generato con successo.',
          wellness: 'Short wellness generato con successo.',
          funfact: 'Short curiosità generato con successo.',
        }
        await showAlert(
          alertByMode[mode] || 'Short generato con successo.',
          'Video Pronto'
        )
        setPlayingShort({
          filename: data.filename,
          url: data.video_url,
          news_title: data.news_title,
          script: data.script,
          caption: data.caption,
          hashtags: data.hashtags || [],
          hashtags_text: (data.hashtags || []).join(' '),
          social_posts: {},
          posted_any: false,
          posted_platforms: [],
        })
        fetchShorts()
      } else {
        await showAlert(`Errore: ${data.message || 'Generazione fallita'}`, 'Errore Generazione')
      }
    } catch (e) {
      await showAlert('Errore di connessione al server.', 'Errore di Rete')
    } finally {
      setShortsLoading(false)
    }
  }

  // Raggruppa gli shorts per data
  const groupedShorts = shorts.reduce((acc, short) => {
    const date = short.date_display
    if (!acc[date]) acc[date] = []
    acc[date].push(short)
    return acc
  }, {})

  const allSelected = shorts.length > 0 && selectedShorts.length === shorts.length

  const toggleShortSelection = (filename) => {
    setSelectedShorts((current) =>
      current.includes(filename)
        ? current.filter((item) => item !== filename)
        : [...current, filename]
    )
  }

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedShorts([])
      return
    }
    setSelectedShorts(shorts.map((short) => short.filename))
  }

  const deleteSelectedShorts = async () => {
    if (selectedShorts.length === 0) {
      await showAlert('Seleziona almeno un reel da eliminare.', 'Nessuna Selezione')
      return
    }

    const confirmed = await showConfirm(
      `Vuoi eliminare ${selectedShorts.length} reel selezionati?\n\nL'operazione rimuoverà sia i record dal database sia i file MP4 e i metadati associati.`,
      'Elimina Reel'
    )
    if (!confirmed) {
      return
    }

    setDeleteLoading(true)
    try {
      const res = await fetch('/api/shorts_delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filenames: selectedShorts }),
      })
      const data = await res.json()
      if (!res.ok) {
        await showAlert(`Errore: ${data.message || 'Eliminazione fallita.'}`, 'Errore Eliminazione')
        return
      }

      if (playingShort && selectedShorts.includes(playingShort.filename)) {
        setPlayingShort(null)
      }
      setSelectedShorts([])
      await fetchShorts()
      await showAlert(
        `Eliminati ${data.deleted_files} reel dai file e ${data.deleted_rows} record dal database.`,
        'Eliminazione Completata'
      )
    } catch (e) {
      await showAlert('Errore di connessione al server.', 'Errore di Rete')
    } finally {
      setDeleteLoading(false)
    }
  }

  const copyText = async (value, label) => {
    if (!value) {
      await showAlert(`Nessun contenuto disponibile per ${label.toLowerCase()}.`, 'Contenuto Assente')
      return
    }

    try {
      await navigator.clipboard.writeText(value)
      await showAlert(`${label} copiati negli appunti.`, 'Copiato')
    } catch (e) {
      console.error(`Errore copia ${label}:`, e)
      await showAlert(`Impossibile copiare ${label.toLowerCase()}.`, 'Errore Copia')
    }
  }

  const [publishing, setPublishing] = useState({ youtube: false, instagram: false, tiktok: false, all: false })

  const handlePublish = async (platform) => {
    setPublishing((prev) => (
      platform === 'all'
        ? { ...prev, youtube: true, instagram: true, tiktok: true, all: true }
        : { ...prev, [platform]: true }
    ))
    try {
      const res = await fetch('/api/shorts_publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: playingShort.filename, platform }),
      })
      const data = await res.json()
      if (res.ok && data.status === 'OK') {
        const refreshedShorts = await fetchShorts()
        const updatedShort = refreshedShorts?.find((short) => short.filename === playingShort.filename)
        if (updatedShort) {
          setPlayingShort(updatedShort)
        } else if (data.social_posts) {
          setPlayingShort((current) => current ? {
            ...current,
            social_posts: data.social_posts,
            posted_any: Object.keys(data.social_posts).length > 0,
            posted_platforms: Object.keys(data.social_posts),
          } : current)
        }
        await showAlert(data.message, 'Pubblicazione Completata')
      } else if (res.ok && data.status === 'partial') {
        const refreshedShorts = await fetchShorts()
        const updatedShort = refreshedShorts?.find((short) => short.filename === playingShort.filename)
        if (updatedShort) {
          setPlayingShort(updatedShort)
        }
        await showAlert(data.message, 'Pubblicazione Parziale')
      } else {
        await showAlert(
          data.message || 'Si è verificato un errore durante la pubblicazione.',
          'Info / Configurazione API'
        )
      }
    } catch (e) {
      await showAlert('Errore di rete durante la pubblicazione.', 'Errore di Rete')
    } finally {
      setPublishing((prev) => (
        platform === 'all'
          ? { ...prev, youtube: false, instagram: false, tiktok: false, all: false }
          : { ...prev, [platform]: false }
      ))
    }
  }

  const rebuildDailyPlan = async () => {
    setPlanLoading(true)
    try {
      const res = await fetch('/api/shorts_plan_rebuild', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true }),
      })
      const data = await res.json()
      await fetchPlanStatus()
      if (res.ok) {
        await showAlert(data.message || `Piano shorts aggiornato (${data.item_count || 0} item).`, 'Piano Aggiornato')
      } else {
        await showAlert(data.message || 'Impossibile rigenerare il piano shorts.', 'Errore Piano')
      }
    } catch (e) {
      await showAlert('Errore di rete durante la rigenerazione del piano.', 'Errore di Rete')
    } finally {
      setPlanLoading(false)
    }
  }

  const processOnePlanItem = async () => {
    setPlanLoading(true)
    try {
      const res = await fetch('/api/shorts_plan_process_once', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const data = await res.json()
      await fetchPlanStatus()
      await fetchShorts()
      if (res.ok) {
        await showAlert(data.message || 'Item shorts processato.', 'Piano Shorts')
      } else {
        await showAlert(data.message || 'Errore durante il processamento item.', 'Errore Piano')
      }
    } catch (e) {
      await showAlert('Errore di rete durante il processamento item.', 'Errore di Rete')
    } finally {
      setPlanLoading(false)
    }
  }

  return (
    <div className="pb-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <Video className="text-indigo-400" />
            Libreria Shorts
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Archivio storico dei video verticali generati da NewsicaTV
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={toggleSelectAll}
            disabled={loading || shorts.length === 0 || deleteLoading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm border border-slate-700 transition disabled:opacity-50"
          >
            {allSelected ? 'Deseleziona Tutti' : 'Seleziona Tutti'}
          </button>
          <button
            onClick={deleteSelectedShorts}
            disabled={selectedShorts.length === 0 || deleteLoading}
            className="flex items-center gap-2 px-4 py-2 bg-rose-700 hover:bg-rose-600 rounded-lg text-sm border border-rose-500/40 text-white transition disabled:opacity-50"
          >
            <Trash2 size={16} />
            {deleteLoading ? 'Eliminazione...' : `Elimina Selezionati${selectedShorts.length ? ` (${selectedShorts.length})` : ''}`}
          </button>
          <button
            onClick={fetchShorts}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm border border-slate-700 transition disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Aggiorna
          </button>
          <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/70 p-1">
            <select
              value={selectedMode}
              onChange={(event) => setSelectedMode(event.target.value)}
              disabled={shortsLoading}
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition disabled:opacity-50"
            >
              {shortModes.map((mode) => (
                <option key={mode.value} value={mode.value}>
                  {mode.label}
                </option>
              ))}
            </select>
            <button
              onClick={() => generateShort(selectedMode)}
              disabled={shortsLoading}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-bold shadow-[0_0_15px_rgba(79,70,229,0.3)] transition disabled:opacity-50"
            >
              <Play size={16} />
              {shortsLoading ? 'Generazione...' : 'Genera Short'}
            </button>
          </div>
        </div>
      </div>

      <div className="mb-6 rounded-xl border border-slate-800 bg-slate-950/70 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.16em] text-slate-400">Autonomia Shorts Giornaliera</div>
            <div className="mt-1 text-sm text-slate-200">
              Data: <span className="font-semibold text-white">{planState.date || '-'}</span> |
              {' '}planned: <span className="font-semibold text-slate-100">{planState.summary.planned || 0}</span> |
              {' '}generating: <span className="font-semibold text-slate-100">{planState.summary.generating || 0}</span> |
              {' '}scheduled: <span className="font-semibold text-emerald-300">{planState.summary.scheduled || 0}</span> |
              {' '}failed: <span className="font-semibold text-rose-300">{planState.summary.failed || 0}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={fetchPlanStatus}
              disabled={planLoading}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white disabled:opacity-50"
            >
              Aggiorna Piano
            </button>
            <button
              onClick={rebuildDailyPlan}
              disabled={planLoading}
              className="rounded-lg border border-indigo-500/40 bg-indigo-600/20 px-3 py-2 text-xs font-semibold text-indigo-200 transition hover:border-indigo-400 hover:text-white disabled:opacity-50"
            >
              {planLoading ? 'Attendi...' : 'Rigenera Piano Oggi'}
            </button>
            <button
              onClick={processOnePlanItem}
              disabled={planLoading}
              className="rounded-lg border border-emerald-500/40 bg-emerald-600/20 px-3 py-2 text-xs font-semibold text-emerald-200 transition hover:border-emerald-400 hover:text-white disabled:opacity-50"
            >
              Processa 1 Item
            </button>
          </div>
        </div>
      </div>

      {loading && shorts.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          Caricamento libreria in corso...
        </div>
      ) : shorts.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center border border-slate-800/50">
          <Video size={48} className="mx-auto text-slate-600 mb-4" />
          <h3 className="text-lg font-medium mb-2">Nessuno Short Generato</h3>
          <p className="text-slate-400 text-sm max-w-md mx-auto">
            Usa il selettore in alto per scegliere la tematica dello short oppure generarlo in modalità casuale.
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(groupedShorts).map(([date, dayShorts]) => (
            <div key={date}>
              <h2 className="text-lg font-bold text-slate-300 mb-4 flex items-center gap-2 border-b border-slate-800 pb-2">
                <Calendar size={18} className="text-indigo-400" />
                {date} <span className="text-sm font-normal text-slate-500">({dayShorts.length} video)</span>
              </h2>
              
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {dayShorts.map((short) => (
                  <div key={short.filename} className="glass rounded-lg overflow-hidden border border-slate-800/80 group">
                    <div 
                      className="aspect-[9/16] bg-slate-900 relative cursor-pointer"
                      onClick={(e) => { e.preventDefault(); setPlayingShort(short); }}
                    >
                      <div className="absolute left-2 top-2 z-10">
                        <input
                          type="checkbox"
                          checked={selectedShorts.includes(short.filename)}
                          onChange={() => toggleShortSelection(short.filename)}
                          onClick={(event) => event.stopPropagation()}
                          className="h-4 w-4 rounded border-slate-500 bg-slate-950 text-indigo-500 focus:ring-indigo-500"
                          aria-label={`Seleziona ${short.filename}`}
                        />
                      </div>
                      {short.theme && (
                        <div className="absolute right-2 top-2 z-10">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] shadow-lg ${themeTagByValue[short.theme]?.className || 'bg-slate-900/85 text-white border-slate-500/60'}`}
                          >
                            {themeTagByValue[short.theme]?.label || short.theme}
                          </span>
                        </div>
                      )}
                      {/* Anteprima video reale */}
                      <video 
                        src={short.url}
                        className="absolute inset-0 w-full h-full object-cover opacity-60 group-hover:opacity-80 transition-opacity pointer-events-none"
                        preload="metadata"
                        muted
                        playsInline
                      />
                      <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/80 flex items-center justify-center">
                        <div className="w-12 h-12 rounded-full bg-indigo-500/80 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.5)] group-hover:scale-110 transition-transform">
                          <Play className="text-white ml-1" fill="currentColor" size={20} />
                        </div>
                      </div>
                      
                      <div className="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/90 to-transparent">
                        <div className="text-xs font-mono text-slate-300">
                          {short.time_display}
                        </div>
                      </div>
                    </div>
                    
                    <div className="p-2 bg-slate-800/50 flex justify-between items-center">
                      <div className="min-w-0 pr-2">
                        <div className="text-[10px] text-slate-400 truncate" title={short.filename}>
                          {short.filename.replace('.mp4', '').replace('short_', '')}
                        </div>
                        {short.posted_any && (
                          <div
                            className="mt-1 inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-200"
                            title={getPostedHint(short)}
                          >
                            <CheckCircle2 size={11} />
                            {short.posted_platforms.length}/3 postati
                          </div>
                        )}
                      </div>
                      <a 
                        href={short.url} 
                        download={short.filename}
                        onClick={(e) => e.stopPropagation()}
                        className="text-slate-400 hover:text-white transition"
                        title="Scarica MP4"
                      >
                        <Download size={14} />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal Video Player */}
      {playingShort && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/90 p-4 backdrop-blur-sm"
          onClick={() => setPlayingShort(null)}
        >
          <div
            className="relative w-full max-w-6xl"
            onClick={(event) => event.stopPropagation()}
          >
            <button 
              onClick={(e) => { e.preventDefault(); setPlayingShort(null); }}
              className="absolute -top-10 right-0 text-white hover:text-slate-300 transition"
            >
              Chiudi (Esc)
            </button>
            <div className="grid gap-6 lg:grid-cols-[400px_minmax(0,1fr)]">
              <video 
                src={playingShort.url} 
                controls 
                autoPlay 
                playsInline
                className="w-full rounded-lg shadow-2xl bg-black aspect-[9/16]"
              />

              <div className="glass rounded-2xl border border-slate-800/80 p-5 text-slate-100">
                <div className="mb-5">
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-400 mb-2">
                    Contenuti Social
                  </div>
                  <h3 className="text-xl font-bold text-white">
                    {playingShort.news_title || 'Short NewsicaTV'}
                  </h3>
                  {playingShort.script && (
                    <p className="mt-2 text-sm text-slate-400 line-clamp-4">
                      {playingShort.script}
                    </p>
                  )}
                </div>

                <div className="space-y-4">
                  {/* Sezione Pubblicazione Social */}
                  <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                    <div className="mb-3">
                      <span className="text-sm font-semibold text-slate-200">Pubblica / Condividi sui Social</span>
                    </div>
                    <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                      {Object.entries(socialPlatformMeta).map(([platform, meta]) => {
                        const socialPost = playingShort.social_posts?.[platform]
                        const isPosted = Boolean(socialPost?.posted_at)
                        return (
                          <div
                            key={platform}
                            title={isPosted ? `Gia pubblicato il ${formatPostedAt(socialPost.posted_at)}` : 'Non ancora pubblicato'}
                            className={`rounded-lg border px-3 py-2 text-xs ${
                              isPosted
                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                                : 'border-slate-700 bg-slate-900/70 text-slate-400'
                            }`}
                          >
                            <div className="flex items-center gap-2 font-semibold">
                              <CheckCircle2 size={14} className={isPosted ? 'text-emerald-300' : 'text-slate-600'} />
                              {meta.label}
                            </div>
                            <div className="mt-1 text-[11px]">
                              {isPosted ? `Gia postato: ${formatPostedAt(socialPost.posted_at)}` : 'Non ancora postato'}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                      <button
                        onClick={() => handlePublish('youtube')}
                        disabled={publishing.youtube || publishing.all}
                        className="flex flex-col items-center justify-center gap-2 p-3 bg-rose-950/30 hover:bg-rose-900/40 text-rose-200 hover:text-white border border-rose-500/20 hover:border-rose-500/40 rounded-xl text-xs font-bold transition disabled:opacity-50"
                      >
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M23.498 6.163a3.003 3.003 0 0 0-2.11-2.11C19.517 3.545 12 3.545 12 3.545s-7.517 0-9.388.508a3.003 3.003 0 0 0-2.11 2.11C0 8.033 0 12 0 12s0 3.967.502 5.837a3.003 3.003 0 0 0 2.11 2.11c1.871.508 9.388.508 9.388.508s7.517 0 9.388-.508a3.003 3.003 0 0 0 2.11-2.11C24 15.967 24 12 24 12s0-3.967-.502-5.837zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                        {publishing.youtube ? 'Invio...' : 'YouTube Shorts'}
                      </button>
                      <button
                        onClick={() => handlePublish('instagram')}
                        disabled={publishing.instagram || publishing.all}
                        className="flex flex-col items-center justify-center gap-2 p-3 bg-pink-950/30 hover:bg-pink-900/40 text-pink-200 hover:text-white border border-pink-500/20 hover:border-pink-500/40 rounded-xl text-xs font-bold transition disabled:opacity-50"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>
                        {publishing.instagram ? 'Invio...' : 'Instagram Reels'}
                      </button>
                      <button
                        onClick={() => handlePublish('tiktok')}
                        disabled={publishing.tiktok || publishing.all}
                        className="flex flex-col items-center justify-center gap-2 p-3 bg-cyan-950/30 hover:bg-cyan-900/40 text-cyan-200 hover:text-white border border-cyan-500/20 hover:border-cyan-500/40 rounded-xl text-xs font-bold transition disabled:opacity-50"
                      >
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.17-2.86-.74-3.99-1.72-.08-.07-.17-.17-.25-.26V14c0 3.31-2.69 6-6 6s-6-2.69-6-6 2.69-6 6-6c.39 0 .77.04 1.14.11V4.28c-1.32-.19-2.67-.12-3.95.22C3.99 5.21 2 7.89 2 11c0 4.42 3.58 8 8 8s8-3.58 8-8V0c-1.49.88-3.21 1.39-4.96 1.41l-.51-1.39z"/></svg>
                        {publishing.tiktok ? 'Invio...' : 'TikTok'}
                      </button>
                      <button
                        onClick={() => handlePublish('all')}
                        disabled={publishing.all || publishing.youtube || publishing.instagram || publishing.tiktok}
                        className="flex flex-col items-center justify-center gap-2 p-3 bg-amber-950/40 hover:bg-amber-900/50 text-amber-100 hover:text-white border border-amber-400/25 hover:border-amber-300/45 rounded-xl text-xs font-bold transition disabled:opacity-50"
                      >
                        <Share2 className="w-5 h-5" />
                        {publishing.all ? 'Invio globale...' : 'Tutti i social'}
                      </button>
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <span className="text-sm font-semibold text-slate-200">Caption pronta per Reel o TikTok</span>
                      <button
                        onClick={() => copyText(playingShort.caption, 'Caption')}
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
                      >
                        <Copy size={14} />
                        Copia caption
                      </button>
                    </div>
                    <textarea
                      readOnly
                      value={playingShort.caption || ''}
                      placeholder="Genera un nuovo short per ottenere una caption pronta da copiare."
                      className="min-h-[220px] w-full resize-none rounded-lg border border-slate-800 bg-slate-900/80 p-3 text-sm leading-6 text-slate-100 outline-none"
                    />
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <span className="text-sm font-semibold text-slate-200">5 hashtag pertinenti</span>
                      <button
                        onClick={() => copyText(playingShort.hashtags_text, 'Hashtag')}
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white"
                      >
                        <Copy size={14} />
                        Copia hashtag
                      </button>
                    </div>
                    <textarea
                      readOnly
                      value={playingShort.hashtags_text || ''}
                      placeholder="Per gli short storici i 5 hashtag non erano ancora salvati."
                      className="min-h-[96px] w-full resize-none rounded-lg border border-slate-800 bg-slate-900/80 p-3 text-sm leading-6 text-slate-100 outline-none"
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(playingShort.hashtags || []).map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-200"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
