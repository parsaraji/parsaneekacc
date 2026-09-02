import os
import shutil
from datetime import datetime
from typing import List, Optional

class BackupManager:
    def __init__(self, db_path: str, backup_dir: str = "backups"):
        self.db_path = db_path
        self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self) -> str:
        """
        Creates a timestamped copy of the SQLite database file in backup_dir.
        Returns the absolute path to the newly created backup file.
        """
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found at {self.db_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"parsanik_backup_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def rotate_backups(self, max_keep: int = 10) -> List[str]:
        """
        Retains the last `max_keep` backup files and removes older ones.
        Returns list of removed file paths.
        """
        if not os.path.exists(self.backup_dir):
            return []

        backups = []
        for fname in os.listdir(self.backup_dir):
            if fname.startswith("parsanik_backup_") and fname.endswith(".db"):
                full_path = os.path.join(self.backup_dir, fname)
                backups.append((os.path.getmtime(full_path), full_path))

        # Sort by modification time ascending
        backups.sort(key=lambda x: x[0])

        removed = []
        if len(backups) > max_keep:
            to_remove = backups[:len(backups) - max_keep]
            for _, path in to_remove:
                try:
                    os.remove(path)
                    removed.append(path)
                except Exception:
                    pass

        return removed

    def restore_backup(self, backup_file_path: str) -> bool:
        """
        Restores database from a given backup file.
        Overwrites current db_path.
        """
        if not os.path.exists(backup_file_path):
            raise FileNotFoundError(f"Backup file not found at {backup_file_path}")

        # Create emergency temp backup of current before overwrite
        temp_backup = self.db_path + ".temp_bak"
        if os.path.exists(self.db_path):
            shutil.copy2(self.db_path, temp_backup)

        try:
            shutil.copy2(backup_file_path, self.db_path)
            if os.path.exists(temp_backup):
                os.remove(temp_backup)
            return True
        except Exception as e:
            # Revert on failure
            if os.path.exists(temp_backup):
                shutil.copy2(temp_backup, self.db_path)
                os.remove(temp_backup)
            raise e
