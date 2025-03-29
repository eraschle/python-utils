## Environment Backup and Restore Script

Dieses Skript ermöglicht das Sichern und Wiederherstellen von Umgebungsvariablen, mit optionaler Integration von 1Password zur Verwaltung von Geheimnissen.

### Abhängigkeiten

Bevor Sie dieses Skript verwenden, stellen Sie sicher, dass Sie die folgenden Abhängigkeiten installiert haben.

**Python:**

- Python 3.12 oder höher
  - Sie können Python von [python.org](https://www.python.org/downloads/) herunterladen.

**Python-Bibliotheken:**

Die Bibliotheken müssen nur installiert werden, wenn das Skript in einer IDE angepasst wird und Typechecking Funktionen gewünscht sind.

- `click` und `1password` Bibliotheken: Installieren Sie diese mit `uv`.
  ```bash
  uv add add click 1password
  ```
- 1Password CLI (op): Installieren Sie gemäß der 1Password-Dokumentation, wenn Sie die 1Password-Integration nutzen möchten.
  - Folgen Sie den Installationsanweisungen für Ihr Betriebssystem in der [1Password CLI-Dokumentation](https://developer.1password.com/docs/cli/).
  - Stellen Sie sicher, dass der `op`-Befehl in Ihrem System-PATH verfügbar ist.

### Befehle

Dieses Skript bietet die folgenden Befehle zur Verwaltung von Umgebungsvariablen:

**1. Backup**

   Der `backup`-Befehl speichert Ihre aktuellen Umgebungsvariablen in einer JSON-Datei. Er kann optional Variablen herausfiltern, deren Werte in Ihrem 1Password-Vault gefunden werden, und ignoriert auch eine vordefinierte Liste von gängigen und sensiblen Umgebungsvariablen.

   ```bash
   uv run env_backup_restore.py backup --env-file <pfad_zur_env_datei.json>
   ```

   **Optionen:**

   - `--env-file <pfad_zur_env_datei.json>`: 
   *(Erforderlich)* 
   Pfad zur JSON-Datei, in der Umgebungsvariablen gespeichert werden.
   - `--check-1password`: 
   *(Optional)* 
   Aktiviert die Überprüfung von Umgebungsvariablenwerten gegen Elemente in Ihrem 1Password-Vault. Wenn aktiviert, werden Variablen mit Werten, die in 1Password gefunden werden, in der Backup-Datei redigiert.
   - `--op-vault <VAULT_NAME>`: 
   *(Optional, aber erforderlich, wenn `--check-1password` verwendet wird)* 
   Der Name Ihres 1Password-Vaults für die Überprüfung.

   **Beispiel:**
   ```bash
   uv run env_backup_restore.py backup --env-file env_backup.json --check-1password --op-vault "Mein Vault"
   ```

**2. Restore**

   Der `restore`-Befehl liest Umgebungsvariablen aus einer JSON-Backup-Datei und gibt `export`-Befehle aus, um sie in Ihrer Shell zu setzen. Wenn die Backup-Datei redigierte Werte enthält (aufgrund der 1Password-Integration während des Backups), versucht er, die ursprünglichen Geheimnisse aus Ihrem 1Password-Vault abzurufen.

   **Wichtig:** Dieser Befehl gibt Shell-Befehle aus. Um diese Variablen auf Ihre aktuelle Shell-Sitzung anzuwenden, müssen Sie `eval` verwenden.

   ```bash
   uv run env_backup_restore.py restore --env-file <pfad_zur_env_datei.json> --op-vault <VAULT_NAME>
   ```

   **Optionen:**

   - `--env-file <pfad_zur_env_datei.json>`: *(Erforderlich)* Pfad zur JSON-Datei mit den gesicherten Umgebungsvariablen.
   - `--op-vault <VAULT_NAME>`: *(Erforderlich)* Der Name Ihres 1Password-Vaults. Dies wird verwendet, um redigierte Geheimnisse abzurufen.

   **Beispiel:**
   ```bash
   eval "$(uv run env_backup_restore.py restore --env-file env_backup.json --op-vault "Mein Vault")"
   ```

**3. Apply**

   Der `apply`-Befehl ähnelt `restore`, gibt jedoch keine `export`-Befehle aus, sondern wendet die Umgebungsvariablen direkt auf den aktuellen Python-Prozess mit `os.environ` an. Dies ist nützlich, wenn Sie Umgebungsvariablen für nachfolgende Python-Skripte oder Operationen innerhalb derselben Sitzung setzen möchten.

   ```bash
   uv run env_backup_restore.py apply --env-file <pfad_zur_env_datei.json> --op-vault <VAULT_NAME>
   ```

   **Optionen:**

   - `--env-file <pfad_zur_env_datei.json>`: *(Erforderlich)* Pfad zur JSON-Datei mit den gesicherten Umgebungsvariablen.
   - `--op-vault <VAULT_NAME>`: *(Erforderlich)* Der Name Ihres 1Password-Vaults. Dies wird verwendet, um redigierte Geheimnisse abzurufen.

   **Beispiel:**
   ```bash
   uv run env_backup_restore.py apply --env-file env_backup.json --op-vault "Mein Vault"
   ```

### Nutzungshinweise

- **1Password-Integration:** Damit die 1Password-Integration korrekt funktioniert, stellen Sie sicher, dass Sie bei der 1Password CLI angemeldet sind (`op login`) und dass der angegebene Vault-Name korrekt ist.
- **Redigierte Geheimnisse:** Bei Verwendung von `--check-1password` während des Backups wird jeder Umgebungsvariablenwert, der mit einem Elementwert in Ihrem 1Password-Vault übereinstimmt, in der Backup-Datei durch `MEIN-GEHEIMNISS` ersetzt. Das eigentliche Geheimnis wird *nicht* in der Backup-Datei gespeichert.
- **Sicherheit:** Achten Sie darauf, wo Sie Ihre Umgebungs-Backup-Dateien speichern, besonders wenn sie sensible Informationen enthalten (auch wenn Geheimnisse redigiert sind). Erwägen Sie gegebenenfalls die Verschlüsselung der Backup-Datei.
- **Ignorierte Variablen:** Das Skript ignoriert automatisch eine vordefinierte Liste von gängigen und shell-bezogenen Umgebungsvariablen während des Backups. Diese Liste ist in der Konstante `IGNORED_ENV_VARS` im Skript definiert. Sie können diese Liste bei Bedarf durch direkte Änderung des Skripts anpassen.
- **Eval für Restore:** Denken Sie daran, `eval` mit dem `restore`-Befehl zu verwenden, um die Umgebungsvariablen tatsächlich in Ihrer Shell zu setzen. Ohne `eval` wird der Befehl nur die `export`-Befehle auf die Standardausgabe drucken, und sie werden Ihre Umgebung nicht beeinflussen.
- **Apply für den aktuellen Prozess:** Der `apply`-Befehl wirkt sich nur auf die Umgebung des aktuellen Python-Prozesses und alle davon gestarteten Unterprozesse aus. Er ändert nicht die Umgebung Ihrer Shell oder anderer laufender Prozesse.

### Beitragen

... (Richtlinien für Beiträge können hier hinzugefügt werden)

### Lizenz

... (Lizenzinformationen können hier hinzugefügt werden)
