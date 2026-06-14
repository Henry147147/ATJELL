using Jellyfin.Data.Enums;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Library;
using MediaBrowser.Controller.Persistence;
using MediaBrowser.Model.Entities;

namespace Jellyfin.Plugin.AutoTranscription.Scanning;

public sealed class JellyfinLibrarySubtitleScanner(
    ILibraryManager libraryManager,
    IMediaSourceManager mediaSourceManager) : ILibrarySubtitleScanner
{
    public Task<IReadOnlyList<MediaItemSnapshot>> GetVideoItemsAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var items = libraryManager.GetItemList(new InternalItemsQuery
        {
            Recursive = true,
            IsFolder = false,
            IsVirtualItem = false,
            MediaTypes = [MediaType.Video]
        });

        var snapshots = items
            .Where(item => !string.IsNullOrWhiteSpace(item.Path))
            .Select(ToSnapshot)
            .ToArray();
        return Task.FromResult<IReadOnlyList<MediaItemSnapshot>>(snapshots);
    }

    private MediaItemSnapshot ToSnapshot(BaseItem item)
    {
        var subtitles = mediaSourceManager.GetMediaStreams(new MediaStreamQuery
            {
                ItemId = item.Id,
                Type = MediaStreamType.Subtitle
            })
            .Select(stream => new SubtitleStreamSnapshot(stream.Language, stream.IsExternal))
            .ToArray();
        return new MediaItemSnapshot(item.Id, item.Path, subtitles);
    }
}
