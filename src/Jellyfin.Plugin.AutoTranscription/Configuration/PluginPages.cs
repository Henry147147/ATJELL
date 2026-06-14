using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.AutoTranscription.Configuration;

public static class PluginPages
{
    public const string Name = "AutoTranscription";

    public const string DisplayName = "Auto Transcription";

    public const string ResourcePath = "Jellyfin.Plugin.AutoTranscription.Configuration.configPage.html";

    public static IEnumerable<PluginPageInfo> GetPages()
    {
        return
        [
            new PluginPageInfo
            {
                Name = Name,
                DisplayName = DisplayName,
                EmbeddedResourcePath = ResourcePath
            }
        ];
    }
}
