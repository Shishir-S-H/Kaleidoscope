"""Shared base for all Google Cloud provider implementations.

Every concrete Google provider should call ``_bootstrap()`` in its ``__init__``
to ensure ADC / Base64-key setup runs before any SDK call is made.
"""

from __future__ import annotations

import logging

from shared.utils.google_auth import (
    get_google_location,
    get_google_project,
    setup_google_credentials,
)

logger = logging.getLogger(__name__)


class GoogleBaseProvider:
    """Mixin that bootstraps Google credentials and exposes project/location."""

    def _bootstrap(self) -> None:
        """Run credential setup and cache project/location for sub-classes."""
        setup_google_credentials()
        self._project: str = get_google_project()
        self._location: str = get_google_location()
        logger.debug(
            "%s initialised (project=%s, location=%s)",
            self.__class__.__name__,
            self._project,
            self._location,
        )
