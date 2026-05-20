# ADR 0022: Regia AI Centrale (DirectorAgent) e Gestione Edizioni Straordinarie (SPECIAL_BROADCAST)

## Stato
Approvato

## Contesto
Nell'ecosistema NewsicaTV, la regia oraria (`director.py`) era gestita mediante un loop rigido e scarsamente flessibile. Con l'introduzione di rubriche articolate in più parti, Podcast a due voci e brani musicali alternati, la complessità decisionale ha superato la capacità di una logica lineare e cablata. Inoltre, la gestione di eventi eccezionali (news ad altissima gravità) richiedeva un'Edizione Straordinaria automatica capace di interrompere il palinsesto ordinario in modo sobrio ed elegante, scrivendo file di stato centralizzati atomici ed offrendo un ripristino post-interruzione altrettanto intelligente (Regola del 40% di durata residua).

## Decisione
Si decide di introdurre:

1. **`DirectorAgent` come Regia AI Centrale**:
   - Una classe che gestisce la progressione a segmenti (`intro`, `body`, `music_stacco`, `closing`, `music_rotation_until_deadline`) vincolata dal palinsesto (*"Il palinsesto decide cosa va in onda, il DirectorAgent decide come"*).
   - Gestione centralizzata del sequenziamento di rubriche standard e podcast in parti multiple intercalate da musica.
   - Integrazione completa con la memoria editoriale locale (`editorial-memory.json`) per evitare la ripetizione ravvicinata di canzoni, notizie o introduzioni dello speaker.

2. **Scoring e Valutazione Gravità Notizie (`GravityAssessor`)**:
   - Un sistema ibrido a due livelli per ridurre al minimo la latenza e i costi computazionali.
   - Livello 1: Euristica veloce a regex locali che calcola un punteggio iniziale (0-100).
   - Livello 2: Se lo score euristico è $\ge 50$, viene invocata la validazione raffinata di Ollama locale (`gemma3:12b`) tramite prompt strutturato JSON.
   - Una gravità $\ge 90$ avvia automaticamente lo stato di **Trasmissione Straordinaria** (`SPECIAL_BROADCAST`).

3. **`SPECIAL_BROADCAST` (Edizione Straordinaria)**:
   - Sospensione del palinsesto e attivazione di un flusso continuo di bollettini urgenti intervallati da sottofondi tesi e solenni.
   - Attivazione automatica dell'accento grafico per la visualizzazione dell'overlay rosso breaking (`accent_breaking.txt`) mappato via `runtime_state.py`.
   - Modifica immediata dello stato ticker a `"🚨 EDIZIONE STRAORDINARIA"` allineando overlay e audio.

4. **Regola del 40% per il Ripristino**:
   - Quando viene revocata la trasmissione straordinaria, `DirectorAgent` calcola il tempo residuo dello slot interrotto.
   - Se manca almeno il 40% della durata totale dello slot, la rubrica viene ripresa in modo conversazionale partendo con musica.
   - Se manca meno del 40%, lo slot viene skippato passando direttamente alla programmazione successiva per rispetto della programmazione e dello spettatore.

5. **Scrittura Atomica e Stato Centralizzato**:
   - Tutti i passaggi di stato e gli overlay (`current_program.txt`, `next_program.txt`, accenti) sono scritti in modo atomico utilizzando file temporanei `.tmp` e sostituzioni atomiche del sistema operativo (`os.replace`) per evitare letture corrotte da parte degli agenti ticker, dashboard ed overlay FFmpeg.

## Conseguenze
- **Modularità eccezionale**: `director.py` è stato notevolmente semplificato, delegando tutta la logica decisionale e di stato al modulo `newsica.broadcast` e `newsica.editorial`.
- **User Experience premium**: Il canale si comporta come una vera web-TV professionale, alternando in modo naturale i contributi, gestendo le urgenze in tempo reale e ripristinando in modo fluido e logico.
- **Zero Costi**: L'intero flusso, inclusa l'elaborazione del testo e la sintesi vocale, rimane locale ed offline, rispettando l'infrastruttura esistente.
