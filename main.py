"""
Airganizator - LLM CLI Orchestrator
Запуск: python main.py
"""
import uvicorn
import signal
import sys


def handle_exit(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n[INFO] Shutting down...")
    sys.exit(0)


def main():
    # Register signal handlers for Windows
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        uvicorn.run(
            "backend.app:app",
            host="127.0.0.1",
            port=6680,
            reload=False,  # Disable reload for proper Ctrl+C handling on Windows
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped")


if __name__ == "__main__":
    main()
