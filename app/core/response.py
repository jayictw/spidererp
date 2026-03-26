from typing import Any


def success_response(data: Any = None, message: str = "") -> dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def error_response(error: str, message: str = "") -> dict[str, Any]:
    return {"success": False, "error": error, "message": message}

