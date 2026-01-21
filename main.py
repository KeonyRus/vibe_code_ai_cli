"""
Airganizator - LLM CLI Orchestrator
Запуск: python main.py
"""
import uvicorn


def main():
    uvicorn.run(
        "backend.app:app",
        host="127.0.0.1",
        port=6680,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
