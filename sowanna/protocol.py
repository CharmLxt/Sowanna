"""JSON-Lines протокол между Python и Bridge.exe.

Один запрос = одна строка JSON, один ответ = одна строка JSON.
Направление всегда один-к-одному: клиент пишет, читает ответ, пишет следующий.
"""
import json
import uuid


class ProtocolError(Exception):
    """Ошибка самого протокола (невалидный JSON, обрыв, рассинхронизация)."""
    pass


class BridgeError(Exception):
    """Ошибка, которую вернул Bridge.exe (исключение в C#-коде)."""

    def __init__(self, csharp_type, message, stack=None):
        self.csharp_type = csharp_type
        self.message = message
        self.stack = stack
        super().__init__(f"{csharp_type}: {message}")

    def __str__(self):
        out = f"{self.csharp_type}: {self.message}"
        if self.stack:
            out += f"\nC# stack trace:\n{self.stack}"
        return out


def make_request(method, args, req_id=None):
    """Формирует словарь-запрос."""
    if req_id is None:
        req_id = str(uuid.uuid4())
    return {"id": req_id, "method": str(method), "args": list(args)}


def encode(obj):
    """Кодирует dict в строку JSON + перевод строки (для записи в stdin)."""
    return json.dumps(obj, ensure_ascii=False) + "\n"


def decode(line):
    """Декодирует одну строку в dict. Пустые строки → ProtocolError."""
    line = line.strip()
    if not line:
        raise ProtocolError("пустая строка от Bridge")
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"невалидный JSON от Bridge: {e} (строка: {line[:200]!r})")
    if not isinstance(obj, dict):
        raise ProtocolError(f"от Bridge пришёл не JSON-объект: {type(obj).__name__}")
    return obj


def parse_response(obj):
    """Извлекает result из ответа. Если error — бросает BridgeError."""
    if "error" in obj and obj["error"] is not None:
        err = obj["error"]
        if not isinstance(err, dict):
            raise ProtocolError(f"поле error должно быть объектом: {err!r}")
        raise BridgeError(
            err.get("type", "BridgeError"),
            err.get("message", "unknown error"),
            err.get("stack"),
        )
    return obj.get("result")


__all__ = [
    "ProtocolError", "BridgeError",
    "make_request", "encode", "decode", "parse_response",
]