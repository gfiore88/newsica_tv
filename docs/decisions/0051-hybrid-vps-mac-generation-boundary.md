# ADR 0051: Confine Ibrido VPS/Mac per Generazione AI Remota

- Stato: Accettato
- Data: 2026-05-29

## Contesto

NewsicaTV nasce con il principio "tutto locale, tutto gratuito": FFmpeg, database, regia, dashboard, LLM, TTS e generazione musicale AI girano sulla stessa macchina.

Questo modello e' semplice e resta necessario come modalita' base, ma crea un collo di bottiglia operativo:
- i modelli AI locali possono saturare CPU/GPU mentre lo stream deve restare realtime;
- i tempi lunghi di podcast, TTS multi-speaker, musica AI e shorts non devono mettere a rischio la diretta;
- un futuro VPS remoto puo' essere piu' adatto a tenere online FFmpeg, database, dashboard e processi residenti H24;
- il Mac locale resta invece piu' adatto alla parte pesante: Ollama, TTS, ACE-Step e rendering.

Serve quindi una modalita' ibrida VPS+Mac, senza perdere la modalita' full local e senza duplicare due pipeline da mantenere manualmente.

## Decisione

NewsicaTV supportera' due modalita' operative selezionabili da environment:

```bash
NEWSICA_GENERATION_MODE=local   # default: comportamento attuale, tutto sulla stessa macchina
NEWSICA_GENERATION_MODE=remote  # VPS runtime + Mac worker AI
```

Qualunque valore dinamico richiesto dalla modalita' remota deve arrivare da environment o da file di configurazione esclusi dal repository pubblico. Esempi:

```bash
NEWSICA_REMOTE_GENERATION_URL=https://vps.example.invalid
NEWSICA_REMOTE_GENERATION_TOKEN=...
NEWSICA_REMOTE_WORKER_ID=mac-studio-1
NEWSICA_REMOTE_POLL_SECONDS=10
NEWSICA_REMOTE_IDLE_POLL_SECONDS=30
NEWSICA_REMOTE_HEARTBEAT_SECONDS=15
NEWSICA_REMOTE_STALE_SECONDS=300
NEWSICA_REMOTE_MAX_UPLOAD_MB=512
NEWSICA_REMOTE_INCOMING_RETENTION_SECONDS=86400
NEWSICA_REMOTE_UPLOAD_METHOD=rsync
NEWSICA_REMOTE_SSH_HOST=...
NEWSICA_REMOTE_SSH_USER=...
NEWSICA_REMOTE_SSH_PORT=22
NEWSICA_REMOTE_ASSETS_INCOMING_DIR=/opt/newsica/runtime/assets/incoming
```

Regola di prodotto: NewsicaTV deve poter diventare repository pubblica o prodotto vendibile. Di conseguenza non e' ammesso hardcodare nel codice URL VPS reali, token, username, host SSH, path assoluti di produzione, stream key, nomi macchina personali o credenziali. Il codice puo' contenere solo default non sensibili e locali, ad esempio `NEWSICA_GENERATION_MODE=local` o endpoint locali di sviluppo.

Il VPS resta proprietario della continuita' live:
- FFmpeg e RTMP verso YouTube;
- database e repository applicativi;
- `DirectorAgent`, scheduler, dashboard, Telegram, chat, breaking news, ticker e overlay;
- palinsesto, stati runtime, fallback e decisioni di messa in onda;
- archivio degli asset validati pronti per lo stream.

Il Mac diventa un worker AI comandato a job:
- genera copioni con LLM locale;
- produce TTS;
- genera musica AI;
- renderizza shorts o altri contenuti pesanti;
- restituisce al VPS un pacchetto asset validabile.

Il `DirectorAgent` non deve dipendere dalla disponibilita' del Mac. La regia legge solo asset gia' `ready` sul VPS e usa fallback editoriali quando un job remoto non arriva entro la deadline.

## Contratto Unico di Generazione

Per evitare due flussi divergenti, non verranno create due pipeline editoriali separate.

La regola architetturale e':

> locale e remoto devono condividere lo stesso contratto applicativo di generazione; cambia solo il trasporto/esecutore.

L'implementazione target dovra' introdurre un'interfaccia comune, ad esempio:

```python
class GenerationClient:
    def request_slot_asset(self, request): ...
    def request_ai_music(self, request): ...
    def get_status(self, generation_id): ...
```

Con due adapter:
- `LocalGenerationClient`: esegue il codice attuale nella stessa macchina;
- `RemoteGenerationClient`: crea job per il worker Mac e aspetta il completamento tramite stato/job queue.

`preparation_agent.py` e i servizi di schedulazione devono parlare con `GenerationClient`, non direttamente con `AIIntegratorAgent`, `tts_generator.py` o `ai_music_worker.py`.

La logica editoriale condivisa deve restare una sola:
- costruzione contenuti e prompt;
- validazione titolo/tema;
- manifest asset;
- fact-check e fallback;
- regole di deadline e stato.

Sono ammessi adapter diversi solo per:
- claim/lock del job;
- trasferimento file;
- heartbeat del worker;
- upload/download asset;
- validazione finale lato VPS.

## Modello Job

La modalita' remota usera' una coda persistente gestita dal VPS. Il modello minimo dei job deve includere:

- `id`
- `job_type`: `slot_audio`, `ai_music`, `short`, `breaking_audio`
- `status`: `pending`, `claimed`, `running`, `uploading`, `ready`, `failed`, `expired`
- `priority`
- `slot_time`
- `character`
- `title`
- `theme`
- `payload_json`
- `artifact_manifest_json`
- `error`
- `deadline_at`
- `worker_id`
- timestamp di creazione, claim, heartbeat e completamento.

