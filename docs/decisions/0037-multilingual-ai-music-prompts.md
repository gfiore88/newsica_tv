# ADR 0037: Prompt multilingua per la musica AI

Data: 2026-05-23

## Contesto

La rotazione musicale AI di NewsicaTV veniva generata senza una politica esplicita sulla lingua dei testi. Per un canale rivolto al pubblico italiano questo produceva un comportamento troppo casuale: mancava una preferenza chiara per canzoni in italiano, pur lasciando spazio a inglese e, per i generi latin, spagnolo.

Serve una regola editoriale stabile che:

- privilegi il repertorio italiano come lingua principale;
- mantenga anche brani in inglese come seconda lingua mainstream;
- favorisca lo spagnolo per latin pop, reggaeton, dembow, merengue e merengueton;
- resti compatibile con ACE-Step, che continua a ricevere un `prompt` in inglese ma può generare lyrics in lingue diverse.

## Decisione

La scelta lingua viene introdotta dentro `EditorialDirectorAgent.generate_music_prompt()` come parte strutturale del prompt musicale.

La policy è:

- `italian` come lingua preferita di default per il pubblico NewsicaTV;
- `english` come seconda lingua ammessa e ricorrente;
- `spanish` come lingua privilegiata per i temi `latin/reggaeton/dembow` e per richieste esplicite coerenti;
- `instrumental` quando il `music_mode` è strumentale.

La lingua può essere:

- scelta per distribuzione pesata in base al tema musicale;
- corretta dal `custom_brief` se la richiesta cita esplicitamente italiano, inglese o spagnolo.

Il JSON del prompt musicale ora espone anche `lyrics_language`, e il metadata del brano generato salva la lingua effettiva insieme a titolo, modalità e prompt.

## Conseguenze

- Pro: il catalogo AI riflette meglio il gusto atteso del pubblico italiano.
- Pro: i blocchi latin acquistano una direzione linguistica coerente con il genere.
- Pro: il dato lingua resta tracciato nei metadata e quindi osservabile a posteriori.
- Pro: i fallback locali non ricadono più sempre su template implicitamente anglofoni o solo strumentali.
- Contro: la varietà linguistica diventa più guidata e meno totalmente casuale.
- Contro: resta possibile che ACE-Step o Ollama producano risultati meno naturali in alcune combinazioni genere/lingua, quindi servirà osservazione empirica sul catalogo generato.
