import pytest

from asub.exceptions import MediaError
from asub.models import CaptionSegment, ProcessingOptions
from asub.subtitles import render_ass, render_srt, render_vtt, validate_segments


def sample_segments():
    return [
        CaptionSegment(index=1, start=0, end=1.5, text="Hello world from a caption", speaker="Speaker 1"),
        CaptionSegment(index=2, start=2, end=4, text="Second sentence.", speaker=None),
    ]


def test_render_srt_vtt_ass_with_speaker_labels():
    options = ProcessingOptions(max_subtitle_chars=20)
    srt = render_srt(sample_segments(), options)
    vtt = render_vtt(sample_segments(), options)
    ass = render_ass(sample_segments(), options)
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "WEBVTT" in vtt
    assert "Speaker 1:" in srt
    assert "[Events]" in ass


def test_hide_speaker_labels():
    options = ProcessingOptions(speaker_labels="hidden")
    assert "Speaker 1:" not in render_srt(sample_segments(), options)


def test_invalid_timing_fails():
    with pytest.raises(MediaError):
        validate_segments([CaptionSegment(index=1, start=2, end=1, text="bad")])
