using System.Diagnostics;

namespace VideoRenderService.Services
{
    public sealed class VideoRenderer
    {
        private readonly HttpClient _httpClient;
        private readonly IWebHostEnvironment _env;

        public VideoRenderer(HttpClient httpClient, IWebHostEnvironment env)
        {
            _httpClient = httpClient;
            _env = env;
        }

        public async Task<string> CreateVideoAsync(
            string imageUrl,
            string? market,
            int durationSeconds,
            CancellationToken ct = default)
        {
            var workDir = Path.Combine(
                _env.ContentRootPath,
                "storage",
                "video-jobs",
                Guid.NewGuid().ToString("N"));

            Directory.CreateDirectory(workDir);

            var imagePath = Path.Combine(workDir, "image.jpg");

            var fileName = $"{Guid.NewGuid():N}.mp4";
            var videoDir = Path.Combine(_env.WebRootPath ?? Path.Combine(_env.ContentRootPath, "wwwroot"), "videos");

            Directory.CreateDirectory(videoDir);

            var outputVideo = Path.Combine(videoDir, fileName);

            await DownloadImageAsync(imageUrl, imagePath, ct);

            var mp3 = GetMp3ByMarket(market);

            await RunFfmpegAsync(
                imagePath,
                mp3,
                outputVideo,
                durationSeconds,
                ct);

            return $"/videos/{fileName}";
        }

        private async Task DownloadImageAsync(string url, string path, CancellationToken ct)
        {
            using var response = await _httpClient.GetAsync(url, ct);
            response.EnsureSuccessStatusCode();

            var contentType = response.Content.Headers.ContentType?.MediaType;

            if (contentType == null || !contentType.StartsWith("image/"))
                throw new InvalidOperationException("URL bir resim döndürmüyor.");

            await using var fs = File.Create(path);
            await response.Content.CopyToAsync(fs, ct);
        }

        private string GetMp3ByMarket(string? market)
        {
            var musicDir = Path.Combine(_env.ContentRootPath, "Assets", "Musics");

            if (!Directory.Exists(musicDir))
                throw new DirectoryNotFoundException(musicDir);

            var files = Directory.GetFiles(musicDir, "*.mp3");

            if (files.Length == 0)
                throw new InvalidOperationException("Mp3 bulunamadı.");

            market = market?.Trim().ToLowerInvariant();

            string keyword = market switch
            {
                "a101" => "a101",
                "bim" => "bim",
                "şok" => "sok",
                "sok" => "sok",
                _ => "kontraa"
            };

            return files.FirstOrDefault(x =>
                Path.GetFileName(x).Contains(keyword, StringComparison.OrdinalIgnoreCase))
                ?? files.First();
        }

        private static async Task RunFfmpegAsync(
            string imagePath,
            string audioPath,
            string outputPath,
            int durationSeconds,
            CancellationToken ct)
        {
            var args =
                $"-y -loop 1 -i \"{imagePath}\" -i \"{audioPath}\" " +
                $"-t {durationSeconds} " +
                "-c:v libx264 " +
                "-tune stillimage " +
                "-pix_fmt yuv420p " +
                "-c:a aac " +
                "-shortest " +
                $"\"{outputPath}\"";

            var process = Process.Start(new ProcessStartInfo
            {
                FileName = "ffmpeg",
                Arguments = args,
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            });

            if (process == null)
                throw new InvalidOperationException("FFmpeg başlatılamadı.");

            await process.WaitForExitAsync(ct);

            if (process.ExitCode != 0)
            {
                var error = await process.StandardError.ReadToEndAsync(ct);
                throw new InvalidOperationException("FFmpeg hata verdi: " + error);
            }
        }
    }
}