import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("flame_intelligence.ntrs")


class NasaNtrsService:
    """Read citation metadata from NASA's public Technical Reports Server API."""

    SEARCH_API = "https://ntrs.nasa.gov/api/citations/search"
    BASE_URL = "https://ntrs.nasa.gov"
    PAGE_SIZE = 10
    MAX_RESULTS = 500

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "FlameIntelligence-NASA-SpaceApps-Research/1.0",
            "Accept": "application/json",
        }
        self.last_http_status: Optional[int] = None
        self.last_error: Optional[str] = None
        self.last_total: Optional[int] = None
        self.last_pages = 0

    async def search_citations(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search and page NTRS results, deduplicating by stable NASA citation ID.

        The return type remains a list for compatibility with mission analysis.
        Pagination and source status are also exposed through ``last_*`` fields
        for the ingestion/source-register workflow.
        """

        if limit < 1 or limit > self.MAX_RESULTS:
            raise ValueError(f"NTRS result limit must be between 1 and {self.MAX_RESULTS}.")

        self.last_http_status = None
        self.last_error = None
        self.last_total = None
        self.last_pages = 0
        results: List[Dict[str, Any]] = []
        seen_ids = set()
        offset = 0
        search_query = f"microgravity combustion {query}".strip()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                while len(results) < limit:
                    page_size = min(self.PAGE_SIZE, limit - len(results))
                    response = await client.post(
                        self.SEARCH_API,
                        json={"q": search_query, "page": {"from": offset, "size": page_size}},
                        headers=self.headers,
                    )
                    self.last_http_status = response.status_code
                    self.last_pages += 1
                    if response.status_code != 200:
                        self.last_error = f"http_{response.status_code}"
                        logger.warning("NTRS search API returned HTTP %s", response.status_code)
                        break
                    try:
                        data = response.json()
                    except ValueError:
                        self.last_error = "invalid_json"
                        logger.warning("NTRS search API returned invalid JSON")
                        break

                    stats = data.get("stats") or {}
                    if self.last_total is None and stats.get("total") is not None:
                        try:
                            self.last_total = int(stats["total"])
                        except (TypeError, ValueError):
                            self.last_total = None
                    page_results = data.get("results") or []
                    if not page_results:
                        break

                    for item in page_results:
                        if not isinstance(item, dict):
                            continue
                        citation_id = item.get("id") or item.get("nasa_id")
                        title = item.get("title")
                        if citation_id is None or not title:
                            continue
                        citation_id = str(citation_id)
                        if citation_id in seen_ids:
                            continue
                        seen_ids.add(citation_id)
                        results.append(self._normalize_citation(item, citation_id))
                        if len(results) >= limit:
                            break

                    offset += len(page_results)
                    if len(page_results) < page_size:
                        break
                    if self.last_total is not None and offset >= self.last_total:
                        break
        except httpx.TimeoutException:
            self.last_error = "timeout"
            logger.warning("NTRS search timed out")
        except httpx.HTTPError as exc:
            self.last_error = "network_error"
            logger.warning("NTRS search failed due to a network error: %s", type(exc).__name__)

        return results[:limit]

    def _normalize_citation(self, item: Dict[str, Any], citation_id: str) -> Dict[str, Any]:
        publications = item.get("publications") or []
        publication = next((pub for pub in publications if isinstance(pub, dict)), {})
        publication_date = (
            publication.get("publicationDate")
            or item.get("distributionDate")
            or item.get("created")
            or item.get("publicationDate")
        )
        if isinstance(publication_date, dict):
            publication_date = publication_date.get("date") or publication_date.get("year")
        year = None
        if publication_date:
            try:
                year = int(str(publication_date)[:4])
            except (ValueError, TypeError):
                pass

        authors = []
        for author_entry in item.get("authorAffiliations") or []:
            if not isinstance(author_entry, dict):
                continue
            author = author_entry.get("meta", {}).get("author", {})
            name = author.get("name") if isinstance(author, dict) else None
            if name and name not in authors:
                authors.append(name)
        if not authors:
            authors = [
                author.get("name") if isinstance(author, dict) else str(author)
                for author in (item.get("authors") or [])
            ]

        downloads = item.get("downloads") or {}
        if isinstance(downloads, list):
            download_links = downloads
        elif isinstance(downloads, dict):
            download_links = [value for value in downloads.values() if isinstance(value, str)]
        else:
            download_links = []

        return {
            "ntrs_id": citation_id,
            "title": item.get("title"),
            "abstract": item.get("abstract") or None,
            "authors": "; ".join(name for name in authors if name) or None,
            "year": year,
            "publication_date": str(publication_date) if publication_date else None,
            "doi": publication.get("doi") or item.get("doi"),
            "publication": publication.get("publicationName") or publication.get("name"),
            "url": f"{NasaNtrsService.BASE_URL}/citations/{citation_id}",
            "download_links": download_links,
            "source": "NASA Technical Reports Server (NTRS)",
            "raw_metadata": item,
        }

    async def check_ntrs_status(self) -> Dict[str, Any]:
        """Check the NTRS health endpoint; this does not retrieve citations."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.BASE_URL}/api/health", headers=self.headers)
            return {
                "provider": "NASA Technical Reports Server (NTRS)",
                "url": self.BASE_URL,
                "status_code": response.status_code,
                "is_accessible": response.status_code < 500,
                "retrieval_status": "health_endpoint_available" if response.status_code < 500 else "unavailable",
                "details": "NTRS health endpoint responded. No citation metadata was retrieved."
                if response.status_code < 500 else f"HTTP {response.status_code}",
            }
        except httpx.TimeoutException:
            return {
                "provider": "NASA Technical Reports Server (NTRS)",
                "url": self.BASE_URL,
                "status_code": None,
                "is_accessible": False,
                "retrieval_status": "timeout",
                "details": "Connection check timed out.",
            }
        except httpx.HTTPError as exc:
            return {
                "provider": "NASA Technical Reports Server (NTRS)",
                "url": self.BASE_URL,
                "status_code": None,
                "is_accessible": False,
                "retrieval_status": "network_error",
                "details": f"Connection check failed: {type(exc).__name__}",
            }
