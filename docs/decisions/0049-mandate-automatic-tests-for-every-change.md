# ADR 0049: Test Automatici Obbligatori per Ogni Modifica

- Stato: Accettato
- Data: 2026-05-27

## Contesto

Nel ciclo di sviluppo live di NewsicaTV alcuni fix sono stati verificati correttamente a runtime, ma la disciplina sui test automatici non era espressa in modo abbastanza rigido e uniforme nei workflow degli agenti.

Questo lasciava spazio a due rischi:
- fix corretti sul caso immediato ma senza protezione regressiva;
- aspettative non allineate tra orchestrazione, sviluppo e review sulla responsabilità di scrivere test.

## Decisione

Da ora in avanti i test automatici sono obbligatori per ogni modifica.

Il contratto minimo per chiudere un task è:
- `py_compile` sui file toccati;
- unit test o regression test pertinenti al ramo modificato;
- verifica post-restart dei log per qualunque modifica che tocchi runtime, stream, dashboard o processi residenti.

Se manca un agente dedicato ai test, l'Orchestratore assegna formalmente il ruolo di **Unit Test Writer** al `/code_reviewer` o al `/python_engineer`.

Una patch senza test automatici viene considerata incompleta.

## Conseguenze

Vantaggi:
- ogni fix lascia una protezione regressiva concreta;
- gli agenti hanno ownership esplicita sulla qualità, non solo sulla correzione locale;
- si riduce il rischio di bug live riaperti dopo restart o refactor adiacenti.

Costo:
- alcune patch richiederanno più tempo operativo;
- i task dovranno includere sin dall'inizio un piano test, non solo l'implementazione.

## File di processo aggiornati

- `.agents/workflows/orchestrator.md`
- `.agents/workflows/python_engineer.md`
- `.agents/workflows/code_reviewer.md`
- `.agents/workflows/task_analyzer.md`
- `README.md`
