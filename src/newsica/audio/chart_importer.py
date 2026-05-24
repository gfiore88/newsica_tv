import os
import sys
import json
import requests
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# Aggiunge il percorso principale del progetto al sys.path
BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.newsica.config.paths import BASE_DIR, TMP_DIR
from src.newsica.audio.settings import resolve_ffmpeg_cmd

# Costanti
MUSIC_DIR = BASE_DIR / "assets" / "music"
ITUNES_CHART_URL = "https://rss.applemediaservices.com/api/v2/it/music/most-played/20/songs.json"
# client_id=56d30c95 è un client_id di test pubblico Jamendo
JAMENDO_CHART_URL = "https://api.jamendo.com/v1.2/tracks/?client_id=56d30c95&format=json&limit={limit}&order=popularity_total&type=single+albumtrack&license_cc=cc-by"

def fetch_itunes_chart(limit=5):
    print(f"📡 [iTunes] Recupero la classifica Top {limit} iTunes Italia...")
    try:
        response = requests.get(ITUNES_CHART_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        songs = data.get("feed", {}).get("results", [])
        if not songs:
            raise ValueError("Classifica iTunes vuota.")
            
        chart_list = []
        for idx, song in enumerate(songs[:limit]):
            chart_list.append({
                "position": idx + 1,
                "title": song.get("name", "").strip(),
                "artist": song.get("artistName", "").strip(),
                "url": song.get("url", ""),
                "download_url": None, # Richiede ricerca YouTube
                "license": "Commercial Copyright (Content ID Risk)",
                "license_url": "",
                "is_mock": False
            })
            
        return chart_list
    except Exception as e:
        print(f"⚠️ [iTunes] Classifica non raggiungibile o vuota ({e}).")
        print(f"💡 [iTunes] Attivo modalità SIMULAZIONE OFFLINE per autotest...")
        mock_songs = [
            {"name": "Nel blu dipinto di blu", "artistName": "Domenico Modugno", "url": "https://music.apple.com/mock1"},
            {"name": "L'Italiano", "artistName": "Toto Cutugno", "url": "https://music.apple.com/mock2"}
        ]
        chart_list = []
        for idx, song in enumerate(mock_songs[:limit]):
            chart_list.append({
                "position": idx + 1,
                "title": song["name"],
                "artist": song["artistName"],
                "url": song["url"],
                "download_url": None,
                "license": "Commercial Copyright (Content ID Risk)",
                "license_url": "",
                "is_mock": True
            })
        return chart_list

def fetch_jamendo_chart(limit=5):
    print(f"📡 [Jamendo] Recupero Top {limit} brani Creative Commons (CC-BY)...")
    url = JAMENDO_CHART_URL.format(limit=limit)
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        songs = data.get("results", [])
        if not songs:
            raise ValueError("Classifica Jamendo vuota.")
            
        chart_list = []
        for idx, song in enumerate(songs):
            chart_list.append({
                "position": idx + 1,
                "title": song.get("name", "").strip(),
                "artist": song.get("artist_name", "").strip(),
                "url": song.get("shorturl", ""),
                "download_url": song.get("audio", ""), # Download diretto MP3
                "license": "Creative Commons BY 3.0 / 4.0 (Safe for Live)",
                "license_url": song.get("license_ccurl", "https://creativecommons.org/licenses/by/3.0/"),
                "is_mock": False
            })
            
        return chart_list
    except Exception as e:
        print(f"⚠️ [Jamendo] Classifica non raggiungibile o vuota ({e}).")
        print(f"💡 [Jamendo] Attivo modalità SIMULAZIONE OFFLINE per autotest...")
        mock_songs = [
            {"name": "Summer Breeze", "artist": "Acoustic CC-Artist", "audio": "https://api.jamendo.com/mock/audio1.mp3", "url": "https://www.jamendo.com/track/mock1"},
            {"name": "Abstract Chill", "artist": "Lo-Fi Creator", "audio": "https://api.jamendo.com/mock/audio2.mp3", "url": "https://www.jamendo.com/track/mock2"}
        ]
        chart_list = []
        for idx, song in enumerate(mock_songs[:limit]):
            chart_list.append({
                "position": idx + 1,
                "title": song["name"],
                "artist": song["artist"],
                "url": song["url"],
                "download_url": song["audio"],
                "license": "Creative Commons BY 3.0 (Safe for Live)",
                "license_url": "https://creativecommons.org/licenses/by/3.0/",
                "is_mock": True
            })
        return chart_list

def get_existing_manifests():
    manifests = {}
    if not MUSIC_DIR.exists():
        return manifests
        
    for file in MUSIC_DIR.iterdir():
        if file.suffix == ".json":
            try:
                with open(file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    artist = manifest.get("artist", "").lower()
                    title = manifest.get("title", "").lower()
                    manifests[f"{artist} - {title}"] = file
            except Exception:
                pass
    return manifests

def clean_filename(name):
    # Pulisce il nome del file da caratteri speciali per renderlo compatibile con tutti i sistemi operativi
    keepcharacters = (' ', '.', '_', '-', '(', ')')
    return "".join(c for c in name if c.isalnum() or c in keepcharacters).rstrip()

def download_and_convert(song, ffmpeg_cmd, source_type):
    title = song["title"]
    artist = song["artist"]
    
    print(f"\n🔍 [Pos. {song['position']}] Elaboro: {artist} - {title}")
    
    # Prepariamo i percorsi temporanei ed il nome pulito del file
    safe_title = clean_filename(f"{artist} - {title}")
    temp_output_path = TMP_DIR / f"temp_{safe_title}.mp3"
    final_output_path = MUSIC_DIR / f"{safe_title}.mp3"
    manifest_output_path = MUSIC_DIR / f"{safe_title}.json"
    
    # 1. Recupero dell'audio (Simulazione Offline o Download Reale)
    if song.get("is_mock", False):
        print(f"  [SIMULAZIONE] Copio un asset locale esistente per simulare il download...")
        source_audio = None
        for file in MUSIC_DIR.iterdir():
            if file.suffix == ".mp3" and not file.name.startswith("temp_"):
                source_audio = file
                break
        if not source_audio:
            # Fallback su un jingle
            jingle_dir = BASE_DIR / "assets" / "jingles"
            if jingle_dir.exists():
                for file in jingle_dir.iterdir():
                    if file.suffix == ".mp3":
                        source_audio = file
                        break
        if not source_audio:
            print("  ❌ Nessun file audio sorgente trovato per la simulazione.")
            return False
            
        print(f"  -> Copio '{source_audio.name}' in '{temp_output_path.name}'...")
        try:
            import shutil
            shutil.copy(source_audio, temp_output_path)
        except Exception as e:
            print(f"  ❌ Errore copia simulata: {e}")
            return False
    else:
        # Download Reale
        if song["download_url"]:
            # Download HTTP diretto (es. Jamendo) - molto più veloce e sicuro!
            print(f"  -> Avvio download HTTP diretto da Jamendo: {song['download_url']}...")
            try:
                response = requests.get(song["download_url"], stream=True, timeout=15)
                response.raise_for_status()
                with open(temp_output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            except Exception as e:
                print(f"  ❌ Errore durante il download HTTP: {e}")
                return False
        else:
            # Ricerca e download via yt-dlp (iTunes)
            query = f"{artist} - {title} official audio"
            temp_output_template = str(TMP_DIR / f"temp_{safe_title}.%(ext)s")
            yt_dlp_cmd = [
                "yt-dlp",
                "--quiet",
                "--no-warnings",
                f"ytsearch1:{query}",
                "-f", "bestaudio",
                "-o", temp_output_template
            ]
            try:
                print(f"  -> Avvio ricerca e download con yt-dlp per la query: \"{query}\"...")
                subprocess.run(yt_dlp_cmd, check=True)
            except subprocess.CalledProcessError as e:
                print(f"  ❌ Errore download yt-dlp per '{artist} - {title}': {e}")
                return False
                
            # Identifichiamo il file temporaneo
            downloaded_file = None
            for file in TMP_DIR.iterdir():
                if file.name.startswith(f"temp_{safe_title}."):
                    downloaded_file = file
                    break
            if not downloaded_file or not downloaded_file.exists():
                print(f"  ❌ File scaricato temporaneo non trovato. Skip.")
                return False
            temp_output_path = downloaded_file

    # 2. Conversione e Normalizzazione in MP3 standard stereo 192k via FFmpeg
    print(f"  -> Normalizzazione e conversione in MP3 via FFmpeg...")
    ffmpeg_convert_cmd = [
        ffmpeg_cmd,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(temp_output_path),
        "-codec:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        str(final_output_path)
    ]
    
    try:
        subprocess.run(ffmpeg_convert_cmd, check=True)
        # Rimuoviamo il file temporaneo
        if temp_output_path.exists():
            temp_output_path.unlink()
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Errore conversione FFmpeg per '{artist} - {title}': {e}")
        if temp_output_path.exists():
            temp_output_path.unlink()
        return False
        
    # 3. Generazione Manifest di Conformità e Tracciamento Licenza
    print(f"  -> Genero il file manifest di conformità licenza...")
    manifest_data = {
        "title": title,
        "artist": artist,
        "imported_from": f"{source_type.upper()} Importer",
        "imported_at": datetime.now().isoformat(timespec="seconds"),
        "license": song["license"],
        "license_url": song["license_url"],
        "testing_only": song.get("is_mock", False),
        "source_url": song["url"],
        "attribution_required": True
    }
    
    try:
        with open(manifest_output_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️ Errore salvataggio manifest per '{artist} - {title}': {e}")
        
    print(f"  ✅ Importato con successo: {safe_title}.mp3")
    return True

def main():
    parser = argparse.ArgumentParser(description="NewsicaTV Chart Music Importer")
    parser.add_argument("--source", type=str, default="jamendo", choices=["jamendo", "itunes"], 
                        help="Sorgente della classifica: jamendo (100 percento Sicuro Creative Commons, default) o itunes (Commerciale, Rischio Copyright)")
    parser.add_argument("--limit", type=int, default=3, help="Numero massimo di canzoni da importare (default: 3)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("📻 NewsicaTV Chart Music Importer")
    print(f"Sorgente selezionata: {args.source.upper()}")
    
    if args.source == "itunes":
        print("\n⚠️  [ATTENZIONE] Stai importando brani commerciali protetti da copyright.")
        print("   Questo comporta un rischio estremamente elevato di Content ID o blocco della live su YouTube!")
    else:
        print("\n🛡️  [SICURO CC-BY] Stai importando brani con licenza Creative Commons Attribution.")
        print("   Questi brani sono al 100% sicuri per la trasmissione in live streaming su YouTube.")
    print("=" * 60 + "\n")
    
    # Assicuriamoci che le cartelle esistano
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    
    # Risolviamo il percorso di FFmpeg
    ffmpeg_cmd = resolve_ffmpeg_cmd()
    if not ffmpeg_cmd:
        print("❌ Errore: FFmpeg non è stato trovato a sistema. Impossibile procedere.")
        sys.exit(1)
        
    # 1. Recupero la classifica
    if args.source == "jamendo":
        chart = fetch_jamendo_chart(limit=args.limit)
    else:
        chart = fetch_itunes_chart(limit=args.limit)
        
    if not chart:
        print("❌ Classifica vuota o non raggiungibile. Esco.")
        sys.exit(1)
        
    # 2. Ottengo i manifest esistenti per evitare duplicati
    existing = get_existing_manifests()
    
    imported_count = 0
    for song in chart:
        key = f"{song['artist'].lower()} - {song['title'].lower()}"
        if key in existing:
            print(f"⏭️ [Pos. {song['position']}] {song['artist']} - {song['title']} è già presente in libreria. Skip.")
            continue
            
        success = download_and_convert(song, ffmpeg_cmd, args.source)
        if success:
            imported_count += 1
            
    print("\n" + "=" * 60)
    print(f"🎉 Importazione completata! Nuovi brani importati: {imported_count}/{len(chart)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
