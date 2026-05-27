namespace VideoRenderService.Models
{
    public sealed class VideoRenderResponse
    {
        public bool IsSuccess { get; set; }
        public string? Description { get; set; }
        public string? FileUrl { get; set; }
    }
}
