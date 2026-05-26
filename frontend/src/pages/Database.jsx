import React, { useState, useEffect } from 'react'
import { Database as DbIcon, RefreshCw } from 'lucide-react'

export default function Database() {
  const [activeTab, setActiveTab] = useState('history')
  const [data, setData] = useState({ history: [], memory: [], assets: [] })
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [histRes, memRes, assetsRes] = await Promise.all([
        fetch('/api/db/history'),
        fetch('/api/db/memory'),
        fetch('/api/db/assets')
      ])
      const [hist, mem, assets] = await Promise.all([
        histRes.json(), memRes.json(), assetsRes.json()
      ])
      setData({
        history: hist.data || [],
        memory: mem.data || [],
        assets: assets.data || []
      })
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchData()
    const int = setInterval(fetchData, 10000)
    return () => clearInterval(int)
  }, [])

  const formatTime = (iso) => {
    if (!iso) return '--:--'
    return new Date(iso).toLocaleTimeString()
  }

  return (
    <div className="flex flex-col h-full bg-slate-950/50 rounded-xl border border-slate-800 shadow-xl overflow-hidden">
      {/* Header & Tabs */}
      <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
         <div className="flex items-center gap-6">
           <h1 className="text-lg font-black text-white flex items-center gap-2">
             <DbIcon className="text-indigo-500" size={24} /> Registro Storico & Audit
           </h1>
           <div className="flex gap-2">
             <button onClick={() => setActiveTab('history')} className={`px-4 py-2 text-sm font-bold uppercase tracking-wider rounded-lg transition ${activeTab === 'history' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>Storico Trasmissioni</button>
             <button onClick={() => setActiveTab('memory')} className={`px-4 py-2 text-sm font-bold uppercase tracking-wider rounded-lg transition ${activeTab === 'memory' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>Memoria Editoriale</button>
             <button onClick={() => setActiveTab('assets')} className={`px-4 py-2 text-sm font-bold uppercase tracking-wider rounded-lg transition ${activeTab === 'assets' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>Stato Asset</button>
           </div>
         </div>
         <button onClick={fetchData} className={`text-slate-400 hover:text-white p-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition ${loading ? 'animate-spin' : ''}`}>
           <RefreshCw size={18} />
         </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto bg-slate-950">
        
        {activeTab === 'history' && (
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900 sticky top-0 border-b border-slate-800 shadow-md">
              <tr>
                <th className="px-6 py-4 font-bold text-slate-400">Inizio</th>
                <th className="px-6 py-4 font-bold text-slate-400">Tipo</th>
                <th className="px-6 py-4 font-bold text-slate-400">Titolo / Segmento</th>
                <th className="px-6 py-4 font-bold text-slate-400">Asset Path</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data.history.map((row, i) => (
                <tr key={i} className="hover:bg-slate-900/50 transition">
                  <td className="px-6 py-3 whitespace-nowrap">{formatTime(row.started_at)}</td>
                  <td className="px-6 py-3">
                    <span className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-[10px] font-bold text-slate-300 uppercase">{row.event_type}</span>
                  </td>
                  <td className="px-6 py-3 font-semibold text-white">{row.title}</td>
                  <td className="px-6 py-3 text-slate-500 font-mono text-xs">{row.asset_path ? row.asset_path.split('/').pop() : '--'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {activeTab === 'memory' && (
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900 sticky top-0 border-b border-slate-800 shadow-md">
              <tr>
                <th className="px-6 py-4 font-bold text-slate-400 w-1/4">Tipo Memoria</th>
                <th className="px-6 py-4 font-bold text-slate-400 w-1/2">Valore</th>
                <th className="px-6 py-4 font-bold text-slate-400 w-1/4">Creazione</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data.memory.map((row, i) => (
                <tr key={i} className="hover:bg-slate-900/50 transition">
                  <td className="px-6 py-3">
                    <span className="px-2.5 py-1 rounded-full bg-purple-900/30 border border-purple-500/30 text-[10px] font-bold text-purple-300 uppercase">{row.memory_type}</span>
                  </td>
                  <td className="px-6 py-3 font-semibold text-white">{row.value}</td>
                  <td className="px-6 py-3 whitespace-nowrap text-slate-400">{formatTime(row.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {activeTab === 'assets' && (
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900 sticky top-0 border-b border-slate-800 shadow-md">
              <tr>
                <th className="px-6 py-4 font-bold text-slate-400">Slot</th>
                <th className="px-6 py-4 font-bold text-slate-400">Character / Titolo</th>
                <th className="px-6 py-4 font-bold text-slate-400">Stato</th>
                <th className="px-6 py-4 font-bold text-slate-400">Aggiornato</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data.assets.map((row, i) => {
                let statusColor = 'text-slate-400 bg-slate-800 border-slate-600'
                if (row.status === 'ready') statusColor = 'text-green-400 bg-green-900/30 border-green-500/50'
                if (row.status === 'preparing') statusColor = 'text-amber-400 bg-amber-900/30 border-amber-500/50 animate-pulse'
                if (row.status === 'failed') statusColor = 'text-red-400 bg-red-900/30 border-red-500/50'
                if (row.status === 'played') statusColor = 'text-blue-400 bg-blue-900/30 border-blue-500/50'
                
                return (
                  <tr key={i} className="hover:bg-slate-900/50 transition">
                    <td className="px-6 py-3 font-mono text-slate-400">{row.slot_time}</td>
                    <td className="px-6 py-3">
                      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{row.character}</div>
                      <div className="font-semibold text-white mt-0.5">{row.title}</div>
                    </td>
                    <td className="px-6 py-3">
                      <span className={`px-2.5 py-1 rounded-full border text-[10px] font-bold uppercase ${statusColor}`}>{row.status}</span>
                      {row.error && <div className="text-[10px] text-red-400 mt-2 font-mono">{row.error}</div>}
                    </td>
                    <td className="px-6 py-3 text-slate-400">{formatTime(row.updated_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

      </div>
    </div>
  )
}
