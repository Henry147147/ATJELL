using MediaBrowser.Controller.Providers;

namespace Jellyfin.Plugin.AutoTranscription.Scanning;

public sealed class JellyfinSubtitleItemRefresher(
    IProviderManager providerManager,
    IDirectoryService directoryService) : ISubtitleItemRefresher
{
    public Task RefreshAsync(Guid itemId, CancellationToken cancellationToken)
    {
        providerManager.QueueRefresh(
            itemId,
            new MetadataRefreshOptions(directoryService)
            {
                MetadataRefreshMode = MetadataRefreshMode.ValidationOnly,
                ImageRefreshMode = MetadataRefreshMode.None,
                IsAutomated = true
            },
            RefreshPriority.Normal);
        return Task.CompletedTask;
    }
}
