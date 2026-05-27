namespace VideoRenderService.Models
{
    public sealed class VideoRenderRequest
    {
        public string ImageUrl { get; set; } = null!;
        public string? Market { get; set; }
        public int DurationSeconds { get; set; } = 10;
    }
}
