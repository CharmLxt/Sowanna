"""Три фасада Sowanna: VovSC, UniPlcahCSC, minpyAovCS."""
import time
from pathlib import Path

from .engine import (
    Engine, SowannaError, BridgeCrashedError,
    BridgeNotBuiltError, MissingManifestError,
)
from .manifest import Manifest, MANIFEST_EXT
from .protocol import BridgeError


# ============================================================
# VovSC — универсальный
# ============================================================

class VovSC:
    """Универсальный фасад. Один процесс Bridge.exe на инстанс."""

    def __init__(self, manifest, bridge_exe=None, auto_discover=True):
        self.engine = Engine(manifest, bridge_exe=bridge_exe,
                             auto_discover=auto_discover)
        self.manifest = self.engine.manifest

    def call(self, method, *args):
        return self.engine.call(method, *args)

    def register_callback(self, name, func):
        return self.engine.register_callback(name, func)

    def unregister_callback(self, name):
        return self.engine.unregister_callback(name)

    def list_callbacks(self):
        return self.engine.list_callbacks()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        def caller(*args):
            return self.engine.call(name, *args)
        return caller

    def __dir__(self):
        base = list(super().__dir__())
        return base + list(self.manifest.methods.keys())

    def stop(self):
        self.engine.stop()

    def __enter__(self):
        self.engine._ensure_running()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False

    def __repr__(self):
        return (
            f"<VovSC manifest={self.manifest.name} "
            f"methods={len(self.manifest.methods)}>"
        )


# ============================================================
# UniPlcahCSC — всегда новый процесс, с circuit breaker
# ============================================================

class UniPlcahCSC:
    """Изолированный фасад: каждый вызов — новый Bridge.exe."""

    def __init__(self, manifest, bridge_exe=None,
                 max_failures=3, cooldown=30.0, timeout=60.0):
        if isinstance(manifest, (str, Path)):
            try:
                manifest = Manifest.from_file(manifest)
            except (FileNotFoundError, ValueError) as e:
                raise MissingManifestError(str(e))
        self.manifest = manifest

        proto = Engine(manifest, bridge_exe=bridge_exe)
        self.bridge_exe = proto.bridge_exe
        proto.stop()

        self.max_failures = int(max_failures)
        self.cooldown = float(cooldown)
        self.timeout = float(timeout)
        self._failures = 0
        self._open_until = 0.0
        self._callbacks = {}

    def register_callback(self, name, func):
        if not callable(func):
            raise TypeError(f"callback должен быть callable, получено {type(func).__name__}")
        self._callbacks[str(name)] = func
        return func

    def unregister_callback(self, name):
        return self._callbacks.pop(str(name), None) is not None

    def list_callbacks(self):
        return list(self._callbacks.keys())

    def _circuit_check(self):
        if self._failures < self.max_failures:
            return
        remaining = self._open_until - time.time()
        if remaining > 0:
            raise BridgeCrashedError(
                f"circuit breaker открыт ещё {remaining:.0f} сек "
                f"({self._failures} падений подряд). Подождите или вызовите reset_circuit()."
            )
        self._failures = 0
        self._open_until = 0.0

    def _record_failure(self):
        self._failures += 1
        if self._failures >= self.max_failures:
            self._open_until = time.time() + self.cooldown

    def _record_success(self):
        self._failures = 0
        self._open_until = 0.0

    def call(self, method, *args):
        self._circuit_check()
        engine = Engine(
            self.manifest,
            bridge_exe=self.bridge_exe,
            auto_discover=True,
            callbacks=self._callbacks,
        )
        try:
            try:
                result = engine.call(method, *args)
            finally:
                engine.stop()
            self._record_success()
            return result
        except (BridgeError, SowannaError) as e:
            self._record_failure()
            raise

    def reset_circuit(self):
        self._failures = 0
        self._open_until = 0.0

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        def caller(*args):
            return self.call(name, *args)
        return caller

    def __repr__(self):
        return (
            f"<UniPlcahCSC manifest={self.manifest.name} "
            f"failures={self._failures}/{self.max_failures}>"
        )


# ============================================================
# minpyAovCS — C#-первый, автогенерация манифеста
# ============================================================

class minpyAovCS:
    """C#-первый фасад: даёте .dll + entry_class, получаете рабочий мост."""

    def __init__(self, manifest, bridge_exe=None):
        if isinstance(manifest, (str, Path)):
            try:
                manifest = Manifest.from_file(manifest)
            except (FileNotFoundError, ValueError) as e:
                raise MissingManifestError(str(e))
        self.manifest = manifest
        self.engine = Engine(manifest, bridge_exe=bridge_exe, auto_discover=True)

    @classmethod
    def from_assembly(cls, dll_path, entry_class, name=None,
                      version="0.1.0", framework="net6.0",
                      bridge_exe=None, write_manifest=True):
        dll = Path(dll_path).resolve()
        if not dll.exists():
            raise FileNotFoundError(f"Сборка не найдена: {dll}")

        if name is None:
            name = dll.stem
        if "." not in entry_class:
            raise ValueError(
                f"entry_class должен быть полным (Namespace.Class), "
                f"получено: {entry_class!r}"
            )

        manifest_path = dll.parent / (dll.stem + MANIFEST_EXT)
        manifest = Manifest(
            name=name,
            assembly=dll.name,
            entry_class=entry_class,
            version=version,
            framework=framework,
            mode="auto",
            methods={},
            _path=manifest_path,
        )
        if write_manifest:
            manifest.save(manifest_path)
        return cls(manifest, bridge_exe=bridge_exe)

    def call(self, method, *args):
        return self.engine.call(method, *args)

    def register_callback(self, name, func):
        return self.engine.register_callback(name, func)

    def unregister_callback(self, name):
        return self.engine.unregister_callback(name)

    def list_callbacks(self):
        return self.engine.list_callbacks()

    def __getattr__(self, attr_name):
        if attr_name.startswith("_"):
            raise AttributeError(attr_name)
        def caller(*args):
            return self.engine.call(attr_name, *args)
        return caller

    def stop(self):
        self.engine.stop()

    def __enter__(self):
        self.engine._ensure_running()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False

    def __repr__(self):
        return (
            f"<minpyAovCS manifest={self.manifest.name} "
            f"entry={self.manifest.entry_class}>"
        )


__all__ = ["VovSC", "UniPlcahCSC", "minpyAovCS"]