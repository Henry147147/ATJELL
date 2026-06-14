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

    [Fact]
    public async Task RunnerHonorsMaxSubmittedJobsPerRun()
    {
        var items = Enumerable.Range(0, 3)
            .Select(index => new MediaItemSnapshot(Guid.NewGuid(), $"/media/{index}.mkv", []))
            .ToArray();
        var client = new FakeClient();
        var refresher = new FakeRefresher();
        var runner = new SubtitleScanTaskRunner(
            new FakeScanner(items),
            client,
            refresher,
            new PluginConfiguration
            {
                TargetLanguages = "en",
                MaxSubmittedJobs = 2
            });

        await runner.RunAsync(new Progress<double>(), CancellationToken.None);

        Assert.Equal(2, client.Requests.Count);
        Assert.Equal(2, refresher.Refreshed.Count);
        Assert.Equal(new[] { "/media/0.mkv", "/media/1.mkv" }, client.Requests.Select(request => request.MediaPath));
    }

    [Fact]
    public async Task RunnerSubmitsConfiguredBatchConcurrently()
    {
        var items = Enumerable.Range(0, 2)
            .Select(index => new MediaItemSnapshot(Guid.NewGuid(), $"/media/{index}.mkv", []))
            .ToArray();
        var client = new CoordinatedClient(expectedConcurrentCalls: 2);
        var runner = new SubtitleScanTaskRunner(
            new FakeScanner(items),
            client,
            new FakeRefresher(),
            new PluginConfiguration
            {
                TargetLanguages = "en",
                MaxSubmittedJobs = 2
            });

        await runner.RunAsync(new Progress<double>(), CancellationToken.None);

        Assert.Equal(2, client.MaxActiveCalls);
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

    private sealed class CoordinatedClient(int expectedConcurrentCalls) : IAsubServiceClient
    {
        private readonly object _sync = new();
        private readonly TaskCompletionSource _allCallsActive = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private int _activeCalls;

        public int MaxActiveCalls { get; private set; }

        public async Task<SubtitleJobResponse> SubmitJobAsync(CreateSubtitleJobRequest request, CancellationToken cancellationToken)
        {
            lock (_sync)
            {
                _activeCalls++;
                MaxActiveCalls = Math.Max(MaxActiveCalls, _activeCalls);
                if (_activeCalls == expectedConcurrentCalls)
                {
                    _allCallsActive.TrySetResult();
                }
            }

            await _allCallsActive.Task.WaitAsync(TimeSpan.FromSeconds(1), cancellationToken).ConfigureAwait(false);

            lock (_sync)
            {
                _activeCalls--;
            }

            return new SubtitleJobResponse("job", "completed", ["/media/out.srt"], null);
        }
    }
}
