"""Shared HTTP client identity for outbound requests to external providers.

Found live to matter, not just courtesy: httpx's default User-Agent
(``python-httpx/<version>``) got this project bot-filtered with HTTP 406
from the flagship Overpass instance, and rejected with HTTP 403 ("only
available to white-listed usages") from a community mirror that, it turned
out, only wanted requests to identify themselves — both resolved simply by
sending a descriptive User-Agent instead of httpx's generic default.
"""

USER_AGENT = "VillagePondPlanningSystem/0.3.0 (CSD Assignment, academic use)"

DEFAULT_HEADERS = {"User-Agent": USER_AGENT}
