"""Re-exports the export command's scrubber so tests (and any other caller) can use it."""
from .management.commands.export_training_data import scrub as scrub_for_test  # noqa: F401
