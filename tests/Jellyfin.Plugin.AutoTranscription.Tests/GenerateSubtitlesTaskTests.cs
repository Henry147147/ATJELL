using Jellyfin.Plugin.AutoTranscription.ScheduledTasks;
using MediaBrowser.Model.Tasks;
using Xunit;

namespace Jellyfin.Plugin.AutoTranscription.Tests;

public sealed class GenerateSubtitlesTaskTests
{
    [Fact]
    public void TaskMetadataIsStable()
    {
        var task = new GenerateSubtitlesTask();

        Assert.Equal("Generate missing AI subtitles", task.Name);
        Assert.Equal("AutoTranscriptionGenerateMissingSubtitles", task.Key);
        Assert.Equal("Auto Transcription", task.Category);
    }

    [Fact]
    public void DefaultTriggerRunsNightly()
    {
        var trigger = Assert.Single(new GenerateSubtitlesTask().GetDefaultTriggers());

        Assert.Equal(TaskTriggerInfoType.DailyTrigger, trigger.Type);
        Assert.Equal(TimeSpan.FromHours(3).Ticks, trigger.TimeOfDayTicks);
    }
}
