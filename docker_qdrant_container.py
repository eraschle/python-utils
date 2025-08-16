import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

DOCKER_IMAGE = "qdrant/qdrant:latest"
CONTAINER_NAME = "qdrant-indexer"


def log_message(message):
    """Log to stderr (wird nicht an Claude gesendet)"""
    print(f"[Qdrant Hook] {message}", file=sys.stderr)


def check_qdrant_running():
    """Prüft ob Qdrant Container läuft"""
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=True)
        return CONTAINER_NAME in result.stdout
    except subprocess.CalledProcessError:
        return False


def check_container_exists():
    """Prüft ob der Container existiert (läuft oder gestoppt)"""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        return CONTAINER_NAME in result.stdout
    except subprocess.CalledProcessError:
        return False


def start_existing_container():
    """Startet einen existierenden Container"""
    try:
        result = subprocess.run(
            ["docker", "start", CONTAINER_NAME],
            capture_output=True,
            text=True,
            check=True
        )
        log_message(f"Started existing container: {CONTAINER_NAME}")
        return True
    except subprocess.CalledProcessError as e:
        log_message(f"Failed to start existing container: {e.stderr}")
        return False


def stop_container():
    """Stoppt den Container sauber"""
    try:
        result = subprocess.run(
            ["docker", "stop", CONTAINER_NAME],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        log_message(f"Stopped container: {CONTAINER_NAME}")
        return True
    except subprocess.CalledProcessError as e:
        log_message(f"Failed to stop container: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        log_message("Container stop timed out")
        return False


def remove_container():
    """Entfernt einen existierenden Container"""
    try:
        # Stoppe zuerst den Container falls er läuft
        subprocess.run(
            ["docker", "stop", CONTAINER_NAME],
            capture_output=True,
            text=True,
            timeout=5
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass  # Container ist bereits gestoppt oder existiert nicht
    
    try:
        # Entferne den Container
        result = subprocess.run(
            ["docker", "rm", CONTAINER_NAME],
            capture_output=True,
            text=True,
            check=True
        )
        log_message(f"Removed container: {CONTAINER_NAME}")
        return True
    except subprocess.CalledProcessError:
        return False


def get_container_status():
    """Gibt den Status des Containers zurück"""
    if check_qdrant_running():
        if check_qdrant_health():
            return "running_healthy"
        else:
            return "running_unhealthy"
    elif check_container_exists():
        return "stopped"
    else:
        return "not_exists"


def check_qdrant_health():
    """Prüft ob Qdrant API verfügbar ist"""
    try:
        # Qdrant nutzt Root-Endpoint statt /health
        response = requests.get("http://localhost:6333/", timeout=2)
        # Prüfe ob die Response JSON mit "title": "qdrant" enthält
        if response.status_code == 200:
            data = response.json()
            return "qdrant" in data.get("title", "").lower()
        return False
    except requests.RequestException as e:
        log_message(f"Qdrant health check failed: {e}")
        return False
    except json.JSONDecodeError:
        return False


def create_new_container():
    """Erstellt und startet einen neuen Qdrant Container detached"""
    qdrant_dir = Path.home() / ".config" / "claude-indexer"
    if not qdrant_dir.exists():
        qdrant_dir.mkdir(parents=True, exist_ok=True)
        log_message(f"Created directory: {qdrant_dir}")

    storage_dir = qdrant_dir / "qdrant_storage"

    cmd = [
        "docker",
        "run",
        "-d",  # Detached mode - läuft im Hintergrund
        "--name",
        CONTAINER_NAME,
        "-p",
        "6333:6333",
        "-p",
        "6334:6334",
        "-v",
        f"{storage_dir}:/qdrant/storage:z",
        "--restart",
        "unless-stopped",  # Automatisch neustarten außer manuell gestoppt
        DOCKER_IMAGE,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_message(f"Created new Qdrant container: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        log_message(f"Failed to create Qdrant container: {e.stderr}")
        return False


def ensure_qdrant_running():
    """Stellt sicher dass Qdrant Container läuft"""
    # Prüfe ob Container bereits läuft
    if check_qdrant_running():
        log_message("Container already running")
        return True
    
    # Prüfe ob Container existiert (aber gestoppt ist)
    if check_container_exists():
        log_message("Container exists but stopped, starting...")
        if start_existing_container():
            return True
        else:
            # Falls Start fehlschlägt, Container entfernen und neu erstellen
            log_message("Failed to start existing container, removing and recreating...")
            remove_container()
            return create_new_container()
    
    # Container existiert nicht, neu erstellen
    log_message("Container does not exist, creating new one...")
    return create_new_container()


def wait_for_qdrant(max_wait=30):
    """Wartet bis Qdrant API verfügbar ist"""
    for i in range(max_wait):
        if check_qdrant_health():
            log_message(f"Qdrant ready after {i + 1} seconds")
            return True
        time.sleep(1)
    return False


def handle_start():
    """Behandelt den Start-Modus"""
    # Prüfe ob Qdrant bereits läuft und bereit ist
    if check_qdrant_running() and check_qdrant_health():
        print(json.dumps({"status": "ready", "message": "Qdrant already running", "url": "http://localhost:6333"}))
        return 0

    # Stelle sicher dass Container läuft (startet oder erstellt ihn)
    if not ensure_qdrant_running():
        log_message("Failed to ensure Qdrant is running")
        print(json.dumps({"status": "error", "message": "Failed to start Qdrant container"}))
        return 1

    # Warte bis Qdrant API bereit ist (blockiert nur bis Container bereit)
    if not wait_for_qdrant(max_wait=30):
        log_message("Qdrant container started but API not ready in time")
        print(json.dumps({
            "status": "warning",
            "message": "Container started but API not ready yet",
            "url": "http://localhost:6333"
        }))
        return 1

    print(
        json.dumps(
            {
                "status": "started",
                "message": "Qdrant started successfully",
                "url": "http://localhost:6333",
                "container": CONTAINER_NAME,
            }
        )
    )
    return 0


def handle_stop():
    """Behandelt den Stop-Modus"""
    if not check_container_exists():
        print(json.dumps({"status": "not_found", "message": "Container does not exist"}))
        return 1
    
    if not check_qdrant_running():
        print(json.dumps({"status": "already_stopped", "message": "Container is already stopped"}))
        return 0
    
    if stop_container():
        print(json.dumps({"status": "stopped", "message": "Container stopped successfully"}))
        return 0
    else:
        print(json.dumps({"status": "error", "message": "Failed to stop container"}))
        return 1


def handle_remove():
    """Behandelt den Remove-Modus"""
    if not check_container_exists():
        print(json.dumps({"status": "not_found", "message": "Container does not exist"}))
        return 1
    
    if remove_container():
        print(json.dumps({"status": "removed", "message": "Container removed successfully"}))
        return 0
    else:
        print(json.dumps({"status": "error", "message": "Failed to remove container"}))
        return 1


def handle_status():
    """Behandelt den Status-Modus"""
    status = get_container_status()
    
    status_messages = {
        "running_healthy": {"status": "running", "message": "Container is running and healthy", "url": "http://localhost:6333"},
        "running_unhealthy": {"status": "unhealthy", "message": "Container is running but API not responding"},
        "stopped": {"status": "stopped", "message": "Container exists but is stopped"},
        "not_exists": {"status": "not_found", "message": "Container does not exist"}
    }
    
    print(json.dumps(status_messages.get(status, {"status": "unknown", "message": "Unknown status"})))
    return 0


def main():
    # Argument Parser einrichten
    parser = argparse.ArgumentParser(description="Manage Qdrant Docker container")
    parser.add_argument("--stop", action="store_true", help="Stop the Qdrant container")
    parser.add_argument("--remove", action="store_true", help="Stop and remove the Qdrant container")
    parser.add_argument("--status", action="store_true", help="Check container status")
    
    args = parser.parse_args()
    
    # Bei Claude Hook-Aufruf ohne Argumente: Session-Daten lesen
    if not (args.stop or args.remove or args.status):
        try:
            # Session-Daten von stdin lesen (optional)
            if not sys.stdin.isatty():
                session_data = json.load(sys.stdin)
                log_message(f"Session started from: {session_data.get('source', 'unknown')}")
        except json.JSONDecodeError:
            log_message("Session started (no JSON data)")
    
    # Modus auswählen und ausführen
    if args.stop:
        return handle_stop()
    elif args.remove:
        return handle_remove()
    elif args.status:
        return handle_status()
    else:
        # Standard: Container starten
        return handle_start()


if __name__ == "__main__":
    sys.exit(main())
