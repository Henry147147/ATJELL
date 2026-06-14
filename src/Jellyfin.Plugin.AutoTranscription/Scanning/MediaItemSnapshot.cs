namespace Jellyfin.Plugin.AutoTranscription.Scanning;

public sealed record SubtitleStreamSnapshot(string? Language, bool IsExternal);

public sealed record MediaItemSnapshot(Guid Id, string Path, IReadOnlyList<SubtitleStreamSnapshot> SubtitleStreams);

public sealed record SubtitleGenerationPlan(Guid ItemId, string MediaPath, IReadOnlyList<string> MissingLanguages)
{
    public bool NeedsGeneration => MissingLanguages.Count > 0;
}
