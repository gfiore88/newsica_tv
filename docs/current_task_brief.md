# 🔎 Task Brief: Regia AI Centrale e Stato di Trasmissione (MVP 3)

## Obiettivo
Trasformare l'attuale script `director.py` (che esegue un banale loop circolare su array statico) in un vero e proprio `DirectorAgent`. Il nuovo motore dovrà gestire la messa in onda in maniera strutturata ed esportare costantemente il proprio stato in un file JSON (`runtime/on-air-state.json`). Questa è la base per permettere ad altri agenti futuri (es. Ticker, Breaking News) di interagire con la diretta.

## Vincoli Tecnici
- **Tutto Locale**: Nessuna chiamata ad API esterne a pagamento.
- **Tracciabilità Realtime**: Il file `runtime/on-air-state.json` deve essere aggiornato con coerenza, mostrando cosa *sta effettivamente andando in onda* (o venendo inviato alla pipe FFmpeg).
- **Continuità**: Mantenere il meccanismo di fallback PCM a silenzio e la stabilità dello stream FFmpeg verso YouTube.

## Piano di Lavoro
1. **Fase 4 (Python Engineer)**: 
   - Refactoring architetturale di `src/director.py`.
   - Creazione della cartella `runtime/` e implementazione del salvataggio continuo in `runtime/on-air-state.json`.
   - Gestione della transizione: l'aggiornamento dello stato JSON deve essere mappato al momento in cui l'audio inizia a fluire verso FFmpeg, non quando viene generato (perché la generazione è in anticipo).
   - Abbozzare una struttura di "palinsesto" minima che sostituisca la lista circolare hardcoded, per prepararsi al task del palinsesto dinamico.
2. **Fase 6 (System Admin)**:
   - Configurare la gestione della directory `runtime/` (gitignore, creazione al boot, pulizia) senza conflitti.
3. **Fase 7 (Code Reviewer)**:
   - Verifica di thread-safety se più thread leggono/scrivono lo stato.
   - Conferma che il refactoring non introduca blocchi (`deadlocks`) nella pipe audio.

## Rischi Potenziali
- **Disallineamento Stato/Stream**: Dato che FFmpeg e la queue consumano byte progressivamente, determinare il momento "esatto" in cui un nuovo blocco news inizia può essere complicato in Python raw. Possibile soluzione: accodare nella queue non solo bytes PCM, ma oggetti misti (metadati + generatore bytes) oppure scrivere lo stato prima di iniziare il ciclo di `fifo.write` del nuovo file.
- **Preparazione Interruzioni**: L'architettura deve essere fatta a oggetti o comunque modulare per facilitare, nel prossimo step, lo "svuotamento" della coda in caso di un alert di breaking news.
