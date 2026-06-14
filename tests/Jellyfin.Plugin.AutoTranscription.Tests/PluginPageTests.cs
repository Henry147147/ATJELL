using Jellyfin.Plugin.AutoTranscription.Configuration;
using Xunit;

namespace Jellyfin.Plugin.AutoTranscription.Tests;

public sealed class PluginPageTests
{
    [Fact]
    public void ConfigurationPageIsExposedAsEmbeddedResource()
    {
        var page = Assert.Single(PluginPages.GetPages());

        Assert.Equal("AutoTranscription", page.Name);
        Assert.Equal("Auto Transcription", page.DisplayName);
        Assert.Equal("Jellyfin.Plugin.AutoTranscription.Configuration.configPage.html", page.EmbeddedResourcePath);
    }
}
