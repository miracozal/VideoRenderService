using VideoRenderService.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddHttpClient<VideoRenderer>();

var app = builder.Build();

var wwwroot = Path.Combine(app.Environment.ContentRootPath, "wwwroot");
var videos = Path.Combine(wwwroot, "videos");

Directory.CreateDirectory(videos);

app.UseHttpsRedirection();

app.UseStaticFiles();

app.UseAuthorization();

app.MapControllers();

app.Run();