# 0025 - Il debug live deve partire sempre dai log

## Contesto

Durante un incidente sulla diretta live, la diagnosi non puo' basarsi solo sul fatto che un processo risulti avviato o su ipotesi operative. In un sistema H24 con DirectorAgent, FIFO audio, FFmpeg RTMP, overlay e YouTube Live, un processo attivo non garantisce che audio, palinsesto, ingest e player pubblico siano effettivamente coerenti.

## Decisione

Ogni debug di diretta deve partire obbligatoriamente dalla lettura dei log e dello stato runtime:

- `./manage.sh status`
- `tmp/director.log`
- `tmp/stream.log`
- `tmp/ffmpeg_progress.txt`
- `runtime/on-air-state.json`
- `tmp/current_program.txt`
- `tmp/next_program.txt`
- `screen -ls`
- `launchctl list | rg 'com\\.newsica' || true`

L'Orchestratore deve citare in chat cosa ha letto e distinguere tra:

- processo locale fermo o degradato;
- FFmpeg attivo ma ingest RTMP problematica;
- ingest RTMP attivo ma Live Control Room/player YouTube non pubblicato o non agganciato.

## Conseguenze

- Nessun restart, patch o diagnosi live e' considerato completo senza verifica log prima e dopo.
- Il workflow `.agents/workflows/orchestrator.md` include ora un protocollo obbligatorio di debug live.
- Il `DirectorAgent` e gli agenti operativi devono produrre log sufficienti a ricostruire cosa e' stato deciso, preparato e mandato in onda.
