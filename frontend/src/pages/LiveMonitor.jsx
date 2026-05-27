import React, { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useDialog } from '../context/DialogContext'
import { AlertTriangle, SkipForward, RefreshCw, Bell, MonitorPlay, Volume2, ShieldAlert } from 'lucide-react'

export default function LiveMonitor() {
  const { state } = useOutletContext()
  const { showConfirm } = useDialog()
  const [loadingAction, setLoadingAction] = useState(null)

  const sendCommandSafe = async (cmd, msg) => {
    if (await showConfirm(msg, 'Conferma Comando')) {
      setLoadingAction(cmd)
      try {
        await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: cmd })
        })
      } catch (err) {
        console.error("Errore comando:", err)
      }
      setLoadingAction(null)
    }
  }

  const triggerChime = async () => {
    try {
      await fetch('/api/chime', { method: 'POST' })
    } catch (err) {}
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
      
      {/* Colonna Principale (Video + Controlli) */}
      <div className="lg:col-span-2 space-y-6 flex flex-col h-full">
        
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
