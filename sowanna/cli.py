"""CLI Sowanna: inspect / bridge-info / test-call / stubs."""
import argparse
import sys
from pathlib import Path

from . import charm_enhance as ui
from .manifest import Manifest, MANIFEST_EXT
from .engine import Engine, SowannaError, BridgeNotBuiltError
from .protocol import BridgeError
from .version import __version__


def _cmd_inspect(args):
    path = Path(args.path)
    if path.is_dir():
        candidates = list(path.glob("*" + MANIFEST_EXT))
        if not candidates:
            ui.error(f"В папке {path} нет файлов *{MANIFEST_EXT}")
            return 1
        path = candidates[0]

    try:
        m = Manifest.from_file(path)
    except Exception as e:
        ui.error(f"Не удалось прочитать манифест: {e}")
        return 1

    ok, errors = m.validate(check_files=True)
    print(ui.banner("SOWANNA MANIFEST", f"{m.name} v{m.version}"))
    print(ui.kv({
        "Path": str(m.manifest_path),
        "Assembly": m.assembly,
        "Entry class": m.entry_class,
        "Framework": m.framework,
        "Mode": m.mode,
        "Methods": len(m.methods),
    }))
    if m.description:
        print()
        print(m.description)

    if m.methods:
        print()
        print(ui.section("Methods"))
        rows = [[name, ", ".join(spec.args) or "—", spec.returns or "—"]
                for name, spec in sorted(m.methods.items())]
        print(ui.table(["Name", "Args", "Returns"], rows))

    print()
    if ok:
        ui.success("Манифест валиден.")
        return 0
    ui.error("Манифест содержит ошибки:")
    for e in errors:
        print(f"  - {e}")
    return 2


def _cmd_bridge_info(args):
    try:
        proto = Engine(Manifest.from_dict({
            "name": "_probe", "assembly": "_probe.dll",
            "entry_class": "X.Y",
        }))
    except BridgeNotBuiltError as e:
        ui.error(str(e))
        return 1
    except Exception as e:
        ui.error(f"Не удалось найти Bridge.exe: {e}")
        return 1

    print(ui.banner("BRIDGE", "Bridge.exe"))
    print(ui.kv({"Path": str(proto.bridge_exe)}))
    return 0


def _cmd_test_call(args):
    try:
        engine = Engine(args.manifest)
    except SowannaError as e:
        ui.error(str(e))
        return 1

    raw_args = []
    for a in (args.arg or []):
        try:
            raw_args.append(int(a))
        except ValueError:
            try:
                raw_args.append(float(a))
            except ValueError:
                raw_args.append(a)

    try:
        result = engine.call(args.method, *raw_args)
    except BridgeError as e:
        ui.error(f"C# вернул ошибку: {e}")
        engine.stop()
        return 2
    except Exception as e:
        ui.error(f"Ошибка вызова: {type(e).__name__}: {e}")
        engine.stop()
        return 3
    finally:
        engine.stop()

    print(ui.banner("RESULT", f"{args.method}({', '.join(map(repr, raw_args))})"))
    print(f"  {result!r}")
    return 0


def _cmd_stubs(args):
    try:
        m = Manifest.from_file(args.manifest)
    except Exception as e:
        ui.error(f"Не удалось прочитать манифест: {e}")
        return 1

    from .stubs import write_stubs
    try:
        out = write_stubs(m, output=args.output, class_name=args.class_name)
    except Exception as e:
        ui.error(f"Не удалось сгенерировать стабы: {e}")
        return 1

    ui.success(f"Стабы сохранены: {out}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="sowanna",
        description=f"Sowanna {__version__} — вызов C# из Python через Bridge.exe.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="Показать манифест .pycsh")
    p.add_argument("path", help="Путь к манифесту или папке с ним")
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("bridge-info", help="Где Sowanna ищет Bridge.exe")
    p.set_defaults(func=_cmd_bridge_info)

    p = sub.add_parser("test-call", help="Вызвать один C#-метод из CLI")
    p.add_argument("manifest", help="Путь к .pycsh")
    p.add_argument("method", help="Имя C#-метода")
    p.add_argument("arg", nargs="*", help="Аргументы (int/float/str)")
    p.set_defaults(func=_cmd_test_call)

    p = sub.add_parser("stubs", help="Сгенерировать .pyi стабы из манифеста")
    p.add_argument("manifest", help="Путь к .pycsh")
    p.add_argument("-o", "--output", default=None,
                   help="Куда сохранить .pyi (по умолчанию рядом с манифестом)")
    p.add_argument("--class-name", default=None,
                   help="Имя класса в стабах (по умолчанию — последний сегмент entry_class)")
    p.set_defaults(func=_cmd_stubs)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"[FATAL] {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())