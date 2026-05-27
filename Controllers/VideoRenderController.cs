using Microsoft.AspNetCore.Mvc;
using VideoRenderService.Models;
using VideoRenderService.Services;

namespace VideoRenderService.Controllers;

[ApiController]
[Route("api/video-render")]
public sealed class VideoRenderController : ControllerBase
{
    private readonly VideoRenderer _videoRenderer;

    public VideoRenderController(VideoRenderer videoRenderer)
    {
        _videoRenderer = videoRenderer;
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
            var fullVideoUrl = $"{baseUrl}{relativeVideoUrl}";

            return Ok(new VideoRenderResponse
            {
                IsSuccess = true,
                Description = null,
                FileUrl = fullVideoUrl
            });
        }
        catch (Exception ex)
        {
            return Ok(new VideoRenderResponse
            {
                IsSuccess = false,
                Description = ex.Message,
                FileUrl = null
            });
        }
    }
}