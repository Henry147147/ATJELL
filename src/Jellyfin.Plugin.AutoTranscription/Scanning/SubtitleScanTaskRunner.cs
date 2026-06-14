using Jellyfin.Plugin.AutoTranscription.Api;
using Jellyfin.Plugin.AutoTranscription.Configuration;

namespace Jellyfin.Plugin.AutoTranscription.Scanning;

public interface ILibrarySubtitleScanner
{
    Task<IReadOnlyList<MediaItemSnapshot>> GetVideoItemsAsync(CancellationToken cancellationToken);
}

public interface ISubtitleItemRefresher
{
    Task RefreshAsync(Guid itemId, CancellationToken cancellationToken);
}

public sealed class SubtitleScanTaskRunner(
    ILibrarySubtitleScanner scanner,
    IAsubServiceClient client,
    ISubtitleItemRefresher refresher,
    PluginConfiguration configuration)
{
    public async Task RunAsync(IProgress<double> progress, CancellationToken cancellationToken)
    {
        var items = await scanner.GetVideoItemsAsync(cancellationToken).ConfigureAwait(false);
        if (items.Count == 0)
        {
            progress.Report(100);
            return;
        }

        var targets = configuration.GetTargetLanguages();
        var maxSubmittedJobs = Math.Max(1, configuration.MaxSubmittedJobs);
        var pendingJobs = new List<(Guid ItemId, CreateSubtitleJobRequest Request)>();
        for (var index = 0; index < items.Count; index++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var item = items[index];
            var plan = SubtitleScanPlanner.Plan(item, targets, configuration.TreatEmbeddedSubtitlesAsPresent);
            if (plan.NeedsGeneration && !configuration.DryRun && pendingJobs.Count < maxSubmittedJobs)
            {
                pendingJobs.Add(
                    (
                        item.Id,
                        new CreateSubtitleJobRequest(
                            plan.MediaPath,
                            plan.MissingLanguages,
                            SubtitleScanPlanner.PresentLanguages(item, configuration.TreatEmbeddedSubtitlesAsPresent))));
            }

            progress.Report(((index + 1) / (double)items.Count) * 100);
        }

        var submissions = pendingJobs.Select(async pendingJob =>
        {
            var response = await client.SubmitJobAsync(pendingJob.Request, cancellationToken).ConfigureAwait(false);
            if (string.Equals(response.State, "completed", StringComparison.OrdinalIgnoreCase))
            {
                await refresher.RefreshAsync(pendingJob.ItemId, cancellationToken).ConfigureAwait(false);
            }
        });
        await Task.WhenAll(submissions).ConfigureAwait(false);
    }
}
