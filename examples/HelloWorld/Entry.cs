using System;
using System.Linq;

namespace HelloWorld
{
    public static class Entry
    {
        // Этот делегат Bridge.exe находит по имени и устанавливает сам.
        // Если поле отсутствует — callback из C# работать не будет,
        // но остальные методы будут работать как обычно.
        public static Func<string, object[], object?>? CallbackHandler;

        public static int Add(int a, int b) => a + b;

        public static string Greet(string name) => $"Hello, {name}!";

        public static int[] Range(int n)
        {
            var arr = new int[n];
            for (int i = 0; i < n; i++) arr[i] = i;
            return arr;
        }

        public static double Mean(double[] values)
        {
            if (values == null || values.Length == 0) return 0.0;
            return values.Average();
        }

        public static string Version() => "HelloWorld 1.0.0";

        public static int CallPythonSum(int a, int b)
        {
            if (CallbackHandler == null)
                throw new InvalidOperationException("Python callback handler не установлен");
            var result = CallbackHandler("sum", new object[] { a, b });
            return Convert.ToInt32(result);
        }

        public static string CallPythonGreet(string name)
        {
            if (CallbackHandler == null)
                throw new InvalidOperationException("Python callback handler не установлен");
            var result = CallbackHandler("greet_from_python", new object[] { name });
            return result?.ToString() ?? "<null>";
        }
    }
}