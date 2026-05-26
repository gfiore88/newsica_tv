import React from 'react'
import { useOutletContext } from 'react-router-dom'
import { AlertTriangle, SkipForward, RefreshCw, Bell, MonitorPlay, Volume2, ShieldAlert } from 'lucide-react'

export default function LiveMonitor() {
  const { state } = useOutletContext()
  const [chatStatus, setChatStatus] = React.useState({ video_id: '', is_running: false })

  React.useEffect(() => {
    let cancelled = false

    const loadChatStatus = async () => {
      try {
        const response = await fetch('/api/chat/status')
        if (!response.ok) {
          return
        }
        const data = await response.json()
        if (!cancelled) {
          setChatStatus({
            video_id: data.video_id || '',
            is_running: Boolean(data.is_running),
          })
        }
      } catch (err) {
        console.error('Errore caricamento chat status:', err)
      }
    }

    loadChatStatus()
    const intervalId = window.setInterval(loadChatStatus, 15000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  const sendCommandSafe = async (cmd, msg) => {
    if (confirm(msg)) {
      try {
        await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: cmd })
        })
      } catch (err) {
        console.error("Errore comando:", err)
      }
    }
  }

  const triggerChime = async () => {
    try {
      await fetch('/api/chime', { method: 'POST' })
    } catch (err) {}
  }

  const activateLiveAudio = () => {
    const targetUrl = chatStatus.video_id
      ? `https://www.youtube.com/watch?v=${chatStatus.video_id}`
      : 'https://www.youtube.com/@newsicaTV/live'
    window.open(targetUrl, '_blank')
  }

  const embedUrl = chatStatus.video_id
    ? `https://www.youtube.com/embed/${chatStatus.video_id}?autoplay=1&mute=1&enablejsapi=1`
    : null

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
      
      {/* Colonna Principale (Video + Controlli) */}
      <div className="lg:col-span-2 space-y-6 flex flex-col h-full">
        
        {/* Player Video */}
        <div className="glass rounded-xl p-5 shadow-xl border border-slate-800">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm uppercase tracking-widest text-slate-300 font-bold flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
              </span>
              Live Monitor
            </h2>
            {state.breaking_news_available ? (
              <span className="animate-pulse px-3 py-1 rounded bg-red-600 text-white font-black uppercase tracking-widest text-[10px] shadow-[0_0_15px_rgba(239,68,68,0.8)] border border-red-400">🚨 BREAKING NEWS ATTIVA</span>
            ) : (
              <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 font-bold uppercase tracking-wider">DIRECT RTMP</span>
            )}
          </div>
          
          <div className="relative w-full aspect-video rounded-lg overflow-hidden border border-slate-700 bg-black shadow-inner">
            {embedUrl ? (
              <iframe
                className="absolute inset-0 w-full h-full"
                src={embedUrl}
                frameBorder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-slate-400">
                Nessun video live rilevato al momento dal sistema di discovery YouTube.
              </div>
            )}
          </div>
          
          <div className="mt-4 flex items-center justify-between">
             <span className="text-xs text-slate-400">
               Canale: <strong className="text-slate-200">@newsicaTV</strong>
               {chatStatus.video_id ? ` • Video ID: ${chatStatus.video_id}` : ''}
             </span>
             <button onClick={activateLiveAudio} className="flex items-center gap-2 text-xs font-bold text-red-400 hover:text-red-300 bg-red-950/30 px-3 py-1.5 rounded-lg border border-red-900/50 transition">
               <MonitorPlay size={14} /> Apri su YouTube
             </button>
          </div>
        </div>

        {/* Controlli Regia Rapidi */}
        <div className="glass rounded-xl p-5 shadow-xl border border-slate-800">
           <h2 className="text-sm uppercase tracking-widest text-slate-300 font-bold mb-4">Controlli di Regia Rapidi</h2>
           
           <div className="grid grid-cols-2 gap-3 mb-3">
             <button onClick={() => sendCommandSafe('FORCE_NEXT', 'Saltare il blocco attuale?')} className="bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3 px-4 rounded-lg flex items-center justify-center gap-2 border border-slate-700 transition">
               <SkipForward size={18} /> Salta Blocco
             </button>
             <button onClick={() => sendCommandSafe('REGEN_SCHEDULE', 'Rigenerare palinsesto?')} className="bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3 px-4 rounded-lg flex items-center justify-center gap-2 border border-slate-700 transition">
               <RefreshCw size={18} /> Rigenera Palinsesto
             </button>
           </div>
           
           <div className="grid grid-cols-2 gap-3 mb-3">
             <button onClick={() => sendCommandSafe('TRIGGER_BREAKING_NEWS', 'ATTENZIONE: Interrompere per Breaking News?')} className="bg-red-600/90 hover:bg-red-500 text-white font-black py-4 px-4 rounded-lg flex items-center justify-center gap-2 border border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.3)] transition">
               <AlertTriangle size={20} /> BREAKING NEWS
             </button>
             <button onClick={triggerChime} className="bg-amber-600/90 hover:bg-amber-500 text-white font-black py-4 px-4 rounded-lg flex items-center justify-center gap-2 border border-amber-500 shadow-[0_0_15px_rgba(251,191,36,0.3)] transition">
               <Bell size={20} /> Segnale Orario
             </button>
           </div>

           <div className="grid grid-cols-2 gap-3">
             <button onClick={() => sendCommandSafe('TRIGGER_SPECIAL_BROADCAST_TEST', 'Simulare edizione straordinaria?')} className="bg-rose-800 hover:bg-rose-700 text-white font-bold py-2 px-3 rounded-lg text-xs flex items-center justify-center gap-2 border border-rose-600 transition">
               <ShieldAlert size={14} /> ED. STRAORDINARIA TEST
             </button>
             <button onClick={() => sendCommandSafe('REVOKE_SPECIAL_BROADCAST', 'Ripristinare palinsesto normale?')} className="bg-emerald-800 hover:bg-emerald-700 text-white font-bold py-2 px-3 rounded-lg text-xs flex items-center justify-center gap-2 border border-emerald-600 transition">
               Ripristina Palinsesto
             </button>
           </div>
        </div>

      </div>

      {/* Colonna Laterale (Stato) */}
      <div className="space-y-6">
        
        {/* In Onda Ora */}
        <div className="glass rounded-xl p-6 shadow-xl border border-slate-800 flex flex-col h-[280px]">
           <h2 className="text-xs uppercase tracking-widest text-slate-400 font-bold mb-4">In Onda Ora</h2>
           
           <div className="flex-1 flex flex-col justify-center">
             <div className="text-2xl font-black text-white mb-2 leading-tight">{state.current_title || 'Caricamento...'}</div>
             <div className="text-sm font-semibold text-purple-400 bg-purple-950/30 px-3 py-1.5 rounded-lg border border-purple-900/50 inline-block w-max">
               {state.current_segment || '--'}
             </div>
           </div>

           <div className="mt-auto pt-4 border-t border-slate-800">
             <h3 className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-2">Prossimo Blocco</h3>
             <div className="flex items-center justify-between bg-slate-950/50 p-3 rounded-lg border border-slate-800">
                <span className="text-sm font-bold text-slate-300 truncate">{state.next_block || '--'}</span>
                <span className="text-xs font-mono bg-slate-800 px-2 py-1 rounded text-slate-400">{state.next_start || '--:--'}</span>
             </div>
           </div>
        </div>

      </div>
    </div>
  )
}
