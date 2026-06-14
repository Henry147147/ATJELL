using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.AutoTranscription.Configuration;

public sealed class PluginConfiguration : BasePluginConfiguration
{
    public string ServiceUrl { get; set; } = "http://asub-api:8765";

    public string ApiToken { get; set; } = string.Empty;

    public string TargetLanguages { get; set; } = "en,es";

    public string SubtitleFormats { get; set; } = "srt";

    public bool TreatEmbeddedSubtitlesAsPresent { get; set; } = true;

    public int MaxSubmittedJobs { get; set; } = 2;

    public bool DryRun { get; set; }

    public IReadOnlyList<string> GetTargetLanguages()
    {
        return NormalizeLanguageList(TargetLanguages);
    }

    public IReadOnlyList<string> GetSubtitleFormats()
    {
        return SubtitleFormats.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(item => item.TrimStart('.').ToLowerInvariant())
            .Where(item => item.Length > 0)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static IReadOnlyList<string> NormalizeLanguageList(string value)
    {
        var output = new List<string>();
        foreach (var raw in value.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var normalized = NormalizeLanguage(raw);
            if (!output.Contains(normalized, StringComparer.OrdinalIgnoreCase))
            {
                output.Add(normalized);
            }
        }

        return output;
    }

    private static string NormalizeLanguage(string value)
    {
        return value.Trim().ToLowerInvariant() switch
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
