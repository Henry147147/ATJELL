using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace Jellyfin.Plugin.AutoTranscription.Api;

public sealed record CreateSubtitleJobRequest(
    [property: JsonPropertyName("media_path")] string MediaPath,
    [property: JsonPropertyName("target_languages")] IReadOnlyList<string> TargetLanguages,
    [property: JsonPropertyName("existing_languages")] IReadOnlyList<string> ExistingLanguages);

public sealed record SubtitleJobResponse(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("state")] string State,
    [property: JsonPropertyName("outputs")] IReadOnlyList<string> Outputs,
    [property: JsonPropertyName("error")] string? Error);

public interface IAsubServiceClient
{
    Task<SubtitleJobResponse> SubmitJobAsync(CreateSubtitleJobRequest request, CancellationToken cancellationToken);
}

public sealed class AsubServiceClient(HttpClient httpClient, string apiToken) : IAsubServiceClient
{
    public async Task<SubtitleJobResponse> SubmitJobAsync(CreateSubtitleJobRequest request, CancellationToken cancellationToken)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "/v1/jobs")
        {
            Content = JsonContent.Create(request)
        };
        if (!string.IsNullOrWhiteSpace(apiToken))
        {
            message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiToken);
        }

        using var response = await httpClient.SendAsync(message, cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<SubtitleJobResponse>(cancellationToken).ConfigureAwait(false)
            ?? throw new InvalidOperationException("ASR service returned an empty job response.");
    }
}
