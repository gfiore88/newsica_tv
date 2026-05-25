# ADR 0042: Rendere lo shutdown del Director cooperativo e distinguibile dal crash

## Stato
Accettata - 2026-05-25

## Contesto

Dopo i refactor recenti il `director` era in grado di recuperare lo slot corrente al restart, ma la sua terminazione restava brusca:

- un `kill` o un restart tecnico interrompeva di colpo il processo Python;
- i sottoprocessi `ffmpeg` figli potevano ancora stare scrivendo PCM verso `pipe:1`, producendo rumore tipo `Broken pipe`;
- il `watchdog.sh` trattava ogni uscita del director come crash, rendendo piu' difficile distinguere un deploy controllato da un errore reale.

Questa situazione non rompeva necessariamente la live, ma sporcava i log e peggiorava il debugging operativo.

## Decisione

Introduciamo uno shutdown cooperativo del `director`:

- `SIGTERM` e `SIGINT` vengono intercettati esplicitamente;
- il director imposta uno stato di shutdown condiviso fra loop principale e generator thread;
- l'audio corrente viene terminato in modo esplicito e la coda PCM viene svuotata;
- il wait sulla FIFO viene sbloccato, cosi' i thread non restano appesi durante il teardown;
- se il teardown cooperativo non si completa entro una breve grace window, il processo si auto-chiude con `exit 0` invece di restare in hang;
- il processo termina con `exit 0` quando lo stop e' intenzionale.

Il `watchdog.sh` viene aggiornato per distinguere:

- exit `0`, `130`, `143`: arresto intenzionale / restart tecnico;
- ogni altro codice: arresto anomalo da trattare come crash.

## Conseguenze

Benefici:

- meno rumore di log durante restart tecnici;
- migliore separazione operativa fra crash veri e deploy/riavvii;
- minore probabilita' di `Broken pipe` dovuti a teardown brusco del processo padre.

Tradeoff:

- la logica di shutdown introduce stato runtime addizionale (`shutdown_requested`);
- resta possibile vedere errori di basso livello se un sottoprocesso esterno viene forzato brutalmente fuori dal path cooperativo.

## Implementazione

- `src/director.py`
  - aggiunti signal handler espliciti;
  - aggiunta `request_shutdown(...)`;
  - il generator e il loop FIFO verificano `shutdown_requested` e terminano in modo cooperativo.
- `src/watchdog.sh`
  - log differenziati per stop intenzionale vs arresto anomalo.

## Verifica

Test eseguiti:

- `python3 -m py_compile src/director.py src/newsica/tests/test_director_shutdown.py`
- `PYTHONPATH=src venv/bin/python3 -m unittest src/newsica/tests/test_director_shutdown.py`

Validazione runtime:

- restart del director sotto watchdog;
- verifica nei log che il director si chiuda con messaggio di shutdown pulito;
- verifica che il watchdog segnali restart intenzionale e non crash.
