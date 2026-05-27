import React from 'react'
import { useOutletContext } from 'react-router-dom'
import { Calendar as CalendarIcon } from 'lucide-react'
import { useDialog } from '../context/DialogContext'

export default function Schedule() {
  const { state } = useOutletContext()
  const { showConfirm, showAlert } = useDialog()

  const schedule = state.schedule || []

  const normalizeTitle = (title) => {
    if (!title) return ''
    return title
      .replace(/\s+-\s+Parte\s+\d+$/i, '')
      .replace(/\s+-\s+Completo$/i, '')
      .trim()
      .toLowerCase()
  }

  const normalizedCurrentTitle = normalizeTitle(state.current_title)
  const normalizedTitleCounts = schedule.reduce((acc, item) => {
    const key = normalizeTitle(item.title)
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})

  const badges = {
    'music_only': { label: '🎵 Musica', bg: 'bg-indigo-950/50 text-indigo-300 border-indigo-800/50' },
    'news': { label: '📰 News', bg: 'bg-emerald-950/50 text-emerald-300 border-emerald-800/50' },
    'sport': { label: '⚽ Sport', bg: 'bg-amber-950/50 text-amber-300 border-amber-800/50' },
    'wellness': { label: '🧘 Benessere', bg: 'bg-rose-950/50 text-rose-300 border-rose-800/50' },
    'meteo': { label: '☀️ Meteo', bg: 'bg-sky-950/50 text-sky-300 border-sky-800/50' }
  }

  const forcePlay = async (index, title) => {
    if (await showConfirm(`Forzare la messa in onda immediata del blocco "${title}"?`, 'Messa in Onda Forzata')) {
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: `FORCE_INDEX_${index}` })
        })
        if (res.ok) {
          await showAlert('Comando accettato: il blocco andrà in onda tra poco.', 'Comando Inviato')
        } else {
          await showAlert('Errore durante l\'invio del comando.', 'Errore')
        }
      } catch (e) {
        await showAlert('Errore di rete.', 'Errore')
        console.error(e)
      }
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-6">
         <h1 className="text-2xl font-black text-white flex items-center gap-3">
           <CalendarIcon className="text-purple-500" /> Palinsesto di Oggi
         </h1>
         <span className="text-sm text-slate-400 font-medium">Clicca su un blocco per forzarne la messa in onda</span>
      </div>

      {schedule.length === 0 ? (
        <div className="glass flex-1 flex items-center justify-center rounded-xl border border-slate-800">
          <p className="text-slate-500 font-bold text-lg">Nessun palinsesto disponibile</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6 gap-4 pb-6">
          {schedule.map((item, idx) => {
            const normalizedItemTitle = normalizeTitle(item.title)
            const hasUniqueTitleMatch =
              normalizedCurrentTitle &&
              normalizedCurrentTitle === normalizedItemTitle &&
              normalizedTitleCounts[normalizedItemTitle] === 1
            const isScheduledSlotActive = state.scheduled_slot && item.time === state.scheduled_slot
            const isActive = Boolean(isScheduledSlotActive || (!state.scheduled_slot && hasUniqueTitleMatch))
            
            const badge = badges[item.type] || { label: '📦 Altro', bg: 'bg-slate-900 text-slate-300 border-slate-700' }

            return (
              <div 
                key={idx}
                onClick={() => !isActive && forcePlay(item.index, item.title)}
                className={`relative group p-5 rounded-xl border flex flex-col h-40 ${
                  isActive 
                    ? 'ring-2 ring-purple-500 bg-gradient-to-br from-slate-800 to-indigo-950 border-purple-500 shadow-xl shadow-purple-500/20 scale-[1.02]' 
                    : 'bg-slate-900/50 hover:bg-slate-800 border-slate-700 hover:border-slate-500 transition-all cursor-pointer'
                }`}
              >
                {isActive && (
                  <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-4 w-4 bg-red-500"></span>
                  </span>
                )}
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-sm font-black tracking-wider ${isActive ? 'text-purple-400' : 'text-slate-400'}`}>
                    {item.time}
                  </span>
                  {isActive && (
                    <span className="text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30">
                      IN ONDA
                    </span>
                  )}
                </div>
                <div className={`text-base font-bold leading-tight line-clamp-2 ${isActive ? 'text-white' : 'text-slate-200 group-hover:text-white'}`}>
                  {item.title}
                </div>
                <div className="mt-auto flex items-center justify-between">
                  <span className={`text-[10px] px-2.5 py-1 rounded-full font-bold border ${badge.bg}`}>
                    {badge.label}
                  </span>
                  {!isActive && (
                    <span className="text-xs text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity font-bold">
                      Forza 🚀
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
