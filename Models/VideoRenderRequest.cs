using System.ComponentModel.DataAnnotations;

namespace VideoRenderService.Models;

public sealed class VideoRenderRequest
{
    [Required]
    [Url]
    public string ImageUrl { get; set; } = null!;

    [StringLength(30)]
    public string? Market { get; set; }

    [Range(3, 30)]
    public int DurationSeconds { get; set; } = 10;
}
