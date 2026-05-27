import React, { useEffect, useState } from 'react'
import { Video, Calendar, Download, Play, RefreshCw } from 'lucide-react'
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

  const generateShort = async () => {
    setShortsLoading(true)
    try {
      const res = await fetch('/api/generate_short', { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        await showAlert(`Short generato con successo.`, 'Video Pronto')
        const filename = data.output.split('/').pop()
        setPlayingShort({ url: `/shorts/${filename}` })
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
                      {/* Simula un placeholder video */}
                      <div className="absolute inset-0 bg-gradient-to-b from-indigo-900/20 to-black flex items-center justify-center">
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
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/90 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-[400px]">
            <button 
              onClick={(e) => { e.preventDefault(); setPlayingShort(null); }}
              className="absolute -top-10 right-0 text-white hover:text-slate-300 transition"
            >
              Chiudi (Esc)
            </button>
            <video 
              src={playingShort.url} 
              controls 
              autoPlay 
              playsInline
              className="w-full rounded-lg shadow-2xl bg-black aspect-[9/16]"
            />
          </div>
        </div>
      )}
    </div>
  )
}
