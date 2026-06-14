using MediaBrowser.Model.Tasks;
using Jellyfin.Plugin.AutoTranscription.Scanning;

namespace Jellyfin.Plugin.AutoTranscription.ScheduledTasks;

public sealed class GenerateSubtitlesTask(SubtitleScanTaskRunner? runner = null) : IScheduledTask
{
    public string Name => "Generate missing AI subtitles";

    public string Key => "AutoTranscriptionGenerateMissingSubtitles";

    public string Description => "Scans video libraries for configured missing subtitle languages and asks the ASR service to write Jellyfin sidecar subtitles.";

    public string Category => "Auto Transcription";

    public Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
    {
        if (runner is not null)
        {
            return runner.RunAsync(progress, cancellationToken);
        }

        progress.Report(100);
        return Task.CompletedTask;
    }

    public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
    {
        return new[]
        {
            new TaskTriggerInfo
            {
                Type = TaskTriggerInfoType.DailyTrigger,
                TimeOfDayTicks = TimeSpan.FromHours(3).Ticks
            }
        };
    }
}
