using Jellyfin.Plugin.AutoTranscription.Api;
using Jellyfin.Plugin.AutoTranscription.Scanning;
using Jellyfin.Plugin.AutoTranscription.ScheduledTasks;
using MediaBrowser.Controller;
using MediaBrowser.Controller.Plugins;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.DependencyInjection;

namespace Jellyfin.Plugin.AutoTranscription;

public sealed class PluginServiceRegistrator : IPluginServiceRegistrator
{
    public void RegisterServices(IServiceCollection serviceCollection, IServerApplicationHost applicationHost)
    {
        serviceCollection.AddSingleton<ILibrarySubtitleScanner, JellyfinLibrarySubtitleScanner>();
        serviceCollection.AddSingleton<ISubtitleItemRefresher, JellyfinSubtitleItemRefresher>();
        serviceCollection.AddSingleton<IScheduledTask, GenerateSubtitlesTask>();
        serviceCollection.AddSingleton(provider => new SubtitleScanTaskRunner(
            provider.GetRequiredService<ILibrarySubtitleScanner>(),
            provider.GetRequiredService<IAsubServiceClient>(),
            provider.GetRequiredService<ISubtitleItemRefresher>(),
            Plugin.Instance?.Configuration ?? new Configuration.PluginConfiguration()));
        serviceCollection.AddHttpClient("AutoTranscriptionAsub", (_, client) =>
        {
            var config = Plugin.Instance?.Configuration ?? new Configuration.PluginConfiguration();
            client.BaseAddress = new Uri(config.ServiceUrl);
        });
        serviceCollection.AddSingleton<IAsubServiceClient>(provider =>
        {
            var config = Plugin.Instance?.Configuration ?? new Configuration.PluginConfiguration();
            var factory = provider.GetRequiredService<IHttpClientFactory>();
            return new AsubServiceClient(factory.CreateClient("AutoTranscriptionAsub"), config.ApiToken);
        });
    }
}
