import os
import sys
import urllib.parse
import requests

# Aggiungi 'src' al path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

def main():
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("❌ Errore: YOUTUBE_CLIENT_ID e YOUTUBE_CLIENT_SECRET devono essere configurati nel file .env.")
        sys.exit(1)

    print("ℹ️  Questo script rigenererà il tuo YOUTUBE_REFRESH_TOKEN con i permessi completi di scrittura.")
    print("   Permesso richiesto: https://www.googleapis.com/auth/youtube")
    print("-" * 60)

    # Permetti all'utente di specificare un redirect URI personalizzato se configurato nella console Google
    default_redirect = "https://developers.google.com/oauthplayground"
    print(f"Il Redirect URI predefinito è: {default_redirect}")
    print("Assicurati che questo Redirect URI sia inserito nelle impostazioni della tua Web App nella Google Cloud Console.")
    redirect_uri = input(f"Premi INVIO per usare quello di default o digita il tuo redirect URI personalizzato: ").strip()
    if not redirect_uri:
        redirect_uri = default_redirect

    # Costruisci l'URL di autorizzazione
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube",
        "access_type": "offline",
        "prompt": "consent"  # Forza il rilascio del refresh token
    }
    
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    
    print("\n👉 STEP 1: Apri il seguente URL nel tuo browser per autorizzare l'applicazione:")
    print(f"\n{auth_url}\n")
    print("👉 STEP 2: Accetta i permessi (assicurati di spuntare la casella per consentire la gestione del canale YouTube).")
    print("👉 STEP 3: Copia il codice di autorizzazione generato (se usi OAuth Playground lo vedi a destra dopo lo step 2, oppure prendilo dal parametro '?code=' nell'URL della pagina a cui vieni reindirizzato).")
    
    code = input("\nIncolla qui il codice di autorizzazione: ").strip()
    if not code:
        print("❌ Errore: Il codice non può essere vuoto.")
        sys.exit(1)

    print("\n🔄 Scambio del codice di autorizzazione con i nuovi token di YouTube...")
    
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    
    try:
        resp = requests.post(token_url, data=token_data, timeout=15)
        resp.raise_for_status()
        resp_json = resp.json()
        
        access_token = resp_json.get("access_token")
        refresh_token = resp_json.get("refresh_token")
        
        if not refresh_token:
            print("⚠️ Attenzione: Nessun refresh_token restituito. Se hai già autorizzato l'app precedentemente,")
            print("   Google potrebbe non restituire il refresh token a meno che tu non vada su:")
            print("   https://myaccount.google.com/permissions e revochi i permessi per questa app, per poi riprovare.")
            print("\nEcco la risposta completa da Google:", resp_json)
            sys.exit(1)
            
        print("\n✅ Token scambiati con successo!")
        print(f"Refresh Token (valido a tempo indefinito): {refresh_token[:15]}...")
        
        # Aggiorna il file .env
        env_path = os.path.join(BASE_DIR, ".env")
        if not os.path.exists(env_path):
            print(f"❌ File .env non trovato in {env_path}")
            sys.exit(1)
            
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith("YOUTUBE_REFRESH_TOKEN="):
                new_lines.append(f"YOUTUBE_REFRESH_TOKEN={refresh_token}\n")
                updated = True
            else:
                new_lines.append(line)
                
        # Se non esisteva, aggiungilo in fondo
        if not updated:
            new_lines.append(f"\nYOUTUBE_REFRESH_TOKEN={refresh_token}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        print("💾 File .env aggiornato automaticamente con il nuovo YOUTUBE_REFRESH_TOKEN con pieni poteri!")
        print("🚀 Ora puoi riprovare ad eseguire `venv/bin/python scratch_force_public.py`!")
        
    except Exception as e:
        print(f"❌ Errore durante lo scambio dei token: {e}")

if __name__ == "__main__":
    main()
