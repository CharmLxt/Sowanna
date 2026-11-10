"""Тесты Sowanna: манифест, протокол, callbacks, стабы, поиск Bridge.exe.

Не требуют собранного Bridge.exe и .NET SDK — проверяют чистую логику.
"""
import io
import sys
import tempfile
from pathlib import Path

from sowanna.manifest import Manifest, MethodSpec, MANIFEST_EXT
from sowanna.protocol import (
    make_request, encode, decode, parse_response,
    ProtocolError, BridgeError,
)
from sowanna import __version__

print("=" * 60)
print(f"  Sowanna {__version__} — Test")
print("=" * 60)

passed = 0
failed = 0


def check(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        print(f"  ❌ {name}: {type(e).__name__}: {e}")


# ---------- Manifest ----------

print("\n[1] Manifest")


def test_manifest_from_dict_basic():
    m = Manifest.from_dict({
        "name": "Test",
        "assembly": "Test.dll",
        "entry_class": "Test.Entry",
    })
    assert m.name == "Test"
    assert m.assembly == "Test.dll"
    assert m.entry_class == "Test.Entry"
    assert m.version == "0.0.0"
    assert m.framework == "net6.0"
    assert m.mode == "auto"
    assert m.methods == {}


check("Manifest: from_dict минимальный", test_manifest_from_dict_basic)


def test_manifest_from_dict_methods():
    m = Manifest.from_dict({
        "name": "X",
        "assembly": "X.dll",
        "entry_class": "X.Entry",
        "methods": {
            "Add": {"args": ["int", "int"], "returns": "int"},
            "Greet": {"args": ["string"], "returns": "string"},
        },
    })
    assert len(m.methods) == 2
    assert "Add" in m.methods
    assert m.methods["Add"].args == ["int", "int"]
    assert m.methods["Add"].returns == "int"


check("Manifest: from_dict с методами", test_manifest_from_dict_methods)


def test_manifest_round_trip():
    src = Manifest.from_dict({
        "name": "RT",
        "assembly": "RT.dll",
        "entry_class": "RT.Entry",
        "version": "1.2.3",
        "methods": {"Foo": {"args": [], "returns": "int"}},
    })
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / f"rt{MANIFEST_EXT}"
        src.save(p)
        assert p.exists()
        loaded = Manifest.from_file(p)
        assert loaded.name == "RT"
        assert loaded.version == "1.2.3"
        assert "Foo" in loaded.methods
        assert loaded._path == p.resolve()


check("Manifest: save + from_file", test_manifest_round_trip)


def test_manifest_missing_field():
    try:
        Manifest.from_dict({"name": "X", "assembly": "X.dll"})
    except ValueError as e:
        assert "entry_class" in str(e)
        return
    raise AssertionError("должно было упасть")


check("Manifest: отсутствие обязательного поля", test_manifest_missing_field)


def test_manifest_validate_ok():
    m = Manifest.from_dict({
        "name": "V", "assembly": "V.dll", "entry_class": "V.Entry",
    })
    ok, errors = m.validate()
    assert ok, errors


check("Manifest: validate ok", test_manifest_validate_ok)


def test_manifest_validate_bad_entry():
    m = Manifest.from_dict({
        "name": "V", "assembly": "V.dll", "entry_class": "NoNamespace",
    })
    ok, errors = m.validate()
    assert not ok
    assert any("entry_class" in e for e in errors)


check("Manifest: validate плохой entry_class", test_manifest_validate_bad_entry)


def test_manifest_validate_bad_assembly():
    m = Manifest.from_dict({
        "name": "V", "assembly": "V.txt", "entry_class": "V.Entry",
    })
    ok, errors = m.validate()
    assert not ok
    assert any("assembly" in e for e in errors)


check("Manifest: validate не .dll", test_manifest_validate_bad_assembly)


def test_manifest_validate_bad_mode():
    m = Manifest.from_dict({
        "name": "V", "assembly": "V.dll", "entry_class": "V.Entry",
        "mode": "banana",
    })
    ok, errors = m.validate()
    assert not ok
    assert any("mode" in e for e in errors)


check("Manifest: validate плохой mode", test_manifest_validate_bad_mode)


# ---------- Protocol ----------

print("\n[2] Protocol")


def test_protocol_encode_decode():
    req = make_request("Add", [2, 3], req_id=1)
    s = encode(req)
    assert s.endswith("\n")
    back = decode(s)
    assert back == req
    assert back["method"] == "Add"
    assert back["args"] == [2, 3]
    assert back["id"] == 1


check("Protocol: encode + decode", test_protocol_encode_decode)


def test_protocol_parse_response_ok():
    assert parse_response({"id": 1, "result": 42}) == 42


check("Protocol: parse_response ok", test_protocol_parse_response_ok)


def test_protocol_parse_response_null():
    assert parse_response({"id": 1, "result": None}) is None


check("Protocol: parse_response null", test_protocol_parse_response_null)


def test_protocol_parse_response_error():
    obj = {
        "id": 1,
        "error": {"type": "DivideByZeroException",
                  "message": "Attempted to divide by zero."},
    }
    try:
        parse_response(obj)
    except BridgeError as e:
        assert e.csharp_type == "DivideByZeroException"
        assert "divide" in e.message.lower()
        return
    raise AssertionError("должно было упасть")


check("Protocol: parse_response ошибка C#", test_protocol_parse_response_error)


def test_protocol_decode_empty():
    try:
        decode("   ")
    except ProtocolError:
        return
    raise AssertionError("должно было упасть")


check("Protocol: пустая строка", test_protocol_decode_empty)


def test_protocol_decode_invalid_json():
    try:
        decode("{not json")
    except ProtocolError:
        return
    raise AssertionError("должно было упасть")


check("Protocol: невалидный JSON", test_protocol_decode_invalid_json)


# ---------- Bridge discovery ----------

print("\n[3] Bridge.exe discovery")


def test_bridge_not_found_error():
    from sowanna.engine import Engine, BridgeNotBuiltError
    try:
        Engine(Manifest.from_dict({
            "name": "X", "assembly": "X.dll", "entry_class": "X.Y",
        }))
    except BridgeNotBuiltError:
        return
    except Exception as e:
        if type(e).__name__ == "FileNotFoundError":
            return
        raise


check("Engine: BridgeNotBuiltError или Bridge найден", test_bridge_not_found_error)


# ---------- Callbacks ----------

print("\n[4] Callbacks")


class _FakeProc:
    def __init__(self):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def poll(self):
        return None


def test_callback_unknown():
    from sowanna.bridge import BridgeProcess
    bp = BridgeProcess("Bridge.exe", "x.dll", "X.Y")
    bp._proc = _FakeProc()
    bp._handle_callback({"kind": "callback", "callback_id": 1,
                         "name": "nope", "args": []})
    bp._proc.stdin.seek(0)
    obj = decode(bp._proc.stdin.read())
    assert obj["kind"] == "callback_result"
    assert obj["callback_id"] == 1
    assert "error" in obj
    assert obj["error"]["type"] == "UnknownCallback"


check("Callback: неизвестный name → error", test_callback_unknown)


def test_callback_known():
    from sowanna.bridge import BridgeProcess
    bp = BridgeProcess("Bridge.exe", "x.dll", "X.Y")
    bp._callbacks["sum"] = lambda a, b: a + b
    bp._proc = _FakeProc()
    bp._handle_callback({"kind": "callback", "callback_id": 5,
                         "name": "sum", "args": [2, 3]})
    bp._proc.stdin.seek(0)
    obj = decode(bp._proc.stdin.read())
    assert obj["kind"] == "callback_result"
    assert obj["callback_id"] == 5
    assert obj["result"] == 5


check("Callback: известный name → result", test_callback_known)


def test_callback_python_error():
    from sowanna.bridge import BridgeProcess
    bp = BridgeProcess("Bridge.exe", "x.dll", "X.Y")

    def boom(a, b):
        raise ValueError("oops")

    bp._callbacks["bad"] = boom
    bp._proc = _FakeProc()
    bp._handle_callback({"kind": "callback", "callback_id": 2,
                         "name": "bad", "args": [1, 2]})
    bp._proc.stdin.seek(0)
    obj = decode(bp._proc.stdin.read())
    assert obj["kind"] == "callback_result"
    assert obj["callback_id"] == 2
    assert "error" in obj
    assert obj["error"]["type"] == "ValueError"
    assert "oops" in obj["error"]["message"]


check("Callback: Python-исключение → error", test_callback_python_error)


# ---------- Stubs ----------

print("\n[5] Stubs")


def test_stubs_basic():
    from sowanna.stubs import generate_stubs
    m = Manifest.from_dict({
        "name": "Test", "assembly": "Test.dll", "entry_class": "Test.Entry",
        "methods": {
            "Add": {"args": ["int", "int"], "returns": "int"},
            "Greet": {"args": ["string"], "returns": "string"},
        },
    })
    s = generate_stubs(m)
    assert "class Entry:" in s
    assert "def Add(arg0: int, arg1: int) -> int" in s
    assert "def Greet(arg0: str) -> str" in s


check("Stubs: базовые методы", test_stubs_basic)


def test_stubs_array_types():
    from sowanna.stubs import generate_stubs
    m = Manifest.from_dict({
        "name": "X", "assembly": "X.dll", "entry_class": "X.Entry",
        "methods": {"Sum": {"args": ["double[]"], "returns": "double"}},
    })
    s = generate_stubs(m)
    assert "List[float]" in s
    assert "from typing import" in s


check("Stubs: массив → List[float]", test_stubs_array_types)


def test_stubs_void():
    from sowanna.stubs import generate_stubs
    m = Manifest.from_dict({
        "name": "X", "assembly": "X.dll", "entry_class": "X.Entry",
        "methods": {"Log": {"args": ["string"], "returns": "void"}},
    })
    s = generate_stubs(m)
    assert "-> None" in s


check("Stubs: void → None", test_stubs_void)


def test_stubs_empty_manifest():
    from sowanna.stubs import generate_stubs
    m = Manifest.from_dict({
        "name": "Empty", "assembly": "Empty.dll",
        "entry_class": "Empty.Entry",
    })
    s = generate_stubs(m)
    assert "class Entry:" in s
    assert "..." in s


check("Stubs: пустой манифест → ...", test_stubs_empty_manifest)


def test_stubs_no_return():
    from sowanna.stubs import generate_stubs
    m = Manifest.from_dict({
        "name": "X", "assembly": "X.dll", "entry_class": "X.Entry",
        "methods": {"Do": {"args": []}},
    })
    s = generate_stubs(m)
    assert "def Do() -> Any" in s


check("Stubs: без returns → Any", test_stubs_no_return)


# ---------- Итог ----------

total = passed + failed
print("\n" + "=" * 60)
print(f"  PASSED: {passed} / {total}")
print(f"  FAILED: {failed}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)