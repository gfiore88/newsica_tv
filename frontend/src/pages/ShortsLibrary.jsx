import React, { useEffect, useState } from 'react'
import { Video, Calendar, Download, Play, RefreshCw, Copy } from 'lucide-react'
import { useDialog } from '../context/DialogContext'

export default function ShortsLibrary() {
  const [shorts, setShorts] = useState([])
  const [loading, setLoading] = useState(true)
  const [playingShort, setPlayingShort] = useState(null)
  const [shortsLoading, setShortsLoading] = useState(false)
  const { showAlert } = useDialog()

  const fetchShorts = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/shorts_library')
      if (res.ok) {
        const data = await res.json()
        setShorts(data.shorts || [])
      }
    } catch (e) {
      console.error("Errore caricamento libreria shorts:", e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchShorts()
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

  const generateShort = async () => {
    setShortsLoading(true)
    try {
      const res = await fetch('/api/generate_short', { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        await showAlert(`Short generato con successo.`, 'Video Pronto')
        setPlayingShort({
          url: data.video_url,
          news_title: data.news_title,
          script: data.script,
          caption: data.caption,
          hashtags: data.hashtags || [],
          hashtags_text: (data.hashtags || []).join(' '),
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
            onClick={fetchShorts}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm border border-slate-700 transition disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Aggiorna
          </button>
          <button
            onClick={generateShort}
            disabled={shortsLoading}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-bold shadow-[0_0_15px_rgba(79,70,229,0.3)] transition disabled:opacity-50"
          >
            <Play size={16} />
            {shortsLoading ? 'Generazione...' : 'Genera Nuovo Short'}
          </button>
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
            Usa il pulsante "Genera Nuovo Short" in alto per creare il tuo primo video verticale basato sulle notizie del giorno.
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
                      <div className="text-[10px] text-slate-400 truncate pr-2" title={short.filename}>
                        {short.filename.replace('.mp4', '').replace('short_', '')}
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
