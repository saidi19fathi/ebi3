#!/usr/bin/env python3
import os
import glob

def restore_backups():
    backup_files = glob.glob("**/*.backup", recursive=True)

    if not backup_files:
        print("Aucun fichier backup trouvé.")
        return

    print(f"Trouvé {len(backup_files)} fichier(s) backup :")

    for backup_file in backup_files:
        original_file = backup_file.replace('.backup', '')

        if os.path.exists(backup_file) and os.path.exists(original_file):
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                os.remove(backup_file)
                print(f"✓ Restauré : {original_file}")
            except Exception as e:
                print(f"✗ Erreur : {original_file} - {e}")

    print("\nRestauration terminée.")

if __name__ == "__main__":
    restore_backups()
