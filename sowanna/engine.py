"""Общее ядро Sowanna: находит Bridge.exe, поднимает процесс, вызывает методы."""
import os
import shutil
from pathlib import Path

from .manifest import Manifest
from .bridge import BridgeProcess
from .protocol import BridgeError, ProtocolError


class SowannaError(Exception):
    """Базовое исключение Sowanna."""
    pass


class MissingManifestError(SowannaError):
    """Манифест не найден или повреждён."""
    pass


class BridgeNotBuiltError(SowannaError):
    """Bridge.exe ещё не собран — нужно выполнить bridge/build.ps1."""
    pass


class MethodNotDeclaredError(SowannaError):
    """Вызван метод, которого нет в манифесте (и запрещён auto-discovery)."""
    pass


class BridgeCrashedError(SowannaError):
    """Bridge.exe упал и не может быть перезапущен."""
    pass


class Engine:
    """Долгоживущий движок. Один Bridge.exe на Engine."""

    def __init__(self, manifest, bridge_exe=None, auto_discover=True,
                 callbacks=None):
        if isinstance(manifest, (str, os.PathLike)):
            try:
                manifest = Manifest.from_file(manifest)
            except (FileNotFoundError, ValueError) as e:
                raise MissingManifestError(str(e))
        if not isinstance(manifest, Manifest):
            raise TypeError(
                f"manifest должен быть Manifest или путь, "
                f"а не {type(manifest).__name__}"
            )

        self.manifest = manifest
        self.auto_discover = auto_discover
        self._bridge = None
        self._callbacks = dict(callbacks) if callbacks else {}

        if bridge_exe is None:
            bridge_exe = self._find_bridge_exe()
        self.bridge_exe = Path(bridge_exe)

    def _find_bridge_exe(self):
        here = Path(__file__).parent
        candidates = [
            here / "_bridge" / "Bridge.exe",
            here / "_bridge" / "Bridge",
            here / "_bridge" / "Bridge.dll",
        ]
        for c in candidates:
            if c.exists():
                return c

        on_path = shutil.which("Bridge.exe") or shutil.which("Bridge")
        if on_path:
            return Path(on_path)

        raise BridgeNotBuiltError(
            "Bridge.exe не найден. Соберите его один раз:\n"
            "    cd Sowanna\\bridge\n"
            "    .\\build.ps1\n"
            "Или передайте bridge_exe=... явно."
        )

    # ---------- Callbacks ----------

    def register_callback(self, name, func):
        if not callable(func):
            raise TypeError(f"callback должен быть callable, получено {type(func).__name__}")
        self._callbacks[str(name)] = func
        return func

    def unregister_callback(self, name):
        return self._callbacks.pop(str(name), None) is not None

    def list_callbacks(self):
        return list(self._callbacks.keys())

    # ---------- Вызов ----------

    def _ensure_running(self):
        if self._bridge is None:
            self._bridge = BridgeProcess(
                self.bridge_exe,
                self.manifest.resolve_assembly(),
                self.manifest.entry_class,
                callbacks=self._callbacks,
            )
            self._bridge.start()
        elif not self._bridge.is_running():
            self._bridge.start()
        return self._bridge

    def call(self, method, *args):
        method = str(method)
        if not self.auto_discover and method not in self.manifest.methods:
            raise MethodNotDeclaredError(
                f"метод '{method}' не объявлен в манифесте, "
                f"а auto_discover=False. Объявите его в .pycsh."
            )
        bridge = self._ensure_running()
        try:
            return bridge.call(method, *args)
        except ProtocolError:
            try:
                bridge.stop()
            except Exception:
                pass
            try:
                bridge = self._ensure_running()
                return bridge.call(method, *args)
            except Exception as e:
                raise BridgeCrashedError(
                    f"Bridge упал при вызове '{method}' и не восстановился: {e}"
                )

    def stop(self):
        if self._bridge is not None:
            self._bridge.stop()
            self._bridge = None

    def is_running(self):
        return self._bridge is not None and self._bridge.is_running()

    def __enter__(self):
        self._ensure_running()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False

    def __repr__(self):
        status = "running" if self.is_running() else "stopped"
        return (
            f"<Engine {status} manifest={self.manifest.name} "
            f"bridge={self.bridge_exe.name} callbacks={len(self._callbacks)}>"
        )


__all__ = [
    "SowannaError",
    "MissingManifestError",
    "BridgeNotBuiltError",
    "MethodNotDeclaredError",
    "BridgeCrashedError",
    "Engine",
]