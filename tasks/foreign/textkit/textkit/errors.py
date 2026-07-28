class TextkitWarning(Exception):
    """Recoverable; the driver collects these and continues."""


class TextkitFatal(Exception):
    """Aborts the pipeline."""
