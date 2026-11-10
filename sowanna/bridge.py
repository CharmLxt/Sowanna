"""Управление процессом Bridge.exe через stdin/stdout."""
import subprocess
import threading
from pathlib import Path

from .protocol import (
    ProtocolError, make_request, encode, decode, parse_response,
)


class BridgeProcess:
    """Долгоживущий процесс Bridge.exe. Потокобезопасен (сериализует вызовы)."""

    def __init__(self, bridge_exe, assembly_path, entry_class,
                 timeout=60.0, callbacks=None):
        self.bridge_exe = Path(bridge_exe)
        self.assembly_path = Path(assembly_path)
        self.entry_class = entry_class
        self.timeout = timeout
        self._proc = None
        self._lock = threading.RLock()
        self._req_counter = 0
        self._stderr_buffer = []
        self._callbacks = callbacks if callbacks is not None else {}

    def start(self):
        if self.is_running():
            return
        if not self.bridge_exe.exists():
            raise FileNotFoundError(f"Bridge.exe не найден: {self.bridge_exe}")
        if not self.assembly_path.exists():
            raise FileNotFoundError(f"Сборка не найдена: {self.assembly_path}")

        self._proc = subprocess.Popen(
            [
                str(self.bridge_exe),
                "--assembly", str(self.assembly_path),
                "--entry", self.entry_class,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        self._stderr_buffer = []
        self._drain_stderr()

    def _drain_stderr(self):
        if self._proc is None or self._proc.stderr is None:
            return

        def _reader():
            try:
                for line in self._proc.stderr:
                    self._stderr_buffer.append(line)
                    if len(self._stderr_buffer) > 200:
                        self._stderr_buffer = self._stderr_buffer[-200:]
            except Exception:
                pass

        threading.Thread(target=_reader, daemon=True).start()

    def _write_line(self, text):
        try:
            self._proc.stdin.write(text)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise ProtocolError(
                f"не удалось записать в Bridge: {e}\n"
                f"stderr: {''.join(self._stderr_buffer)[-500:]}"
            )

    def _read_line(self):
        line = self._proc.stdout.readline()
        if not line:
            err_text = "".join(self._stderr_buffer)[-1000:]
            raise ProtocolError(
                f"Bridge умер без ответа. stderr: {err_text or '<пусто>'}"
            )
        return line

    def _handle_callback(self, obj):
        cb_id = obj.get("callback_id")
        name = obj.get("name")
        args = obj.get("args", [])
        if not isinstance(args, list):
            args = []

        handler = self._callbacks.get(name)
        if handler is None:
            resp = {
                "kind": "callback_result",
                "callback_id": cb_id,
                "error": {
                    "type": "UnknownCallback",
                    "message": f"нет зарегистрированного Python-callback '{name}'",
                },
            }
        else:
            try:
                result = handler(*args)
                resp = {
                    "kind": "callback_result",
                    "callback_id": cb_id,
                    "result": result,
                }
            except Exception as e:
                resp = {
                    "kind": "callback_result",
                    "callback_id": cb_id,
                    "error": {"type": type(e).__name__, "message": str(e)},
                }

        try:
            line = encode(resp)
        except (TypeError, ValueError) as e:
            line = encode({
                "kind": "callback_result",
                "callback_id": cb_id,
                "error": {
                    "type": "SerializationError",
                    "message": f"Python-callback вернул не-JSON-значение: {e}",
                },
            })
        self._write_line(line)

    def call(self, method, *args):
        with self._lock:
            if not self.is_running():
                raise ProtocolError("Bridge процесс не запущен или умер")
            self._req_counter += 1
            req = make_request(method, args, req_id=self._req_counter)
            self._write_line(encode(req))

            while True:
                line = self._read_line()
                obj = decode(line)
                kind = obj.get("kind", "response")
                if kind == "callback":
                    self._handle_callback(obj)
                    continue
                return parse_response(obj)

    def stop(self):
        if self._proc is None:
            return
        if self._proc.poll() is None:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None

    def is_running(self):
        return self._proc is not None and self._proc.poll() is None

    def get_stderr_tail(self, n=50):
        return "".join(self._stderr_buffer[-n:])

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False

    def __repr__(self):
        status = "running" if self.is_running() else "stopped"
        return f"<BridgeProcess {status} exe={self.bridge_exe.name} entry={self.entry_class}>"


__all__ = ["BridgeProcess"]