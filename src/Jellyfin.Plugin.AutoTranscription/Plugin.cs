using Jellyfin.Plugin.AutoTranscription.Configuration;
using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;

namespace Jellyfin.Plugin.AutoTranscription;

public sealed class Plugin : BasePlugin<PluginConfiguration>, IHasWebPages
{
    public Plugin(IApplicationPaths applicationPaths, IXmlSerializer xmlSerializer)
        : base(applicationPaths, xmlSerializer)
    {
        Instance = this;
    }

    public static Plugin? Instance { get; private set; }

    public override string Name => "Auto Transcription";

    public override Guid Id => Guid.Parse("8b4c0a75-16a4-40f7-a874-d8620cce28f3");

    public IEnumerable<PluginPageInfo> GetPages()
    {
        return PluginPages.GetPages();
    }
}
