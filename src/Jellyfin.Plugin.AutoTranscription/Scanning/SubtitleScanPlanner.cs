namespace Jellyfin.Plugin.AutoTranscription.Scanning;

public static class SubtitleScanPlanner
{
    public static SubtitleGenerationPlan Plan(
        MediaItemSnapshot item,
        IReadOnlyList<string> targetLanguages,
        bool treatEmbeddedAsPresent)
    {
        var present = item.SubtitleStreams
            .Where(stream => stream.IsExternal || treatEmbeddedAsPresent)
            .Select(stream => NormalizeLanguage(stream.Language))
            .Where(language => language.Length > 0)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        var missing = targetLanguages
            .Select(NormalizeLanguage)
            .Where(language => language.Length > 0)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Where(language => !present.Contains(language))
            .ToArray();

        return new SubtitleGenerationPlan(item.Id, item.Path, missing);
    }

    private static string NormalizeLanguage(string? value)
    {
        return (value ?? string.Empty).Trim().ToLowerInvariant() switch
        {
            "eng" or "english" => "en",
            "spa" or "esp" or "spanish" => "es",
            "fre" or "fra" or "french" => "fr",
            "ger" or "deu" or "german" => "de",
            "jpn" or "japanese" => "ja",
            "kor" or "korean" => "ko",
            "por" or "portuguese" => "pt",
            var code => code.Replace('_', '-')
        };
    }
}
