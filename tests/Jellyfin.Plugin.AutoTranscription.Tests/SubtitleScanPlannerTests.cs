using Jellyfin.Plugin.AutoTranscription.Scanning;
using Xunit;

namespace Jellyfin.Plugin.AutoTranscription.Tests;

public sealed class SubtitleScanPlannerTests
{
    [Fact]
    public void EmbeddedSubtitleSatisfiesLanguageWhenConfigured()
    {
        var item = new MediaItemSnapshot(
            Guid.NewGuid(),
            "/media/Movie.mkv",
            new[] { new SubtitleStreamSnapshot("en", false) });

        var result = SubtitleScanPlanner.Plan(item, new[] { "en", "es" }, treatEmbeddedAsPresent: true);

        Assert.Equal(new[] { "es" }, result.MissingLanguages);
    }

    [Fact]
    public void SidecarSubtitleSatisfiesLanguage()
    {
        var item = new MediaItemSnapshot(
            Guid.NewGuid(),
            "/media/Movie.mkv",
            new[] { new SubtitleStreamSnapshot("es", true) });

        var result = SubtitleScanPlanner.Plan(item, new[] { "en", "es" }, treatEmbeddedAsPresent: true);

        Assert.Equal(new[] { "en" }, result.MissingLanguages);
    }

    [Fact]
    public void ExistingEmbeddedSubtitleCanBeIgnoredByPolicy()
    {
        var item = new MediaItemSnapshot(
            Guid.NewGuid(),
            "/media/Movie.mkv",
            new[] { new SubtitleStreamSnapshot("en", false) });

        var result = SubtitleScanPlanner.Plan(item, new[] { "en" }, treatEmbeddedAsPresent: false);

        Assert.Equal(new[] { "en" }, result.MissingLanguages);
    }
}
