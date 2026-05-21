# 0027. Separazione Messa in Onda e Generazione (Pre-Produzione Multi-Agente)

## Contesto
Fino a questo momento, la generazione dei contenuti editoriali (Ollama + TTS) veniva innescata in modo sincrono dal `DirectorAgent` non appena il palinsesto richiedeva la messa in onda di uno slot, bloccando l'event loop della regia tramite l'azione `WAIT_OR_GENERATE`.
In una WebTV 24/7 in cui l'LLM e il TTS possono richiedere minuti (specialmente su hardware condiviso), questo causava starvation dei buffer di FFmpeg, vuoti nello stream e violava il principio della continuità di trasmissione. 

## Decisione
Si è deciso di attuare due refactoring architetturali radicali:

1. **Pre-Produzione e Content Buffer (Bufferizzazione Asincrona)**:
   La regia (On-Air Loop) non attende più la generazione. Può mandare in onda solo asset audio già validati e posizionati nella directory `runtime/assets/ready/[FASCIA_ORARIA]`. Se il file non è pronto all'ora X, il DirectorAgent attiva un fallback editoriale musicale (`music_rotation_until_deadline`), proteggendo lo stream.

2. **Architettura Multi-Agente Python (Separation of Concerns)**:
   È stato rimosso l'uso di script monolitici richiamati via `subprocess.run()`. Ora il sistema utilizza vere e proprie classi Python specializzate coordinate da un loop indipendente (`PreparationAgent`):
   - **`ContentStrategistAgent`**: Raccoglie fonti (scraping) e compila il prompt.
   - **`AIIntegratorAgent`**: Riceve il prompt, contatta Ollama e genera l'audio via TTS.
   - **`SystemAdminAgent`**: Muove i file tra le cartelle temporanee (`preparing/`), finali (`ready/`) o di fallimento (`failed/`), ed elimina i vecchi file.

## Conseguenze
- **Pro**: Lo stream RTMP non può più subire interruzioni o starvation a causa della lentezza dell'inferenza AI. La regia è completamente isolata dalla produzione.
- **Pro**: Il codice è ora estremamente modulare, facilitando test unitari per i singoli agenti.
- **Contro**: L'impronta di spazio su disco aumenta perché gli asset restano nel Content Buffer fino a che il SystemAdminAgent non li ripulisce.
- **Contro**: Richiede che il palinsesto venga conosciuto in anticipo dal `PreparationAgent` (orizzonte corrente: 2 ore).

## Stato
Approvata e Implementata.
