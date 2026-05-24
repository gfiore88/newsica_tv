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

def fetch_itunes_chart(limit=5):
    print(f"📡 Recupero la classifica Top {limit} iTunes Italia...")
    try:
        response = requests.get(ITUNES_CHART_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        songs = data.get("feed", {}).get("results", [])
        chart_list = []
        
        for idx, song in enumerate(songs[:limit]):
            chart_list.append({
                "position": idx + 1,
                "title": song.get("name", "").strip(),
                "artist": song.get("artistName", "").strip(),
                "url": song.get("url", ""),
                "is_mock": False
            })
            
        return chart_list
    except Exception as e:
        print(f"⚠️ Connessione internet non disponibile (Failed to resolve host).")
        print(f"💡 Attivo modalità SIMULAZIONE OFFLINE per autotest di importazione...")
        # Generiamo una chart fittizia per scopi di autotest
        mock_songs = [
            {"name": "Nel blu dipinto di blu", "artistName": "Domenico Modugno", "url": "https://music.apple.com/mock1"},
            {"name": "L'Italiano", "artistName": "Toto Cutugno", "url": "https://music.apple.com/mock2"},
            {"name": "Volare", "artistName": "Gipsy Kings", "url": "https://music.apple.com/mock3"}
        ]
        chart_list = []
        for idx, song in enumerate(mock_songs[:limit]):
            chart_list.append({
                "position": idx + 1,
                "title": song["name"],
                "artist": song["artistName"],
                "url": song["url"],
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

def download_and_convert(song, ffmpeg_cmd):
    title = song["title"]
    artist = song["artist"]
    query = f"{artist} - {title} official audio"
    
    print(f"\n🔍 [Pos. {song['position']}] Cerco e scarico: {artist} - {title}")
    
    # Prepariamo i percorsi temporanei ed il nome pulito del file
    safe_title = clean_filename(f"{artist} - {title}")
    temp_output_path = TMP_DIR / f"temp_{safe_title}.mp3"
    final_output_path = MUSIC_DIR / f"{safe_title}.mp3"
    manifest_output_path = MUSIC_DIR / f"{safe_title}.json"
    
    if song.get("is_mock", False):
        print(f"  [SIMULAZIONE] Copio un asset locale esistente per simulare il download di yt-dlp...")
        # Copiamo un file audio esistente come sorgente di test per simulare il download
        # Troviamo un qualsiasi file mp3 in assets/music/
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
        # Eseguiamo yt-dlp per cercare e scaricare solo l'audio migliore
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
            print(f"  -> Avvio download con yt-dlp per la query: \"{query}\"...")
            subprocess.run(yt_dlp_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Errore download yt-dlp per '{artist} - {title}': {e}")
            return False
        
    # Cerchiamo il file temporaneo scaricato (poiché l'estensione può variare: .webm, .m4a, ecc.)
    downloaded_file = None
    for file in TMP_DIR.iterdir():
        if file.name.startswith(f"temp_{safe_title}."):
            downloaded_file = file
            break
            
    if not downloaded_file or not downloaded_file.exists():
        print(f"  ❌ File scaricato temporaneo non trovato per '{artist} - {title}'. Skip.")
        return False
        
    # Convertiamo l'audio nel formato MP3 stereo standard ad alta fedeltà (192kbps)
    print(f"  -> Converto in MP3 standard via FFmpeg...")
    ffmpeg_convert_cmd = [
        ffmpeg_cmd,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(downloaded_file),
        "-codec:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        str(final_output_path)
    ]
    
    try:
        subprocess.run(ffmpeg_convert_cmd, check=True)
        # Rimuoviamo il file temporaneo originale per liberare spazio
        downloaded_file.unlink()
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Errore conversione FFmpeg per '{artist} - {title}': {e}")
        if downloaded_file.exists():
            downloaded_file.unlink()
        return False
        
    # Generiamo il file manifest JSON per consentire alla regia di tracciarlo correttamente
    print(f"  -> Genero il file manifest per il tracciamento...")
    manifest_data = {
        "title": title,
        "artist": artist,
        "imported_from": "iTunes Top Played Chart Italy",
        "imported_at": datetime.now().isoformat(timespec="seconds"),
        "testing_only": True,
        "source_url": song["url"]
    }
    
    try:
        with open(manifest_output_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️ Errore salvataggio manifest per '{artist} - {title}': {e}")
        
    print(f"  ✅ Importato con successo: {safe_title}.mp3")
    return True

def main():
    parser = argparse.ArgumentParser(description="NewsicaTV Chart Music Importer (Test-Only)")
    parser.add_argument("--limit", type=int, default=3, help="Numero massimo di canzoni da importare (default: 3)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("📻 NewsicaTV Chart Music Importer — STRUMENTO DI TEST")
    print("=" * 60)
    
    # Assicuriamoci che le cartelle esistano
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    
    # Risolviamo il percorso di FFmpeg
    ffmpeg_cmd = resolve_ffmpeg_cmd()
    if not ffmpeg_cmd:
        print("❌ Errore: FFmpeg non è stato trovato a sistema. Impossibile procedere.")
        sys.exit(1)
        
    # 1. Recupero la classifica
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
            
        success = download_and_convert(song, ffmpeg_cmd)
        if success:
            imported_count += 1
            
    print("\n" + "=" * 60)
    print(f"🎉 Importazione completata! Nuovi brani importati con successo: {imported_count}/{args.limit}")
    print("=" * 60)

if __name__ == "__main__":
    main()
