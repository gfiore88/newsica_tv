import { useState, useEffect } from 'react'
import { Database as DbIcon, RefreshCw } from 'lucide-react'

export default function Database() {
  const [activeTab, setActiveTab] = useState('history')
  const [data, setData] = useState({ history: [], memory: [], assets: [], rotation: { recent_tracks: [], block_events: [], configured_window: 0, tracked_count: 0 } })
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [histRes, memRes, assetsRes, rotationRes] = await Promise.all([
        fetch('/api/db/history'),
        fetch('/api/db/memory'),
        fetch('/api/db/assets'),
        fetch('/api/db/music-rotation')
      ])
      const [hist, mem, assets, rotation] = await Promise.all([
        histRes.json(), memRes.json(), assetsRes.json(), rotationRes.json()
      ])
      setData({
        history: hist.data || [],
        memory: mem.data || [],
        assets: assets.data || [],
        rotation: rotation.data || { recent_tracks: [], block_events: [], configured_window: 0, tracked_count: 0 }
      })
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => {
    Promise.resolve().then(fetchData)
    const int = setInterval(fetchData, 10000)
    return () => clearInterval(int)
  }, [])

  const formatDateTime = (iso) => {
    if (!iso) return '--'
    return new Date(iso).toLocaleString()
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
             <button onClick={() => setActiveTab('rotation')} className={`px-4 py-2 text-sm font-bold uppercase tracking-wider rounded-lg transition ${activeTab === 'rotation' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>Rotazione Musica</button>
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
                  <td className="px-6 py-3 whitespace-nowrap">{formatDateTime(row.started_at)}</td>
                  <td className="px-6 py-3">
                    <span className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-[10px] font-bold text-slate-300 uppercase">{row.event_type}</span>
                  </td>
                  <td className="px-6 py-3">
                    <div className="font-semibold text-white">{row.display_title || row.title}</div>
                    <div className="text-[11px] text-slate-500 mt-1">{row.display_detail || row.segment || row.block_type || '--'}</div>
                  </td>
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
                <th className="px-6 py-4 font-bold text-slate-400 w-1/5">Tipo Memoria</th>
                <th className="px-6 py-4 font-bold text-slate-400 w-2/5">Sintesi</th>
                <th className="px-6 py-4 font-bold text-slate-400 w-2/5">Valore</th>
                <th className="px-6 py-4 font-bold text-slate-400 w-1/5">Creazione</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data.memory.map((row, i) => (
                <tr key={i} className="hover:bg-slate-900/50 transition">
                  <td className="px-6 py-3">
                    <span className="px-2.5 py-1 rounded-full bg-purple-900/30 border border-purple-500/30 text-[10px] font-bold text-purple-300 uppercase">{row.memory_type}</span>
                  </td>
                  <td className="px-6 py-3 text-sm text-slate-300 align-top">{row.value_summary || '--'}</td>
                  <td className="px-6 py-3 align-top">
                    {row.value_is_json ? (
                      <pre className="max-w-[520px] overflow-auto rounded-lg border border-slate-800 bg-slate-950/80 p-3 text-[11px] leading-5 text-slate-300 whitespace-pre-wrap">
                        {row.value_pretty}
                      </pre>
                    ) : (
                      <div className="max-w-[520px] whitespace-pre-wrap text-sm font-semibold text-white">
                        {row.value}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-3 whitespace-nowrap text-slate-400 align-top">{formatDateTime(row.created_at)}</td>
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
                    <td className="px-6 py-3 text-slate-400">{formatDateTime(row.updated_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {activeTab === 'rotation' && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 p-6">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-800 bg-slate-900">
                <div className="text-xs uppercase tracking-widest font-bold text-sky-400">Finestra Recente</div>
                <div className="text-sm text-slate-400 mt-1">
                  Limite configurato: {data.rotation.configured_window || 0} brani. Attualmente tracciati: {data.rotation.tracked_count || 0}.
                </div>
              </div>
              <div className="divide-y divide-slate-800/60">
                {data.rotation.recent_tracks.length === 0 ? (
                  <div className="px-5 py-8 text-sm text-slate-500">Nessuna history runtime disponibile.</div>
                ) : (
                  data.rotation.recent_tracks.map((track, i) => (
                    <div key={`${track.path}-${i}`} className="px-5 py-4">
                      <div className="text-sm font-semibold text-white">{track.display_title || track.filename}</div>
                      <div className="text-[11px] text-slate-500 mt-1 font-mono break-all">{track.filename}</div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-800 bg-slate-900">
                <div className="text-xs uppercase tracking-widest font-bold text-amber-400">Candidati Scartati</div>
                <div className="text-sm text-slate-400 mt-1">
                  Ultimi eventi in cui la rotazione ha escluso brani recenti prima di scegliere un’alternativa.
                </div>
              </div>
              <div className="divide-y divide-slate-800/60">
                {data.rotation.block_events.length === 0 ? (
                  <div className="px-5 py-8 text-sm text-slate-500">Ancora nessun candidato escluso dalla finestra recente.</div>
                ) : (
                  data.rotation.block_events.map((event, i) => (
                    <div key={`${event.timestamp}-${i}`} className="px-5 py-4">
                      <div className="flex items-center justify-between gap-4">
                        <div className="text-sm font-semibold text-white">{formatDateTime(event.timestamp)}</div>
                        <div className="text-[11px] text-slate-500">
                          {event.blocked_count} esclusi su {event.candidate_count} candidati
                        </div>
                      </div>
                      <div className="text-[11px] text-amber-300 mt-2 uppercase tracking-wider font-bold">
                        Motivo: {event.reason} | finestra={event.recent_window}
                      </div>
                      <div className="mt-3 space-y-2">
                        {event.blocked_tracks.map((track, idx) => (
                          <div key={`${track.path}-${idx}`} className="rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2">
                            <div className="text-sm text-slate-200">{track.display_title || track.filename}</div>
                            <div className="text-[11px] text-slate-500 mt-1 font-mono break-all">{track.filename}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
