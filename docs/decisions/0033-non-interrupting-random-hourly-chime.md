# ADR 0033: Segnale orario random e non interrompente

Data: 2026-05-21

## Contesto

Il palinsesto ora contiene trasmissioni a cadenza oraria. Mandare il segnale orario al minuto `:00` collide quasi sempre con l'avvio di uno show, e il comportamento precedente del Director trattava il chime come un'interruzione sincrona: sfumava la coda, scriveva lo stato `chime` e mandava il WAV al posto dell'audio regolare.

Questo rendeva il segnale orario troppo invasivo e poteva coprire speaker o programmi parlati.

## Decisione

Il segnale orario viene programmato una volta all'ora a un minuto casuale stabile, compreso tra `:07` e `:53`, calcolato deterministicamente sulla specifica ora locale.

Il Director non tratta più `HOURLY_CHIME_READY` come interrupt. Prima di mandarlo controlla lo stato runtime e lo autorizza solo se è in onda una rotazione musicale (`music_only` o `music_rotation_until_deadline`).

Quando autorizzato, il segnale viene mixato sopra i chunk musicali già presenti in coda. La coda non viene svuotata, non viene attivato fade-out preventivo e lo stato on-air non viene sostituito da `SEGNALE ORARIO`.

Se al minuto scelto è in onda uno speaker o un contenuto parlato, il segnale viene saltato.

## Conseguenze

- Il chime non interrompe più news, podcast, meteo parlato, rubriche o speaker.
- Non c'è più dipendenza dal minuto `:00`, quindi le partenze orarie del palinsesto restano pulite.
- Il test manuale da dashboard resta disponibile, ma non forza la copertura di una voce: passa comunque dal guardrail del Director.
- Il mix viene eseguito localmente in PCM con NumPy e FFmpeg già presenti nel sistema, senza API o servizi esterni.
