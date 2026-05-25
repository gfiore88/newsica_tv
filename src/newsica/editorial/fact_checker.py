import re

def check_hallucinations(script_text: str, source_truth: str) -> tuple[bool, list[str]]:
    """
    Verifica se il testo generato contiene numeri (cifre o percentuali) 
    che non sono presenti nel prompt sorgente.
    Ritorna un booleano (is_safe) e una lista di entità fallite.
    """
    raw_str = source_truth.lower()
    
    # Trova tutti i numeri (inclusi quelli con virgola/punto e percentuali)
    # Es: 50, 3.5, 20%, 30.000
    pattern = re.compile(r'\b\d+(?:[.,]\d+)?%?\b')
    script_numbers = pattern.findall(script_text.lower())
    
    bad_entities = []
    
    # Ignora anni e numeri molto piccoli che potrebbero far parte di discorsi colloquiali
    # o strutture del palinsesto (es. "parte 1", "3 notizie", "24 ore").
    ignore_list = {"2024", "2025", "2026", "24", "48", "3", "4", "1", "2"}
    
    for num_str in set(script_numbers):
        if num_str in ignore_list:
            continue
            
        # Se il numero non è presente come stringa nel raw JSON, è un'allucinazione oggettiva.
        if num_str not in raw_str:
            bad_entities.append(num_str)
            
    if bad_entities:
        return False, bad_entities
    
    return True, []

def silent_scrub(script_text: str, bad_entities: list[str]) -> str:
    """
    Rimuove chirurgicamente l'intera frase che contiene una delle bad_entities.
    Preserva il resto del blocco senza interruzioni.
    """
    # Dividiamo il testo in frasi in modo grossolano
    sentences = re.split(r'(?<=[.!?])\s+', script_text)
    
    safe_sentences = []
    
    for sentence in sentences:
        is_bad = False
        lower_sent = sentence.lower()
        for bad in bad_entities:
            # Match della parola esatta
            if re.search(r'\b' + re.escape(bad) + r'\b', lower_sent):
                is_bad = True
                break
                
        if not is_bad:
            safe_sentences.append(sentence)
            
    scrubbed_text = " ".join(safe_sentences).strip()
    
    # Failsafe assoluto se tutte le frasi sono state droppate
    if not scrubbed_text:
         return "Le notizie dettagliate sono in fase di aggiornamento. Ci risentiamo tra poco con la nostra selezione musicale. [MUSIC_BREAK]"
         
    return scrubbed_text
