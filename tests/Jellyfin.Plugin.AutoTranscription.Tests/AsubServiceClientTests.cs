using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Jellyfin.Plugin.AutoTranscription.Api;
using Xunit;

namespace Jellyfin.Plugin.AutoTranscription.Tests;

public sealed class AsubServiceClientTests
{
    [Fact]
    public async Task SubmitJobSendsBearerTokenAndPayload()
    {
        using var handler = new CapturingHandler("""{"id":"job-1","state":"completed","outputs":["/media/Movie.en.srt"]}""");
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://asub-api:8765") };
        var client = new AsubServiceClient(http, "secret");

        var response = await client.SubmitJobAsync(
            new CreateSubtitleJobRequest("/media/Movie.mkv", new[] { "en" }, new[] { "es" }),
            CancellationToken.None);

        Assert.Equal("job-1", response.Id);
        Assert.Equal(HttpMethod.Post, handler.Request!.Method);
        Assert.Equal("/v1/jobs", handler.Request.RequestUri!.AbsolutePath);
        Assert.Equal("Bearer", handler.Request.Headers.Authorization!.Scheme);
        Assert.Equal("secret", handler.Request.Headers.Authorization.Parameter);

        var payload = JsonSerializer.Deserialize<CreateSubtitleJobRequest>(handler.Body!);
        Assert.Equal("/media/Movie.mkv", payload!.MediaPath);
        Assert.Equal(new[] { "en" }, payload.TargetLanguages);
        Assert.Equal(new[] { "es" }, payload.ExistingLanguages);
    }

    private sealed class CapturingHandler(string responseBody) : HttpMessageHandler
    {
        public HttpRequestMessage? Request { get; private set; }
        public string? Body { get; private set; }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Request = request;
            Body = request.Content is null
                ? null
                : await request.Content.ReadAsStringAsync(cancellationToken);
            return new HttpResponseMessage(HttpStatusCode.Accepted)
            {
                Content = new StringContent(responseBody)
            };
        }
    }
}
