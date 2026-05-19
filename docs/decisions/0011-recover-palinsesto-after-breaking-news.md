# 0011 - Ripristinare il palinsesto dopo una Breaking News

## Stato

Accettata

## Contesto

Una breaking news lanciata dalla UI interrompe correttamente musica o speaker, svuota la coda e mette in onda l'edizione straordinaria. Dopo la fine, pero', lo stato ON AIR poteva restare su `ULTIM'ORA` e il generatore poteva rimanere appeso a un processo FFmpeg del contenuto interrotto.

## Decisione

- La regia usa una terminazione centralizzata del processo audio corrente: prima `terminate`, poi `kill` se FFmpeg non esce entro un secondo.
- Alla fine della breaking news, la regia forza subito una metadata del palinsesto corrente per aggiornare dashboard e overlay.
- Dopo la breaking news viene attivato un interrupt del ciclo regolare, cosi' eventuali code o letture audio residue vengono scartate e il generatore riparte da un ciclo pulito.

## Conseguenze

L'edizione straordinaria resta prioritaria, ma al termine la live torna in modo prevedibile alla fascia corretta senza lasciare la UI o l'overlay bloccati su `ULTIM'ORA`.
