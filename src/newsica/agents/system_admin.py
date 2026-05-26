import os
import shutil
import time
import json
from pathlib import Path
from newsica.storage.repositories import asset_slots_repository

BASE_DIR = Path(__file__).parent.parent.parent.parent
RUNTIME_DIR = BASE_DIR / "runtime"
ASSETS_DIR = RUNTIME_DIR / "assets"

class SystemAdminAgent:
    STALE_PREPARING_SECONDS = 30 * 60

    def __init__(self):
        self._ensure_asset_dirs()
        
    def _ensure_asset_dirs(self):
        for d in ["planned", "preparing", "ready", "queued", "aired", "failed", "archive"]:
            (ASSETS_DIR / d).mkdir(parents=True, exist_ok=True)
            
    def _manifest_matches(self, ready_dir, character=None, title=None):
        # 1. Prova a caricare il manifest.json (fallback)
        manifest_path = ready_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if character and manifest.get("character") != character:
                    return False
                if character == "podcast" or manifest.get("character") == "podcast":
                    return True
                if title and manifest.get("title") != title:
                    return False
                return True
            except Exception:
                pass

        # 2. Prova a verificare tramite il database SQLite delle asset_slots
        try:
            slot_id = ready_dir.name
            slot_time = f"{slot_id[:2]}:{slot_id[2:]}" if len(slot_id) == 4 else ""
            if slot_time:
                for row in asset_slots_repository.list_slots():
                    if row.get("slot_time") == slot_time and row.get("character") == character and row.get("status") == "ready":
                        if character == "podcast":
                            return True
                        if title and row.get("title") == title:
                            return True
        except Exception as e:
            print(f"⚠️ Errore durante il riscontro di _manifest_matches via DB slots: {e}")

        # 3. Prova a caricare i metadati dal database audio_metadata
        for audio_file in [ready_dir / "audio.wav", ready_dir / "audio_part1.wav"]:
            if audio_file.exists():
                try:
                    from newsica.storage.repositories.audio_metadata_repository import get_metadata
                    meta_row = get_metadata(str(audio_file.resolve()))
                    if meta_row and meta_row.get("metadata"):
                        meta = meta_row["metadata"]
                        if character and meta.get("character") != character:
                            return False
                        if character == "podcast" or meta.get("character") == "podcast":
                            return True
                        if title and meta.get("title") != title:
                            return False
                        return True
                except Exception:
                    pass

        return False

    def _archive_dir(self, source_dir: Path, suffix: str):
        if not source_dir.exists():
            return
        stale_dir = ASSETS_DIR / "archive" / f"{source_dir.name}_{suffix}_{int(time.time())}"
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
        source_dir.rename(stale_dir)

    def reconcile_asset_slots(self, schedule_data):
        """Ripulisce record DB e cartelle non più coerenti col palinsesto corrente."""
        for row in asset_slots_repository.list_slots():
            slot_time = row.get("slot_time")
            character = row.get("character")
            title = row.get("title")
            status = row.get("status")
            slot_id = slot_time.replace(":", "")
            ready_dir = ASSETS_DIR / "ready" / slot_id
            preparing_dir = ASSETS_DIR / "preparing" / slot_id
            expected = schedule_data.get(slot_time)

            is_podcast = (character == "podcast" or (expected and expected.get("type") == "podcast"))
            title_mismatch = False if is_podcast else (expected.get("title") != title)

            if not expected or expected.get("type") != character or title_mismatch:
                if preparing_dir.exists():
                    self._archive_dir(preparing_dir, "schedule_mismatch")
                if ready_dir.exists():
                    self._archive_dir(ready_dir, "schedule_mismatch")
                asset_slots_repository.delete_slot(slot_time, character)
                print(
                    f"♻️ [SystemAdminAgent] Ripulito asset slot stale {slot_time} "
                    f"({character}/{title}) non coerente col palinsesto attuale."
                )
                continue

            if status == "preparing" and not preparing_dir.exists():
                asset_slots_repository.delete_slot(slot_time, character)
                print(
                    f"♻️ [SystemAdminAgent] Ripulito preparing orfano per {slot_time} "
                    f"({character}/{title}). Verrà rigenerato al prossimo ciclo."
                )

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
            age = time.time() - preparing_dir.stat().st_mtime
            is_empty = not any(preparing_dir.iterdir())
            if age > self.STALE_PREPARING_SECONDS or (is_empty and age > 5 * 60):
                self._archive_dir(preparing_dir, "preparing_stale")
                print(f"♻️ [SystemAdminAgent] Preparazione stale per {slot_time}. Archivio e rigenero.")
            else:
                return None, "L'asset è già in preparazione."

        if preparing_dir.exists():
            return None, "L'asset è già in preparazione."
            
        preparing_dir.mkdir(parents=True, exist_ok=True)

        # Logging to SQLite
        asset_slots_repository.delete_slot(slot_time, character or "unknown")
        asset_slots_repository.upsert_slot(
            slot_time=slot_time,
            character=character or "unknown",
            title=title or "unknown",
            status="preparing"
        )
        
        return preparing_dir, "OK"
        
    def commit_assets(self, slot_time, audio_files, preparing_dir, metadata=None):
        """Sposta i file validati nella cartella ready."""
        slot_id = slot_time.replace(":", "")
        ready_dir = ASSETS_DIR / "ready" / slot_id
        
        try:
            for f in audio_files:
                dest = preparing_dir / f.name
                if f.resolve() != dest.resolve():
                    shutil.copy(f, dest)
                
            if ready_dir.exists():
                shutil.rmtree(ready_dir)
            preparing_dir.rename(ready_dir)
            
            # Logging to SQLite
            asset_slots_repository.upsert_slot(
                slot_time=slot_time,
                character=metadata.get("character", "unknown") if metadata else "unknown",
                title=metadata.get("title", "unknown") if metadata else "unknown",
                status="ready",
                ready_dir=str(ready_dir),
                manifest_path=None
            )
            
            # Salviamo il metadata nel DB audio in modo che il regista non debba leggere file
            if metadata:
                from newsica.storage.repositories.audio_metadata_repository import save_metadata
                save_metadata(
                    file_path=str(ready_dir / "audio.wav"),
                    title=metadata.get("title", "Podcast"),
                    artist=metadata.get("character", "unknown"),
                    metadata=metadata
                )
            
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
            
        # Try to guess character from slot_time or just use 'unknown' 
        # (It will just update if the record exists because of conflict resolution)
        asset_slots_repository.update_status(
            slot_time=slot_time,
            character="unknown", 
            status="failed",
            error=error
        )
        # We might have the actual character in DB, we could do an UPDATE WHERE slot_time = ...
        # Since character is part of the UNIQUE constraint, let's provide a dedicated update
        # Actually, let's use a simpler DB update that ignores character if we don't know it.
        # Wait, the schema is UNIQUE(slot_time, character). If we don't know character here, 
        # let's just do a manual update or pass character down.
        # For now, let's just do it cleanly by updating the error field where slot_time matches.
        try:
            from newsica.storage.database import get_connection
            with get_connection() as conn:
                conn.execute("UPDATE asset_slots SET status = 'failed', error = ? WHERE slot_time = ?", (error, slot_time))
                conn.commit()
        except Exception as e:
            print(f"⚠️ Errore db in fail_slot fallback: {e}")
            
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
