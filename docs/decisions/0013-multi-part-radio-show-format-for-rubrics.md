# 0013 - Formato Rubrica Multi-Part in Stile Show Radiofonico

## Stato

Accettata

## Contesto

Al momento, le rubriche tematiche (es. *Pausa Wellness*, *Sport Flash*) presentano un singolo intervento parlato dello speaker seguito da musica di riempimento casuale fino al blocco successivo. Questo rende l'esperienza meno dinamica e fa ripetere allo speaker frasi introduttive simili. L'obiettivo è trasformare ogni rubrica in un vero e proprio "show radiofonico/televisivo" strutturato in più parti (Interventi) intervallate da un brano musicale completo.

## Decisione

Implementare un formato **Multi-Part Radio Show** che mantenga totale compatibilità con il flusso esistente (meccanismo di fallback a parte singola se l'LLM o il TTS falliscono).

### 1. Generazione del Copione (LLM/Fallback)
* Il processore LLM (`src/llm_processor.py`) viene istruito nei system prompt dei personaggi a generare un copione strutturato in due parti, separate esattamente dal marcatore `[MUSIC_BREAK]`.
* **Parte 1 (Introduzione & News Calde):** Presentazione energica della rubrica e lettura delle prime notizie o concetti chiave. Conclusione invitando all'ascolto di un brano musicale.
* **Parte 2 (Curiosità & Chiusura):** Rientro in studio ("Bentornati su..."), approfondimenti, curiosità o consigli pratici del tema trattato e chiusura formale della rubrica.
* Il generatore di fallback (`build_fallback_script`) inserisce programmaticamente il marcatore `[MUSIC_BREAK]` a metà delle notizie estratte per garantire consistenza anche offline.

### 2. Sintesi Vocale (TTS)
* Il generatore TTS (`src/tts_generator.py`) controlla se il copione in `tmp/script.txt` contiene il marcatore `[MUSIC_BREAK]`.
* Se presente:
  * Divide il testo in due parti.
  * Genera due file audio WAV separati: `tmp/audio_part1.wav` e `tmp/audio_part2.wav`.
  * Crea un file semaforo vuoto `tmp/is_multipart.txt` per notificare la regia.
* Se assente:
  * Genera il singolo file `tmp/audio.wav` (compatibilità legacy).
  * Rimuove `tmp/is_multipart.txt`.

### 3. Sequenziamento della Regia (`src/director.py`)
Quando la regia riproduce una rubrica non puramente musicale:
* Controlla se esiste `tmp/is_multipart.txt`.
* In caso positivo (Show Radiofonico Multi-Part):
  1. Esegue il **Jingle** tematico o classico della rubrica.
  2. Esegue l'**Intervento 1** (`tmp/audio_part1.wav`) mixato con musica di sottofondo a volume ridotto (ducking).
  3. Riproduce **un brano musicale completo** (a volume standard 80%) scelto dalla libreria musicale.
  4. Esegue l'**Intervento 2** (`tmp/audio_part2.wav`) mixato con musica di sottofondo a volume ridotto.
  5. Continua a trasmettere musica di riempimento standard fino all'inizio della fascia successiva.
* In caso negativo:
  * Segue il vecchio comportamento lineare (Jingle -> Singolo audio -> Filler).

## Conseguenze

L'esperienza d'ascolto di NewsicaTV fa un enorme salto di qualità qualitativo, offrendo la sensazione di una vera e propria diretta radiofonica professionale con uno speaker che lancia un pezzo musicale e torna in studio per completare la rubrica. Il sistema di fallback a file singoli previene qualsiasi regressione o crash dei servizi.
