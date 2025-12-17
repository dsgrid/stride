"""Settings module for STRIDE dashboard."""

from stride.ui.settings.callbacks import register_settings_callbacks
from stride.ui.settings.layout import create_settings_layout

__all__ = ["create_settings_layout", "register_settings_callbacks"]
