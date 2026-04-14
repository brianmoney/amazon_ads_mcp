"""Media type registry and resolution helpers."""

import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse


class MediaTypeRegistry:
    """Registry for managing media types from OpenAPI specs and sidecars.

    This class maintains a registry of media types for both requests and
    responses, extracted from OpenAPI specifications and sidecar files.
    It provides methods to add media type mappings and resolve the
    appropriate content types for specific HTTP methods and URL paths.

    The registry supports templated paths and includes caching for
    improved performance when resolving media types.
    """

    def __init__(self) -> None:
        """Initialize the media type registry.

        Sets up internal storage for request entries, response entries,
        and a cache for resolved media type lookups.
        """
        self._req_entries: List[Dict[Tuple[str, str], str]] = []
        self._resp_entries: List[Dict[Tuple[str, str], List[str]]] = []
        self._cache: Dict[
            Tuple[str, str], Tuple[Optional[str], Optional[List[str]]]
        ] = {}
        self._bulk_loading: bool = False

    def begin_bulk_load(self) -> None:
        """Begin a bulk-loading phase.

        During bulk loading, cache invalidation is deferred until
        :meth:`end_bulk_load` is called. Use this when mounting
        multiple specs at startup to avoid redundant cache clears.
        """
        self._bulk_loading = True

    def end_bulk_load(self) -> None:
        """End the bulk-loading phase and invalidate the cache once.

        Call this after all specs have been registered during startup.
        """
        self._bulk_loading = False
        self._cache.clear()

    def add_entries(
        self,
        request_media: Dict[Tuple[str, str], str],
        response_media: Dict[Tuple[str, str], List[str]],
    ) -> None:
        """Add precomputed media type mappings to the registry."""
        req_map = dict(request_media)
        resp_map = {key: list(values) for key, values in response_media.items()}
        self._req_entries.append(req_map)
        self._resp_entries.append(resp_map)
        if not self._bulk_loading:
            self._cache.clear()

    def resolve(
        self, method: str, url: str
    ) -> Tuple[Optional[str], Optional[List[str]]]:
        """Resolve media types for a specific HTTP method and URL.

        Attempts to find the appropriate request and response media
        types for the given method and URL. First checks for exact
        matches, then falls back to templated path matching. Results
        are cached for subsequent lookups.

        :param method: HTTP method (e.g., 'GET', 'POST')
        :type method: str
        :param url: URL to resolve media types for
        :type url: str
        :return: Tuple of (request_media_type, response_media_types)
        :rtype: Tuple[Optional[str], Optional[List[str]]]
        """
        m = (method or "get").lower()
        path = (urlparse(url).path or "/").rstrip("/") or "/"
        cache_key = (m, path)
        if cache_key in self._cache:
            return self._cache[cache_key]
        for req_map, resp_map in zip(self._req_entries, self._resp_entries):
            if (m, path) in req_map or (m, path) in resp_map:
                result = (req_map.get((m, path)), resp_map.get((m, path)))
                self._cache[cache_key] = result
                return result
        for req_map, resp_map in zip(self._req_entries, self._resp_entries):
            keys: Set[Tuple[str, str]] = set(req_map.keys()) | set(resp_map.keys())
            for mm, templated in keys:
                if mm != m:
                    continue
                if re.match(_oai_template_to_regex(templated), path):
                    result = (
                        req_map.get((mm, templated)),
                        resp_map.get((mm, templated)),
                    )
                    self._cache[cache_key] = result
                    return result
        result = (None, None)
        self._cache[cache_key] = result
        return result


def _oai_template_to_regex(path_template: str) -> str:
    """Convert an OpenAPI path template to a regular expression."""
    if not path_template:
        return r"^/$"
    escaped = re.escape(path_template)
    escaped = re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", escaped)
    return rf"^{escaped.rstrip('/') or '/'}$"


__all__ = [
    "MediaTypeRegistry",
]
