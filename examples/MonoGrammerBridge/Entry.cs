using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;

namespace MonogrammerBridge
{
    public static class Entry
    {
        // Импорт системных функций Windows для управления мышью
        [DllImport("user32.dll")]
        static extern bool SetCursorPos(int X, int Y);

        [DllImport("user32.dll")]
        static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);

        private const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
        private const uint MOUSEEVENTF_LEFTUP = 0x0004;

        // 1. Захват экрана (возвращает картинку в Base64)
        public static string CaptureScreen(int quality = 50)
        {
            int screenWidth = 1920; // Можно получить динамически через Screen.PrimaryScreen.Bounds.Width
            int screenHeight = 1080;
            
            using (Bitmap bitmap = new Bitmap(screenWidth, screenHeight))
            using (Graphics g = Graphics.FromImage(bitmap))
            {
                g.CopyFromScreen(0, 0, 0, 0, bitmap.Size);
                
                // Сжимаем в JPEG, чтобы не гонять по сети сырые мегабайты
                using (MemoryStream ms = new MemoryStream())
                {
                    var encoderParameters = new EncoderParameters(1);
                    encoderParameters.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, quality);
                    var jpegCodec = GetEncoder(ImageFormat.Jpeg);
                    
                    bitmap.Save(ms, jpegCodec, encoderParameters);
                    return Convert.ToBase64String(ms.ToArray());
                }
            }
        }

        // 2. Движение мыши
        public static void MoveMouse(int x, int y)
        {
            SetCursorPos(x, y);
        }

        // 3. Клик мыши
        public static void ClickMouse(bool down)
        {
            if (down) mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
            else mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
        }

        // Вспомогательная функция для поиска JPEG-кодека
        private static ImageCodecInfo GetEncoder(ImageFormat format)
        {
            ImageCodecInfo[] codecs = ImageCodecInfo.GetImageDecoders();
            foreach (ImageCodecInfo codec in codecs)
            {
                if (codec.FormatID == format.Guid) return codec;
            }
            return null;
        }
    }
}