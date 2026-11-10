using System;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace Sowanna.Bridge
{
    public static class Bridge
    {
        private static Assembly? _assembly;
        private static Type? _entry;
        private static string _entryName = "";
        private static long _callbackCounter = 0;

        public static int Main(string[] args)
        {
            try { Console.OutputEncoding = new UTF8Encoding(false); } catch { }
            try { Console.InputEncoding = new UTF8Encoding(false); } catch { }

            string assemblyPath = "";
            string entryClass = "";
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "--assembly") assemblyPath = args[i + 1];
                else if (args[i] == "--entry") entryClass = args[i + 1];
            }

            if (string.IsNullOrEmpty(assemblyPath) || string.IsNullOrEmpty(entryClass))
            {
                Console.Error.WriteLine("Bridge: --assembly <path> --entry <Namespace.Class> обязательны");
                return 1;
            }

            try
            {
                var fullPath = Path.GetFullPath(assemblyPath);
                if (!File.Exists(fullPath))
                {
                    Console.Error.WriteLine($"Bridge: сборка не найдена: {fullPath}");
                    return 1;
                }
                _assembly = Assembly.LoadFrom(fullPath);
                _entry = _assembly.GetType(entryClass);
                if (_entry == null)
                {
                    Console.Error.WriteLine($"Bridge: класс '{entryClass}' не найден в сборке");
                    return 1;
                }
                _entryName = entryClass;
            }
            catch (Exception e)
            {
                Console.Error.WriteLine($"Bridge: ошибка загрузки: {e.GetType().Name}: {e.Message}");
                return 1;
            }

            TryInstallCallbackHandler();

            Console.Error.WriteLine($"Bridge: загружено '{_entryName}' из {Path.GetFileName(assemblyPath)}");

            string? line;
            while ((line = Console.In.ReadLine()) != null)
            {
                line = line.Trim();
                if (line.Length == 0) continue;

                string resp;
                try { resp = HandleRequest(line); }
                catch (Exception e)
                {
                    resp = ErrorJson(null, "BridgeInternal", $"{e.GetType().Name}: {e.Message}");
                }
                Console.Out.WriteLine(resp);
                Console.Out.Flush();
            }

            return 0;
        }

        private static void TryInstallCallbackHandler()
        {
            if (_entry == null) return;
            FieldInfo? field;
            try
            {
                field = _entry.GetField("CallbackHandler",
                    BindingFlags.Public | BindingFlags.Static);
            }
            catch { return; }
            if (field == null) return;

            var expectedType = typeof(Func<string, object[], object?>);
            if (field.FieldType != expectedType)
            {
                Console.Error.WriteLine(
                    $"Bridge: поле CallbackHandler имеет тип {field.FieldType.Name}, " +
                    $"ожидался Func<string, object[], object?>. Callback не установлен.");
                return;
            }
            try
            {
                field.SetValue(null, (Func<string, object[], object?>)InvokePythonCallback);
                Console.Error.WriteLine($"Bridge: callback handler установлен в {_entryName}");
            }
            catch (Exception e)
            {
                Console.Error.WriteLine($"Bridge: не удалось установить callback handler: {e.Message}");
            }
        }

        private static object? InvokePythonCallback(string name, object[] args)
        {
            long cbId = Interlocked.Increment(ref _callbackCounter);
            var sb = new StringBuilder(128);
            sb.Append("{\"kind\":\"callback\",\"callback_id\":");
            sb.Append(cbId);
            sb.Append(",\"name\":");
            sb.Append(JsonSerializer.Serialize(name));
            sb.Append(",\"args\":[");
            for (int i = 0; i < args.Length; i++)
            {
                if (i > 0) sb.Append(',');
                sb.Append(args[i] == null ? "null" : JsonSerializer.Serialize(args[i], args[i].GetType()));
            }
            sb.Append("]}");
            Console.Out.WriteLine(sb.ToString());
            Console.Out.Flush();

            string? respLine = Console.In.ReadLine();
            if (respLine == null)
                throw new IOException("Bridge: stdin закрыт во время ожидания callback_result");
            respLine = respLine.Trim();
            if (respLine.Length == 0)
                throw new IOException("Bridge: пустой ответ на callback");

            using var doc = JsonDocument.Parse(respLine);
            var root = doc.RootElement;
            if (!root.TryGetProperty("kind", out var kindElem) ||
                kindElem.ValueKind != JsonValueKind.String ||
                kindElem.GetString() != "callback_result")
            {
                throw new InvalidOperationException(
                    "Bridge: ожидался callback_result, получено: " +
                    respLine.Substring(0, Math.Min(200, respLine.Length)));
            }
            if (root.TryGetProperty("error", out var errElem) && errElem.ValueKind != JsonValueKind.Null)
            {
                string et = "PythonCallbackError";
                string em = "python callback failed";
                if (errElem.ValueKind == JsonValueKind.Object)
                {
                    if (errElem.TryGetProperty("type", out var te) && te.ValueKind == JsonValueKind.String)
                        et = te.GetString() ?? et;
                    if (errElem.TryGetProperty("message", out var me) && me.ValueKind == JsonValueKind.String)
                        em = me.GetString() ?? em;
                }
                throw new InvalidOperationException($"{et}: {em}");
            }
            if (root.TryGetProperty("result", out var resElem) && resElem.ValueKind != JsonValueKind.Null)
            {
                try { return JsonSerializer.Deserialize<object>(resElem.GetRawText()); }
                catch { return resElem.GetRawText(); }
            }
            return null;
        }

        private static string HandleRequest(string line)
        {
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            JsonElement? idElem = root.TryGetProperty("id", out var idv) ? idv : (JsonElement?)null;

            if (!root.TryGetProperty("method", out var methodElem) ||
                methodElem.ValueKind != JsonValueKind.String)
                return ErrorJson(idElem, "MissingMethod", "поле 'method' обязательно");
            string methodName = methodElem.GetString() ?? "";

            if (_entry == null)
                return ErrorJson(idElem, "BridgeNotReady", "класс не загружен");

            MethodInfo? method;
            try
            {
                method = _entry.GetMethod(methodName,
                    BindingFlags.Public | BindingFlags.Static | BindingFlags.IgnoreCase);
            }
            catch (AmbiguousMatchException)
            {
                return ErrorJson(idElem, "AmbiguousMatch",
                    $"метод '{methodName}' имеет несколько перегрузок; Sowanna 0.1.0 не поддерживает overloads");
            }

            if (method == null)
                return ErrorJson(idElem, "MissingMethod",
                    $"метод '{methodName}' не найден в {_entryName}");

            var parameters = method.GetParameters();

            JsonElement[] argElems;
            if (root.TryGetProperty("args", out var argsElem) &&
                argsElem.ValueKind == JsonValueKind.Array)
            {
                argElems = new JsonElement[argsElem.GetArrayLength()];
                int idx = 0;
                foreach (var a in argsElem.EnumerateArray()) argElems[idx++] = a;
            }
            else
            {
                argElems = Array.Empty<JsonElement>();
            }

            if (argElems.Length != parameters.Length)
                return ErrorJson(idElem, "ArgCount",
                    $"метод '{methodName}' ожидает {parameters.Length} аргументов, получено {argElems.Length}");

            object?[] callArgs = new object?[parameters.Length];
            for (int i = 0; i < parameters.Length; i++)
            {
                try { callArgs[i] = ConvertArg(argElems[i], parameters[i].ParameterType); }
                catch (Exception e)
                {
                    return ErrorJson(idElem, "ArgConversion",
                        $"аргумент {i} ({parameters[i].ParameterType.Name}): {e.Message}");
                }
            }

            try
            {
                object? result = method.Invoke(null, callArgs);
                return ResultJson(idElem, result, method.ReturnType);
            }
            catch (TargetInvocationException tie)
            {
                var inner = tie.InnerException ?? tie;
                return ErrorJson(idElem, inner.GetType().Name, inner.Message, inner.StackTrace);
            }
            catch (Exception e)
            {
                return ErrorJson(idElem, e.GetType().Name, e.Message, e.StackTrace);
            }
        }

        private static object? ConvertArg(JsonElement elem, Type target)
        {
            if (elem.ValueKind == JsonValueKind.Null) return null;
            return JsonSerializer.Deserialize(elem.GetRawText(), target);
        }

        private static string ResultJson(JsonElement? id, object? value, Type returnType)
        {
            string idStr = id.HasValue ? id.Value.GetRawText() : "null";
            string resultStr = value == null ? "null" : JsonSerializer.Serialize(value, returnType);
            return $"{{\"id\":{idStr},\"result\":{resultStr}}}";
        }

        private static string ErrorJson(JsonElement? id, string type, string message, string? stack = null)
        {
            string idStr = id.HasValue ? id.Value.GetRawText() : "null";
            var typeEsc = JsonSerializer.Serialize(type);
            var msgEsc = JsonSerializer.Serialize(message);
            string inner = stack == null ? "" : $",\"stack\":{JsonSerializer.Serialize(stack)}";
            return $"{{\"id\":{idStr},\"error\":{{\"type\":{typeEsc},\"message\":{msgEsc}{inner}}}}}";
        }
    }
}