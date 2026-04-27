import json
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"


def post_analyze() -> dict[str, Any]:
    response = requests.post(
        f"{BASE_URL}/api/v1/analyze",
        json={
            "raw_text": "Тестовая боль клиента",
            "source": "test",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_history() -> dict[str, Any]:
    response = requests.get(
        f"{BASE_URL}/api/v1/history",
        params={
            "source": "test",
            "limit": 10,
            "offset": 0,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    analyze_result = post_analyze()
    print("Analyze response:")
    print(json.dumps(analyze_result, ensure_ascii=False, indent=2))

    history_result = get_history()
    print("\nHistory response:")
    print(json.dumps(history_result, ensure_ascii=False, indent=2))

    saved = any(item["id"] == analyze_result["id"] for item in history_result["items"])
    print(f"\nSaved in SQLite: {saved}")


if __name__ == "__main__":
    main()
