# ADR 0001: Uso di Named Pipe (FIFO) e Raw PCM per lo Streaming Continuo

## Stato
Accettato

## Data
2026-05-18

## Contesto
Per realizzare un canale TV H24 automatico (MVP 2), abbiamo la necessità di aggiornare continuamente il flusso audio (nuove notizie, musica di sottofondo) senza mai interrompere la connessione RTMP tra FFmpeg e YouTube. L'approccio precedente (loop su un singolo file WAV) non permetteva aggiornamenti dinamici senza riavviare lo stream.

## Decisione
Abbiamo deciso di utilizzare una **Named Pipe (FIFO)** in Unix (creata via Python con `os.mkfifo`) per far comunicare lo script di regia (`src/director.py`) e lo script di streaming (`src/stream.sh`).
Inoltre, per evitare problemi di lettura degli header WAV ripetuti quando si concatenano più file nella stessa pipe, abbiamo deciso di inviare dati in formato **Raw PCM (s16le, 24000Hz, mono)**.

## Conseguenze
- **Pro**: Lo stream FFmpeg rimane sempre attivo leggendo dalla pipe, garantendo la continuità H24 su YouTube.
- **Pro**: Python può generare e mixare audio in background e "spingerlo" nella pipe quando pronto.
- **Contro**: Se Python non alimenta la pipe abbastanza velocemente, FFmpeg potrebbe andare in buffer underflow (risolto inserendo musica di riempimento o mantenendo il flusso costante).
- **Contro**: È necessario avviare prima lo script Python (che si blocca in attesa di apertura della pipe) e poi FFmpeg.
