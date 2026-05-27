import sys
import os
import requests

def main():
    if len(sys.argv) < 2:
        print("Uso: venv/bin/python scratch_exchange_tiktok.py <codice_copiato_da_url>")
        sys.exit(1)
        
    code = sys.argv[1].strip()
    client_key = "sbaw4wbttbdt465ebe"
    client_secret = "MRy2x7JoOaXksh3n8arJo68WDOCxN9CX"
    redirect_uri = "https://developers.google.com/oauthplayground"
    
    print(f"🔄 Scambio del codice '{code}' con i token di TikTok...")
    
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=15)
        resp.raise_for_status()
        resp_json = resp.json()
        
        if "error" in resp_json and resp_json.get("error") != "":
            print(f"❌ Errore da TikTok: {resp_json.get('error_description') or resp_json.get('error')}")
            sys.exit(1)
            
        access_token = resp_json.get("access_token")
        refresh_token = resp_json.get("refresh_token")
        
        if not refresh_token:
            print("❌ Nessun refresh_token restituito da TikTok. Risposta completa:", resp_json)
            sys.exit(1)
            
        print("✅ Token scambiati con successo!")
        print(f"Access Token (scade in 24h): {access_token[:15]}...")
        print(f"Refresh Token (valido 1 anno): {refresh_token[:15]}...")
        
        # Aggiorna il file .env
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if not os.path.exists(env_path):
            print(f"❌ File .env non trovato in {env_path}")
            sys.exit(1)
            
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith("TIKTOK_REFRESH_TOKEN="):
                new_lines.append(f"TIKTOK_REFRESH_TOKEN={refresh_token}\n")
                updated = True
            elif line.startswith("TIKTOK_ACCESS_TOKEN="):
                new_lines.append(f"TIKTOK_ACCESS_TOKEN={access_token}\n")
            else:
                new_lines.append(line)
                
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        print("💾 File .env aggiornato automaticamente con i nuovi token di TikTok!")
        print("🚀 Ora puoi riavviare con `./manage.sh restart` ed il gioco è fatto!")
        
    except Exception as e:
        print(f"❌ Errore durante lo scambio dei token: {e}")

if __name__ == "__main__":
    main()
