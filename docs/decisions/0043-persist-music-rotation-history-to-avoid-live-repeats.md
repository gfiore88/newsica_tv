# ADR 0043: Persistenza history rotazione musica anti-ripetizione

Data: 2026-05-21

## Contesto

La libreria musicale di NewsicaTV alterna `assets/music/` e `assets/ai_music/`, ma fino ad ora ricordava solo l'ultima sorgente usata in memoria. Dopo un restart del director, o in pool piccoli, la diretta poteva ripetere troppo presto lo stesso brano o tornare subito su tracce appena andate in onda.

Serve una memoria locale, persistente e a costo zero che riduca le ripetizioni ravvicinate senza introdurre dipendenze esterne e senza rompere la modalita' `ai_only`.

## Decisione

`MusicLibrary` salva ora la history recente dei brani in `runtime/music_rotation_history.json`.

La scelta del prossimo brano:

- mantiene una finestra recente locale configurabile con `MUSIC_ROTATION_RECENT_WINDOW` (default `20`);
- valuta prima l'intero pool candidato del momento, poi scarta i brani presenti nella history recente quando esistono alternative fresche;
- applica il filtro prima della scelta della sorgente, cosi' la modalita' `mixed` non favorisce accidentalmente una cartella piena di tracce appena usate;
- non sporca la history durante i tentativi del Director: i brani entrano nella memoria recente solo quando il playout li mette davvero in onda;
- ricade sul pool completo solo quando tutte le opzioni candidate rientrano gia' nella finestra recente.
- salva anche gli ultimi eventi di esclusione in `runtime/music_rotation_blocks.json`, cosi' la Dashboard puo' mostrare quali candidati sono stati scartati dalla finestra recente.

## Conseguenze

- La diretta riduce le ripetizioni ravvicinate anche dopo restart tecnici del director.
- La logica resta interamente locale e basata su file runtime gia' coerenti con il progetto.
- La regia ha ora una diagnostica ispezionabile dalla Dashboard per verificare history recente e candidati esclusi senza dover leggere i log del Director.
- In pool molto piccoli il sistema continua comunque a trovare un brano valido, evitando deadlock o silenzi artificiali.