Il worker Mac deve usare claim atomico: un job puo' essere preso da un solo worker. I job `claimed` o `running` senza heartbeat oltre una soglia devono tornare recuperabili o fallire in modo esplicito.

## Pacchetto Asset

Ogni output remoto deve arrivare sul VPS come directory staging incompleta, per esempio:

```text
runtime/assets/incoming/{job_id}/
  manifest.json
  script.txt
  audio.wav
  audio_part1.wav
  audio_part2.wav
```

Il VPS deve validare il pacchetto prima di renderlo visibile alla regia:
- manifest presente e coerente con `slot_time`, `character`, `title`, `theme`;
- file audio/video richiesti presenti;
- durata e formato compatibili con il playout;
- nessun mismatch con il palinsesto corrente;
- move atomico verso `runtime/assets/ready/{slot_id}` solo dopo validazione.

La regia non deve mai leggere asset da `incoming` o da directory parziali.

## Trasporto

Il modello preferito e' pull dal Mac verso VPS:
- il VPS espone job e stato;
- il Mac apre connessioni in uscita, evitando problemi di NAT domestico;
- upload via HTTPS autenticato, SFTP/rsync su SSH, o comandi CLI remoti.

Non va usato SQLite montato via rete. Il database resta locale al VPS; il worker comunica tramite API/comandi controllati.

Per la prima implementazione e' accettabile un trasporto semplice basato su SSH/rsync, purche':
- il claim del job sia atomico lato VPS;
- gli upload siano in staging;
- la pubblicazione dell'asset sia atomica;
- ogni errore sia registrato nello stato job.

Le credenziali e i parametri di trasporto devono essere configurati esclusivamente via environment. Se una variabile obbligatoria manca, il processo deve fallire con un errore esplicito, non usare fallback personali o valori reali cablati.

## Rollout

La migrazione deve essere incrementale e reversibile:

1. Aggiungere `NEWSICA_GENERATION_MODE`, default `local`.
2. Estrarre `GenerationClient` senza cambiare comportamento.
3. Implementare `LocalGenerationClient` usando il codice attuale.
4. Aggiungere coda job e `RemoteGenerationClient` dietro feature flag.
5. Aggiungere un worker co-located di sviluppo che consuma la coda persistente e valida stati/heartbeat.
6. Testare prima `ai_music` remoto, perche' non blocca direttamente uno slot parlato.
7. Implementare il trasporto Mac-VPS usando lo stesso contratto job.
8. Estendere a slot audio pre-prodotti.
9. Estendere a podcast e shorts.

Il passaggio a `remote` non deve cambiare il contratto della regia: un contenuto va in onda solo se e' `ready`; altrimenti scatta fallback.

## Test Obbligatori

Ogni implementazione derivata da questo ADR deve includere test automatici su:

- modalita' `local` invariata;
- adapter remoto con worker fake;
- claim concorrente di uno stesso job;
- job running stale;
- upload incompleto non visibile al Director;
- manifest mismatch rigettato;
- deadline scaduta con fallback;
- move atomico da `incoming` a `ready`;
- compatibilita' dei repository DB.

Per modifiche runtime, restano obbligatori anche `py_compile`, regression test pertinenti e verifica log post-restart secondo ADR 0049.

## Conseguenze

Vantaggi:
- la diretta H24 resta sul VPS e non dipende dalla stabilita' del Mac;
- il Mac puo' essere usato come macchina AI pesante senza esporre servizi in ingresso;
- la modalita' full local resta disponibile e diventa il baseline di regressione;
- il rischio di drift tra locale e remoto viene ridotto tramite un contratto unico e adapter sottili.

Costi:
- serve introdurre una coda job piu' generale rispetto all'attuale `ai_music_jobs`;
- la validazione asset deve diventare piu' rigorosa;
- il sistema avra' piu' stati operativi da osservare in dashboard e log.

## Stato Implementativo

Al 2026-05-29 sono implementati:
- `NEWSICA_GENERATION_MODE=local|remote`;
- contratto `GenerationClient` con adapter locale e remoto;
- tabella `generation_jobs` con claim atomico, heartbeat, recovery stale e stati di lifecycle;
- worker `src/generation_worker.py` con backend `sqlite` e `http`;
- API VPS protette da `NEWSICA_REMOTE_GENERATION_TOKEN` per claim, running, heartbeat, upload, ready e failed;
- upload multipart HTTP degli artifact;
- staging `runtime/assets/incoming/{job_id}`;
- validazione e pubblicazione atomica per `slot_audio`;
- pubblicazione artifact `ai_music` in `runtime/assets/ai_music`.
- limite upload configurabile con `NEWSICA_REMOTE_MAX_UPLOAD_MB`;
- API summary e cleanup staging `incoming`.

Resta da completare per produzione reale:
- deployment separato Mac/VPS;
- hardening TLS/reverse proxy;
- eventuale trasporto alternativo rsync/SFTP per artifact molto grandi;
- UI completa per monitorare worker e job remoti.

## Non Decisioni

Questo ADR non sceglie ancora:
- il protocollo definitivo tra VPS e Mac;
- il formato finale dell'API HTTP o CLI;
- il database futuro oltre SQLite;
- il provider di reverse proxy o TLS.

Queste scelte verranno prese in ADR successivi o nel task di implementazione, mantenendo il vincolo zero SaaS a pagamento.
