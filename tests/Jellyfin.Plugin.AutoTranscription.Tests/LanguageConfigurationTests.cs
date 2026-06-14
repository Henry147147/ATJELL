using Jellyfin.Plugin.AutoTranscription.Configuration;
using Xunit;

namespace Jellyfin.Plugin.AutoTranscription.Tests;

public sealed class LanguageConfigurationTests
{
    [Fact]
    public void DefaultsTargetEnglishAndSpanish()
    {
        var config = new PluginConfiguration();

        Assert.Equal("http://asub-api:8765", config.ServiceUrl);
        Assert.Equal(new[] { "en", "es" }, config.GetTargetLanguages());
        Assert.Equal("srt", config.SubtitleFormats);
        Assert.True(config.TreatEmbeddedSubtitlesAsPresent);
    }

    [Fact]
    public void NormalizesDistinctTargetLanguages()
    {
        var config = new PluginConfiguration { TargetLanguages = " EN, es, eng, Spanish " };

        Assert.Equal(new[] { "en", "es" }, config.GetTargetLanguages());
    }
}
