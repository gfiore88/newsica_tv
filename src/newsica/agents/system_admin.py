import os
import shutil
import time
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent.parent
RUNTIME_DIR = BASE_DIR / "runtime"
ASSETS_DIR = RUNTIME_DIR / "assets"

class SystemAdminAgent:
    def __init__(self):
        self._ensure_asset_dirs()
        
    def _ensure_asset_dirs(self):
        for d in ["planned", "preparing", "ready", "queued", "aired", "failed", "archive"]:
            (ASSETS_DIR / d).mkdir(parents=True, exist_ok=True)
            
    def _manifest_matches(self, ready_dir, character=None, title=None):
        manifest_path = ready_dir / "manifest.json"
        if not manifest_path.exists():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        if character and manifest.get("character") != character:
            return False
        if title and manifest.get("title") != title:
            return False
        return True

    def prepare_slot(self, slot_time, character=None, title=None):
        """Prepara la cartella per l'asset in generazione e previene le race condition."""
        slot_id = slot_time.replace(":", "")
        ready_dir = ASSETS_DIR / "ready" / slot_id
        preparing_dir = ASSETS_DIR / "preparing" / slot_id
        
        if ready_dir.exists():
            if not self._manifest_matches(ready_dir, character=character, title=title):
                stale_dir = ASSETS_DIR / "archive" / f"{slot_id}_stale_{int(time.time())}"
                if stale_dir.exists():
                    shutil.rmtree(stale_dir)
                ready_dir.rename(stale_dir)
                print(f"♻️ [SystemAdminAgent] Asset pronto per {slot_time} non coerente col palinsesto attuale. Rigenero.")
            else:
                return None, "L'asset è già pronto."
            
        if ready_dir.exists():
            return None, "L'asset è già pronto."
            
        if preparing_dir.exists():
            return None, "L'asset è già in preparazione."
            
        preparing_dir.mkdir(parents=True, exist_ok=True)
        return preparing_dir, "OK"
        
    def commit_assets(self, slot_time, audio_files, preparing_dir, metadata=None):
        """Sposta i file validati nella cartella ready."""
        slot_id = slot_time.replace(":", "")
        ready_dir = ASSETS_DIR / "ready" / slot_id
        
        try:
            for f in audio_files:
                shutil.copy(f, preparing_dir / f.name)
            if metadata:
                (preparing_dir / "manifest.json").write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                
            if ready_dir.exists():
                shutil.rmtree(ready_dir)
            preparing_dir.rename(ready_dir)
            print(f"✅ [SystemAdminAgent] Asset per {slot_time} pronto in {ready_dir.name}")
        except Exception as e:
            self.fail_slot(slot_time, preparing_dir, error=str(e))
            raise
            
    def fail_slot(self, slot_time, preparing_dir, error=""):
        """Gestisce il fallimento spostando in failed."""
        print(f"❌ [SystemAdminAgent] Errore generazione per {slot_time}: {error}")
        slot_id = slot_time.replace(":", "")
        failed_dir = ASSETS_DIR / "failed" / slot_id
        
        if failed_dir.exists():
            shutil.rmtree(failed_dir)
        if preparing_dir.exists():
            preparing_dir.rename(failed_dir)
            
    def cleanup_old_assets(self, max_age_hours=24):
        """Pulisce le vecchie directory per evitare l'esaurimento dello spazio."""
        now = time.time()
        for status_dir in ["ready", "queued", "aired", "failed", "archive"]:
            dir_path = ASSETS_DIR / status_dir
            if not dir_path.exists():
                continue
                
            for slot_dir in dir_path.iterdir():
                if not slot_dir.is_dir():
                    continue
                age = now - slot_dir.stat().st_mtime
                if age > (max_age_hours * 3600):
                    try:
                        shutil.rmtree(slot_dir)
                        print(f"🧹 [SystemAdminAgent] Rimossa vecchia cartella: {slot_dir}")
                    except Exception:
                        pass
