class AsubError(Exception):
    """Base application error with a user-facing message."""


class ToolMissingError(AsubError):
    pass


class UnsupportedLanguageError(AsubError):
    pass


class MediaError(AsubError):
    pass


class WorkerError(AsubError):
    pass


class ResumeError(AsubError):
    pass
