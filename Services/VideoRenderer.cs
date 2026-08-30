using System.Diagnostics;
using System.Net;
using System.Net.Sockets;

namespace VideoRenderService.Services;

public sealed class VideoRenderer
{
    private const int MaxImageBytes = 10 * 1024 * 1024;
    private const int MaxRedirects = 3;

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
        if (durationSeconds is < 3 or > 30)
            throw new ArgumentOutOfRangeException(nameof(durationSeconds), "Video süresi 3 ile 30 saniye arasında olmalıdır.");

        var workDir = Path.Combine(
            _env.ContentRootPath,
            "storage",
            "video-jobs",
            Guid.NewGuid().ToString("N"));

        Directory.CreateDirectory(workDir);

        var imagePath = Path.Combine(workDir, "image");
        var fileName = $"{Guid.NewGuid():N}.mp4";
        var videoDir = Path.Combine(_env.WebRootPath ?? Path.Combine(_env.ContentRootPath, "wwwroot"), "videos");
        var outputVideo = Path.Combine(videoDir, fileName);

        Directory.CreateDirectory(videoDir);

        try
        {
            await DownloadImageAsync(imageUrl, imagePath, ct);

            await RunFfmpegAsync(
                imagePath,
                GetMp3ByMarket(market),
                outputVideo,
                durationSeconds,
                ct);

            return $"/videos/{fileName}";
        }
        catch
        {
            TryDeleteFile(outputVideo);
            throw;
        }
        finally
        {
            TryDeleteDirectory(workDir);
        }
    }

    private async Task DownloadImageAsync(string url, string path, CancellationToken ct)
    {
        var currentUri = await ValidatePublicHttpUriAsync(url, ct);

        for (var redirectCount = 0; redirectCount <= MaxRedirects; redirectCount++)
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, currentUri);
            using var response = await _httpClient.SendAsync(
                request,
                HttpCompletionOption.ResponseHeadersRead,
                ct);

            if (IsRedirect(response.StatusCode))
            {
                if (redirectCount == MaxRedirects || response.Headers.Location is null)
                    throw new HttpRequestException("Resim URL'i çok fazla yönlendirme içeriyor.");

                var redirectUri = response.Headers.Location.IsAbsoluteUri
                    ? response.Headers.Location
                    : new Uri(currentUri, response.Headers.Location);

                currentUri = await ValidatePublicHttpUriAsync(redirectUri.ToString(), ct);
                continue;
            }

            response.EnsureSuccessStatusCode();

            var contentType = response.Content.Headers.ContentType?.MediaType;
            if (contentType is null || !contentType.StartsWith("image/", StringComparison.OrdinalIgnoreCase))
                throw new HttpRequestException("URL bir resim döndürmüyor.");

            if (response.Content.Headers.ContentLength > MaxImageBytes)
                throw new HttpRequestException("Resim boyutu en fazla 10 MB olabilir.");

            await using var input = await response.Content.ReadAsStreamAsync(ct);
            await using var output = File.Create(path);
            await CopyWithLimitAsync(input, output, MaxImageBytes, ct);
            return;
        }
    }

    private static async Task<Uri> ValidatePublicHttpUriAsync(string url, CancellationToken ct)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) ||
            (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps))
        {
            throw new ArgumentException("Geçerli bir HTTP veya HTTPS resim URL'i gönderilmelidir.", nameof(url));
        }

        if (uri.IsLoopback)
            throw new ArgumentException("Yerel ağ adresleri kullanılamaz.", nameof(url));

        IPAddress[] addresses;
        try
        {
            addresses = await Dns.GetHostAddressesAsync(uri.DnsSafeHost, ct);
        }
        catch (SocketException ex)
        {
            throw new HttpRequestException("Resim URL'inin adresi çözümlenemedi.", ex);
        }

        if (addresses.Length == 0 || addresses.Any(IsPrivateOrReserved))
            throw new ArgumentException("Yerel veya özel ağ adresleri kullanılamaz.", nameof(url));

        return uri;
    }

    private static bool IsPrivateOrReserved(IPAddress address)
    {
        if (IPAddress.IsLoopback(address) || address.Equals(IPAddress.Any) || address.Equals(IPAddress.IPv6Any))
            return true;

        if (address.AddressFamily == AddressFamily.InterNetworkV6)
        {
            if (address.IsIPv6LinkLocal || address.IsIPv6SiteLocal || address.IsIPv6Multicast)
                return true;

            if (address.IsIPv4MappedToIPv6)
                return IsPrivateOrReserved(address.MapToIPv4());

            return (address.GetAddressBytes()[0] & 0xFE) == 0xFC;
        }

        var bytes = address.GetAddressBytes();
        return bytes[0] == 0 ||
               bytes[0] == 10 ||
               bytes[0] == 127 ||
               bytes[0] >= 224 ||
               (bytes[0] == 100 && bytes[1] is >= 64 and <= 127) ||
               (bytes[0] == 169 && bytes[1] == 254) ||
               (bytes[0] == 172 && bytes[1] is >= 16 and <= 31) ||
               (bytes[0] == 192 && bytes[1] == 168);
    }

    private static async Task CopyWithLimitAsync(
        Stream input,
        Stream output,
        int maxBytes,
        CancellationToken ct)
    {
        var buffer = new byte[81920];
        var totalBytes = 0;

        while (true)
        {
            var bytesRead = await input.ReadAsync(buffer, ct);
            if (bytesRead == 0)
                break;

            totalBytes += bytesRead;
            if (totalBytes > maxBytes)
                throw new HttpRequestException("Resim boyutu en fazla 10 MB olabilir.");

            await output.WriteAsync(buffer.AsMemory(0, bytesRead), ct);
        }
    }

    private string GetMp3ByMarket(string? market)
    {
        var musicDir = Path.Combine(_env.ContentRootPath, "Assets", "Musics");

        if (!Directory.Exists(musicDir))
            throw new DirectoryNotFoundException(musicDir);

        var files = Directory.GetFiles(musicDir, "*.mp3");
        if (files.Length == 0)
            throw new InvalidOperationException("Mp3 bulunamadı.");

        var keyword = market?.Trim().ToLowerInvariant() switch
        {
            "a101" => "a101",
            "bim" => "bim",
            "şok" => "sok",
            "sok" => "sok",
            "migros" => "migros",
            "trendyol" => "trendyol",
            "hepsiburada" => "hepsiburada",
            "gratis" => "gratis",
            _ => "kontraa"
        };

        var marketTrack = files.FirstOrDefault(x =>
            Path.GetFileName(x).Contains(keyword, StringComparison.OrdinalIgnoreCase));
        if (marketTrack != null)
            return marketTrack;

        return files.FirstOrDefault(x =>
                   Path.GetFileName(x).Contains("kontraa", StringComparison.OrdinalIgnoreCase))
               ?? throw new InvalidOperationException(
                   "Markete özel MP3 ve genel müzik yedeği bulunamadı.");
    }

    private static async Task RunFfmpegAsync(
        string imagePath,
        string audioPath,
        string outputPath,
        int durationSeconds,
        CancellationToken ct)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "ffmpeg",
            RedirectStandardError = true,
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        var arguments = new[]
        {
            "-y",
            "-loop", "1",
            "-framerate", "30",
            "-i", imagePath,
            "-i", audioPath,
            "-t", durationSeconds.ToString(),
            "-filter_complex",
            "color=c=0xF3F4F6:s=1080x1920:r=30[canvas];" +
            "[0:v]scale=900:1400:force_original_aspect_ratio=decrease:flags=lanczos," +
            "unsharp=5:5:0.45:5:5:0.0," +
            "pad=960:1460:(ow-iw)/2:(oh-ih)/2:color=white[card];" +
            "[canvas][card]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v]",
            "-map", "[v]",
            "-map", "1:a",
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-profile:v", "high",
            "-level", "4.1",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-shortest",
            "-movflags", "+faststart",
            outputPath
        };

        foreach (var argument in arguments)
            startInfo.ArgumentList.Add(argument);

        using var process = Process.Start(startInfo)
            ?? throw new InvalidOperationException("FFmpeg başlatılamadı.");

        var standardErrorTask = process.StandardError.ReadToEndAsync(ct);
        var standardOutputTask = process.StandardOutput.ReadToEndAsync(ct);

        try
        {
            await process.WaitForExitAsync(ct);
        }
        catch (OperationCanceledException)
        {
            if (!process.HasExited)
                process.Kill(entireProcessTree: true);

            throw;
        }

        await standardOutputTask;
        var standardError = await standardErrorTask;

        if (process.ExitCode != 0)
            throw new InvalidOperationException("FFmpeg hata verdi: " + standardError);
    }

    private static bool IsRedirect(HttpStatusCode statusCode) =>
        statusCode is HttpStatusCode.MovedPermanently
            or HttpStatusCode.Redirect
            or HttpStatusCode.RedirectMethod
            or HttpStatusCode.TemporaryRedirect
            or HttpStatusCode.PermanentRedirect;

    private static void TryDeleteFile(string path)
    {
        try
        {
            if (File.Exists(path))
                File.Delete(path);
        }
        catch
        {
            // Cleanup failures must not hide the render error.
        }
    }

    private static void TryDeleteDirectory(string path)
    {
        try
        {
            if (Directory.Exists(path))
                Directory.Delete(path, recursive: true);
        }
        catch
        {
            // Cleanup failures must not hide the render result.
        }
    }
}
