"""Манифест Sowanna: формат .pycsh, парсинг, валидация, сохранение."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


MANIFEST_EXT = ".pycsh"


@dataclass
class MethodSpec:
    """Описание одного публичного метода C#-класса."""
    name: str
    args: list = field(default_factory=list)
    returns: Optional[str] = None
    description: str = ""

    def to_dict(self):
        return {
            "args": list(self.args),
            "returns": self.returns,
            "description": self.description,
        }


@dataclass
class Manifest:
    """Манифест проекта Sowanna."""
    name: str
    assembly: str
    entry_class: str
    version: str = "0.0.0"
    description: str = ""
    framework: str = "net6.0"
    mode: str = "auto"
    methods: dict = field(default_factory=dict)
    source_dir: Optional[str] = None
    _path: Optional[Path] = None

    # ---------- Загрузка ----------

    @classmethod
    def from_file(cls, path):
        path = Path(path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Манифест не найден: {path}")
        try:
            data = json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Манифест {path.name} повреждён: {e}")
        if not isinstance(data, dict):
            raise ValueError(f"Манифест {path.name} должен быть JSON-объектом")

        for required in ("name", "assembly", "entry_class"):
            if required not in data:
                raise ValueError(f"В {path.name} отсутствует поле '{required}'")

        methods_raw = data.get("methods", {})
        methods = {}
        if isinstance(methods_raw, dict):
            for m_name, m_spec in methods_raw.items():
                if isinstance(m_spec, dict):
                    methods[m_name] = MethodSpec(
                        name=m_name,
                        args=list(m_spec.get("args", [])),
                        returns=m_spec.get("returns"),
                        description=m_spec.get("description", ""),
                    )
                else:
                    methods[m_name] = MethodSpec(name=m_name)

        return cls(
            name=str(data["name"]),
            assembly=str(data["assembly"]),
            entry_class=str(data["entry_class"]),
            version=str(data.get("version", "0.0.0")),
            description=str(data.get("description", "")),
            framework=str(data.get("framework", "net6.0")),
            mode=str(data.get("mode", "auto")),
            methods=methods,
            source_dir=data.get("source_dir"),
            _path=path.resolve(),
        )

    @classmethod
    def from_dict(cls, data):
        """Создаёт манифест из словаря (без файла — путь будет None)."""
        for required in ("name", "assembly", "entry_class"):
            if required not in data:
                raise ValueError(f"В словаре отсутствует поле '{required}'")
        methods_raw = data.get("methods", {})
        methods = {}
        if isinstance(methods_raw, dict):
            for m_name, m_spec in methods_raw.items():
                if isinstance(m_spec, dict):
                    methods[m_name] = MethodSpec(
                        name=m_name,
                        args=list(m_spec.get("args", [])),
                        returns=m_spec.get("returns"),
                        description=m_spec.get("description", ""),
                    )
                else:
                    methods[m_name] = MethodSpec(name=m_name)
        return cls(
            name=str(data["name"]),
            assembly=str(data["assembly"]),
            entry_class=str(data["entry_class"]),
            version=str(data.get("version", "0.0.0")),
            description=str(data.get("description", "")),
            framework=str(data.get("framework", "net6.0")),
            mode=str(data.get("mode", "auto")),
            methods=methods,
            source_dir=data.get("source_dir"),
            _path=None,
        )

    # ---------- Пути ----------

    def resolve_assembly(self):
        """Возвращает абсолютный путь к .dll сборки, если манифест привязан к файлу."""
        if self._path is None:
            raise ValueError("Манифест не привязан к файлу — путь к сборке неизвестен")
        return (self._path.parent / self.assembly).resolve()

    @property
    def manifest_path(self):
        return self._path

    # ---------- Сохранение ----------

    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "assembly": self.assembly,
            "entry_class": self.entry_class,
            "framework": self.framework,
            "mode": self.mode,
            "methods": {k: v.to_dict() for k, v in self.methods.items()},
        }

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            "utf-8",
        )
        self._path = path.resolve()
        return path

    # ---------- Валидация ----------

    def validate(self, check_files=False):
        """Проверяет манифест. Возвращает (ok, list_of_errors)."""
        errors = []
        if not self.name:
            errors.append("name пустой")
        if not self.entry_class or "." not in self.entry_class:
            errors.append(
                "entry_class должен быть полным именем класса (Namespace.Class)"
            )
        if not self.assembly.lower().endswith((".dll", ".exe")):
            errors.append("assembly должен быть .dll или .exe")
        if self.mode not in ("auto", "fast", "safe"):
            errors.append(f"mode='{self.mode}' — допустимо только auto/fast/safe")

        if check_files and self._path is not None:
            try:
                asm_path = self.resolve_assembly()
            except ValueError as e:
                errors.append(str(e))
            else:
                if not asm_path.exists():
                    errors.append(f"Сборка не найдена: {asm_path}")

        return (len(errors) == 0, errors)

    def __repr__(self):
        path_str = str(self._path) if self._path else "<no file>"
        return (
            f"<Manifest {self.name} v{self.version} "
            f"assembly={self.assembly} entry={self.entry_class} "
            f"methods={len(self.methods)} path={path_str}>"
        )


__all__ = ["MANIFEST_EXT", "MethodSpec", "Manifest"]