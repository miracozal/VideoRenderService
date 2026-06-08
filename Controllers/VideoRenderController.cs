using Microsoft.AspNetCore.Mvc;
using VideoRenderService.Models;
using VideoRenderService.Services;

namespace VideoRenderService.Controllers;

[ApiController]
[Route("api/video-render")]
public sealed class VideoRenderController : ControllerBase
{
    private readonly VideoRenderer _videoRenderer;
    private readonly ILogger<VideoRenderController> _logger;

    public VideoRenderController(
        VideoRenderer videoRenderer,
        ILogger<VideoRenderController> logger)
    {
        _videoRenderer = videoRenderer;
        _logger = logger;
    }

    [HttpPost]
    public async Task<IActionResult> Create(
        [FromBody] VideoRenderRequest request,
        CancellationToken cancellationToken)
    {
        try
        {
            var relativeVideoUrl = await _videoRenderer.CreateVideoAsync(
                request.ImageUrl,
                request.Market,
                request.DurationSeconds,
                cancellationToken);

            var baseUrl = $"{Request.Scheme}://{Request.Host}";

            return Ok(new VideoRenderResponse
            {
                IsSuccess = true,
                Description = null,
                FileUrl = $"{baseUrl}{relativeVideoUrl}"
            });
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new VideoRenderResponse
            {
                IsSuccess = false,
                Description = ex.Message,
                FileUrl = null
            });
        }
        catch (HttpRequestException ex)
        {
            return UnprocessableEntity(new VideoRenderResponse
            {
                IsSuccess = false,
                Description = ex.Message,
                FileUrl = null
            });
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return StatusCode(499);
        }
        catch (OperationCanceledException)
        {
            return StatusCode(StatusCodes.Status504GatewayTimeout, new VideoRenderResponse
            {
                IsSuccess = false,
                Description = "Resim indirme veya video oluşturma işlemi zaman aşımına uğradı.",
                FileUrl = null
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Video render işlemi başarısız oldu.");

            return StatusCode(StatusCodes.Status500InternalServerError, new VideoRenderResponse
            {
                IsSuccess = false,
                Description = "Video oluşturulurken beklenmeyen bir hata oluştu.",
                FileUrl = null
            });
        }
    }
}
