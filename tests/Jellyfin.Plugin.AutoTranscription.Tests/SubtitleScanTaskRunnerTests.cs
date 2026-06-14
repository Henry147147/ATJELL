using Jellyfin.Plugin.AutoTranscription.Api;
using Jellyfin.Plugin.AutoTranscription.Configuration;
using Jellyfin.Plugin.AutoTranscription.Scanning;
using Xunit;

namespace Jellyfin.Plugin.AutoTranscription.Tests;

public sealed class SubtitleScanTaskRunnerTests
{
    [Fact]
    public async Task RunnerSubmitsOnlyItemsWithMissingLanguagesAndRefreshesCompletedItems()
    {
        var first = new MediaItemSnapshot(Guid.NewGuid(), "/media/one.mkv", new[] { new SubtitleStreamSnapshot("en", false) });
        var second = new MediaItemSnapshot(Guid.NewGuid(), "/media/two.mkv", new[] { new SubtitleStreamSnapshot("en", false), new SubtitleStreamSnapshot("es", true) });
        var scanner = new FakeScanner(first, second);
        var client = new FakeClient();
        var refresher = new FakeRefresher();
        var runner = new SubtitleScanTaskRunner(
            scanner,
            client,
            refresher,
            new PluginConfiguration { TargetLanguages = "en,es" });

        await runner.RunAsync(new Progress<double>(), CancellationToken.None);

        var request = Assert.Single(client.Requests);
        Assert.Equal("/media/one.mkv", request.MediaPath);
        Assert.Equal(new[] { "es" }, request.TargetLanguages);
        Assert.Equal(new[] { "en" }, request.ExistingLanguages);
        Assert.Equal(new[] { first.Id }, refresher.Refreshed);
    }

    [Fact]
    public async Task RunnerDoesNotSubmitInDryRun()
    {
        var item = new MediaItemSnapshot(Guid.NewGuid(), "/media/one.mkv", []);
        var client = new FakeClient();
        var refresher = new FakeRefresher();
        var runner = new SubtitleScanTaskRunner(
            new FakeScanner(item),
            client,
            refresher,
            new PluginConfiguration { DryRun = true });

        await runner.RunAsync(new Progress<double>(), CancellationToken.None);

        Assert.Empty(client.Requests);
        Assert.Empty(refresher.Refreshed);
    }

    private sealed class FakeScanner(params MediaItemSnapshot[] items) : ILibrarySubtitleScanner
    {
        public Task<IReadOnlyList<MediaItemSnapshot>> GetVideoItemsAsync(CancellationToken cancellationToken)
        {
            return Task.FromResult<IReadOnlyList<MediaItemSnapshot>>(items);
        }
    }

    private sealed class FakeClient : IAsubServiceClient
    {
        public List<CreateSubtitleJobRequest> Requests { get; } = [];

        public Task<SubtitleJobResponse> SubmitJobAsync(CreateSubtitleJobRequest request, CancellationToken cancellationToken)
        {
            Requests.Add(request);
            return Task.FromResult(new SubtitleJobResponse("job", "completed", ["/media/out.srt"], null));
        }
    }

    private sealed class FakeRefresher : ISubtitleItemRefresher
    {
        public List<Guid> Refreshed { get; } = [];

        public Task RefreshAsync(Guid itemId, CancellationToken cancellationToken)
        {
            Refreshed.Add(itemId);
            return Task.CompletedTask;
        }
    }
}
