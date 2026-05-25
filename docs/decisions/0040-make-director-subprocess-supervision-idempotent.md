# ADR 0040: Rendere idempotente la supervisione dei sotto-processi del Director

## Stato
Accettata - 2026-05-25

## Contesto

Dopo il refactor del director, un restart del solo `director.py` mostrava errori come:

- `Un'altra istanza di ticker_agent è già in esecuzione`
- `Un'altra istanza di overlay_agent è gia' in esecuzione`
- `Un'altra istanza di chat_agent è gia' in esecuzione`

Inoltre, due agenti avviati dal supervisor non avevano nemmeno una protezione singleton locale:

- `preparation_agent.py`
- `hourly_chime_agent.py`

Questo produceva doppi processi reali quando il director veniva riavviato dal watchdog o manualmente.

## Decisione

Il `SubprocessSupervisor` del director deve diventare idempotente:

- prima di lanciare un agente secondario, verifica via process table se lo script e' gia' vivo;
- se trova una istanza gia' attiva, non la rilancia e logga uno skip informativo.

In aggiunta:

- `preparation_agent.py` riceve un lock singleton in `runtime/preparation_agent.lock`;
- `hourly_chime_agent.py` riceve un lock singleton in `runtime/hourly_chime_agent.lock`.

## Conseguenze

Benefici:

- restart del director piu' puliti e leggibili;
- niente doppie istanze di preparazione o segnale orario;
- minore rumore nei log durante recovery del watchdog.

Tradeoff:

- il supervisor usa la process table locale per capire se un agente e' attivo;
- il controllo e' pragmatico e dipende dal path dello script, ma e' adeguato al runtime locale di NewsicaTV.

## Implementazione

- `src/newsica/broadcast/process_monitor.py`
  - aggiunto `_is_agent_running(script_name)`
  - `start_all()` ora salta gli agenti gia' vivi
- `src/preparation_agent.py`
  - aggiunto singleton lock
- `src/hourly_chime_agent.py`
  - aggiunto singleton lock

## Verifica

Test eseguiti:

- `python3 -m py_compile src/newsica/broadcast/process_monitor.py src/hourly_chime_agent.py src/preparation_agent.py`
- `PYTHONPATH=src venv/bin/python3 -m unittest src/newsica/tests/test_process_monitor.py`

Validazione runtime:

- pulizia manuale delle doppie istanze gia' esistenti;
- restart del director sotto watchdog;
- verifica che i log mostrino `skip avvio duplicato` invece di errori di singleton o nuove doppie istanze reali.
