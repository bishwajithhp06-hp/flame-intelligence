import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import httpx

logger = logging.getLogger("flame_intelligence.psi")


class NasaPsiError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class NasaPsiService:
    """Read PSI records from the repository's public first-party JSON service.

    PSI's current repository web client uses the ``/geode-py/ws/repo`` JSON
    endpoints. NASA also lists the public ``nasa-psi`` S3 bucket in its Open
    Data Registry. The PSI web endpoints are not a separately versioned API, so
    callers should treat schema changes and partial search responses as normal
    source limitations.
    """

    BASE_URL = "https://psi.nasa.gov"
    REPO_URL = f"{BASE_URL}/physci/repo/"
    API_BASE_URL = f"{BASE_URL}/geode-py/ws"
    SEARCH_API = f"{API_BASE_URL}/repo/search"
    INVESTIGATION_API = f"{API_BASE_URL}/repo/investigations"
    DOWNLOAD_API = f"{API_BASE_URL}/studies"
    PUBLIC_S3_BUCKET = "nasa-psi"
    PUBLIC_S3_REGION = "us-west-2"
    PUBLIC_S3_URL = f"https://{PUBLIC_S3_BUCKET}.s3.{PUBLIC_S3_REGION}.amazonaws.com"
    S3_REGISTRY_URL = "https://registry.opendata.aws/nasa-psi/"
    S3_XML_NAMESPACE = "http://s3.amazonaws.com/doc/2006-03-01/"
    MAX_LIST_LIMIT = 100
    MAX_DATASET_BYTES = 10 * 1024 * 1024
    ACCESSIBLE_SIGNED_HOSTS = {
        "psi-repo-prod.s3.amazonaws.com",
        "nasa-psi.s3.us-west-2.amazonaws.com",
    }

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "FLAME-INTELLIGENCE/1.0 (research metadata ingestion)",
            "Accept": "application/json",
        }
        self.last_http_status: Optional[int] = None
        self.last_error: Optional[str] = None

    async def search_investigations(
        self,
        query: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search real PSI investigation metadata with bounded paging."""

        if limit < 1 or limit > 100:
            raise ValueError("PSI page size must be between 1 and 100.")
        if offset < 0:
            raise ValueError("PSI search offset cannot be negative.")

        params: Dict[str, Any] = {"from": offset, "size": limit}
        if query and query.strip():
            params["term"] = query.strip()

        self.last_http_status = None
        self.last_error = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(self.SEARCH_API, params=params, headers=self.headers)
        except httpx.HTTPError as exc:
            self.last_error = "network_error"
            raise NasaPsiError("NASA PSI metadata search is unavailable.") from exc

        self.last_http_status = response.status_code
        if response.status_code != 200:
            self.last_error = f"http_{response.status_code}"
            raise NasaPsiError(
                f"NASA PSI metadata search returned HTTP {response.status_code}.",
                response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            self.last_error = "invalid_json"
            raise NasaPsiError("NASA PSI metadata search returned invalid JSON.", response.status_code) from exc

        hit_set = payload.get("hits") or {}
        hits = hit_set.get("hits") or []
        total = hit_set.get("total", 0)
        if isinstance(total, dict):
            total = total.get("value", 0)
        normalized = []
        for hit in hits:
            source = hit.get("_source") or {}
            accession = source.get("Accession")
            if not accession:
                continue
            normalized.append({
                "source_record_id": str(accession),
                "accession": str(accession),
                "title": source.get("Title"),
                "acronym": source.get("Acronym") or None,
                "project_type": source.get("Project Type"),
                "research_area": source.get("Research Area"),
                "sub_research_area": source.get("SubResearch Area"),
                "flight_platform": source.get("Flight Platform"),
                "objectives": source.get("Objectives"),
                "approach": source.get("Approach"),
                "public_release_date": source.get("Public Release Date"),
                "source_url": self.investigation_page_url(str(accession)),
                "search_index": hit.get("_index"),
                "raw_metadata": source,
            })

        shard_info = payload.get("_shards") or {}
        return {
            "records": normalized,
            "total": int(total or 0),
            "offset": offset,
            "limit": limit,
            "timed_out": bool(payload.get("timed_out", False)),
            "failed_shards": int(shard_info.get("failed", 0) or 0),
        }

    async def get_investigation_metadata(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Fetch an actual PSI detail record by accession or investigation acronym."""

        accession = identifier.strip()
        if not re.fullmatch(r"PSI-[A-Za-z0-9-]+", accession, re.IGNORECASE):
            search = await self.search_investigations(query=accession, limit=100)
            match = next(
                (
                    record for record in search["records"]
                    if (record.get("acronym") or "").casefold() == accession.casefold()
                ),
                None,
            )
            if match is None:
                return None
            accession = match["accession"]

        url = f"{self.INVESTIGATION_API}/{quote(accession, safe='-')}"
        self.last_http_status = None
        self.last_error = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
        except httpx.HTTPError as exc:
            self.last_error = "network_error"
            raise NasaPsiError("NASA PSI investigation metadata is unavailable.") from exc

        self.last_http_status = response.status_code
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            self.last_error = f"http_{response.status_code}"
            raise NasaPsiError(
                f"NASA PSI investigation metadata returned HTTP {response.status_code}.",
                response.status_code,
            )
        try:
            metadata = response.json()
        except ValueError as exc:
            self.last_error = "invalid_json"
            raise NasaPsiError("NASA PSI investigation endpoint returned invalid JSON.", response.status_code) from exc
        if not isinstance(metadata, dict) or not metadata.get("accession"):
            raise NasaPsiError("NASA PSI returned a detail record without an accession.", response.status_code)
        return metadata

    async def check_psi_status(self) -> Dict[str, Any]:
        """Report page/API availability separately from dataset retrieval."""

        page_status = None
        metadata_result_count = 0
        metadata_api_status = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                page_response = await client.get(self.REPO_URL, headers={"User-Agent": self.headers["User-Agent"]})
            page_status = page_response.status_code
            search_result = await self.search_investigations(limit=1)
            metadata_api_status = self.last_http_status
            metadata_result_count = len(search_result["records"])
        except Exception as exc:
            if metadata_api_status is None:
                metadata_api_status = self.last_http_status
            self.last_error = self.last_error or type(exc).__name__

        return {
            "provider": "NASA Physical Sciences Informatics (PSI)",
            "url": self.REPO_URL,
            "status_code": metadata_api_status or page_status,
            "repository_page_status": page_status,
            "metadata_api_status": metadata_api_status,
            "metadata_records_returned": metadata_result_count,
            "dataset_content_retrieved": False,
            "is_accessible": bool(page_status and page_status < 400 and metadata_api_status == 200),
            "retrieval_status": "metadata_api_available" if metadata_api_status == 200 else "unavailable",
            "details": (
                "PSI repository page and first-party metadata search were reachable. "
                "This connectivity check did not retrieve or validate dataset content."
                if page_status and page_status < 400 and metadata_api_status == 200
                else f"Repository page status={page_status}; metadata API status={metadata_api_status}; error={self.last_error or 'not available'}."
            ),
        }

    @classmethod
    def investigation_page_url(cls, accession: str) -> str:
        return f"{cls.REPO_URL}data/investigations/{quote(accession, safe='-')}"

    @classmethod
    def list_dataset_files(cls, accession: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract file references from the PSI detail response without fetching files."""

        files: List[Dict[str, Any]] = []
        seen = set()

        def visit(value: Any, category: str = ""):
            if isinstance(value, dict):
                file_name = value.get("file_name") or value.get("fileName") or value.get("filename")
                remote_path = value.get("remote_path") or value.get("s3_path") or value.get("remote_url")
                if file_name and remote_path:
                    stable_key = (str(file_name), str(remote_path))
                    if stable_key not in seen:
                        seen.add(stable_key)
                        files.append({
                            "file_name": str(file_name),
                            "category": category,
                            "remote_path": str(remote_path),
                            "file_size": _optional_nonnegative_int(value.get("file_size") or value.get("fileSize")),
                            "restricted": bool(value.get("restricted", metadata.get("restricted", False))),
                            "version": str(
                                value.get("version")
                                or value.get("file_version")
                                or value.get("fileVersion")
                                or metadata.get("version")
                                or ""
                            ),
                            "source_url": cls.investigation_page_url(accession),
                            "download_endpoint": (
                                f"{cls.DOWNLOAD_API}/{quote(accession, safe='-')}/download"
                            ),
                        })
                for key, item in value.items():
                    visit(item, key)
            elif isinstance(value, list):
                for item in value:
                    visit(item, category)

        visit(metadata)
        return files

    async def download_dataset_file(
        self,
        accession: str,
        file_reference: Dict[str, Any],
        max_bytes: int = MAX_DATASET_BYTES,
    ) -> Dict[str, Any]:
        """Download one explicitly selected, public PSI file under a strict byte cap."""

        if max_bytes < 1 or max_bytes > self.MAX_DATASET_BYTES:
            raise ValueError(f"Dataset download limit must be between 1 and {self.MAX_DATASET_BYTES} bytes.")
        name = file_reference.get("file_name")
        if not name:
            raise ValueError("A PSI file reference with a file_name is required.")
        if file_reference.get("restricted"):
            raise NasaPsiError("The selected PSI file is marked restricted and was not downloaded.")
        if file_reference.get("file_size") is not None and file_reference["file_size"] > max_bytes:
            raise NasaPsiError(
                f"The PSI file is {file_reference['file_size']} bytes, above the configured {max_bytes}-byte download cap."
            )

        params = {
            "file": name,
            "version": str(file_reference.get("version") or ""),
            "redirect": "false",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                link_response = await client.get(
                    f"{self.DOWNLOAD_API}/{quote(accession, safe='-')}/download",
                    params=params,
                    headers={"User-Agent": self.headers["User-Agent"]},
                )
                self.last_http_status = link_response.status_code
                if link_response.status_code != 200:
                    raise NasaPsiError(
                        f"NASA PSI download-link request returned HTTP {link_response.status_code}.",
                        link_response.status_code,
                    )
                signed_url = link_response.text.strip().strip('"')
                if link_response.headers.get("content-type", "").lower().startswith("application/json"):
                    try:
                        link_payload = link_response.json()
                    except ValueError:
                        link_payload = None
                    if isinstance(link_payload, str):
                        signed_url = link_payload
                    elif isinstance(link_payload, dict):
                        signed_url = link_payload.get("url") or link_payload.get("download_url") or ""
                parsed = urlparse(signed_url)
                if parsed.scheme != "https" or parsed.hostname not in self.ACCESSIBLE_SIGNED_HOSTS:
                    raise NasaPsiError("NASA PSI returned an unsupported dataset download host.")

                async with client.stream("GET", signed_url) as dataset_response:
                    self.last_http_status = dataset_response.status_code
                    if dataset_response.status_code != 200:
                        raise NasaPsiError(
                            f"NASA PSI dataset download returned HTTP {dataset_response.status_code}.",
                            dataset_response.status_code,
                        )
                    declared_size = _optional_nonnegative_int(dataset_response.headers.get("content-length"))
                    if declared_size is not None and declared_size > max_bytes:
                        raise NasaPsiError(
                            f"The PSI file is {declared_size} bytes, above the configured {max_bytes}-byte download cap."
                        )
                    chunks = bytearray()
                    async for chunk in dataset_response.aiter_bytes():
                        if len(chunks) + len(chunk) > max_bytes:
                            raise NasaPsiError("PSI dataset download exceeded the configured byte cap.")
                        chunks.extend(chunk)
                    content = bytes(chunks)
                    if file_reference.get("file_size") is not None and len(content) != file_reference["file_size"]:
                        raise NasaPsiError("Downloaded PSI file size does not match the source metadata.")
                    if declared_size is not None and len(content) != declared_size:
                        raise NasaPsiError("Downloaded PSI file size does not match the HTTP content length.")
                    return {
                        "content": content,
                        "content_type": dataset_response.headers.get("content-type"),
                        "size_bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        # Store the stable, public PSI record URL. Never persist the
                        # short-lived signed URL returned by the download endpoint.
                        "source_url": file_reference.get("source_url")
                        or self.investigation_page_url(accession),
                        "accession": accession,
                        "file_name": name,
                        "version": params["version"],
                    }
        except httpx.HTTPError as exc:
            self.last_error = "network_error"
            raise NasaPsiError("NASA PSI dataset retrieval failed due to a network error.") from exc

    async def list_public_s3_objects(
        self,
        prefix: str = "",
        limit: int = 100,
        continuation_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List public PSI registry object metadata; this is not a content download."""

        if limit < 1 or limit > 1000:
            raise ValueError("Public PSI S3 page size must be between 1 and 1000.")
        if prefix.startswith("/") or ".." in prefix.split("/"):
            raise ValueError("Invalid PSI S3 prefix.")
        params: Dict[str, Any] = {"list-type": "2", "prefix": prefix, "max-keys": limit}
        if continuation_token:
            params["continuation-token"] = continuation_token
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(self.PUBLIC_S3_URL, params=params)
        except httpx.HTTPError as exc:
            raise NasaPsiError("NASA PSI public S3 object listing is unavailable.") from exc
        self.last_http_status = response.status_code
        if response.status_code != 200:
            raise NasaPsiError(
                f"NASA PSI public S3 object listing returned HTTP {response.status_code}.",
                response.status_code,
            )
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise NasaPsiError("NASA PSI public S3 returned invalid XML.", response.status_code) from exc
        ns = {"s3": self.S3_XML_NAMESPACE}
        objects = []
        for item in root.findall("s3:Contents", ns):
            key = item.findtext("s3:Key", namespaces=ns)
            if not key:
                continue
            objects.append({
                "key": key,
                "size_bytes": _optional_nonnegative_int(item.findtext("s3:Size", namespaces=ns)) or 0,
                "last_modified": item.findtext("s3:LastModified", namespaces=ns),
                "etag": (item.findtext("s3:ETag", namespaces=ns) or "").strip('"') or None,
                "url": f"{self.PUBLIC_S3_URL}/{quote(key, safe='/')}",
            })
        return {
            "objects": objects,
            "prefixes": [
                item.findtext("s3:Prefix", namespaces=ns)
                for item in root.findall("s3:CommonPrefixes", ns)
                if item.findtext("s3:Prefix", namespaces=ns)
            ],
            "is_truncated": (root.findtext("s3:IsTruncated", namespaces=ns) or "false").lower() == "true",
            "next_continuation_token": root.findtext("s3:NextContinuationToken", namespaces=ns),
        }

    async def download_public_s3_object(self, key: str, max_bytes: int = MAX_DATASET_BYTES) -> Dict[str, Any]:
        """Download one public registry object only when its size fits the byte cap."""

        if max_bytes < 1 or max_bytes > self.MAX_DATASET_BYTES:
            raise ValueError(f"Dataset download limit must be between 1 and {self.MAX_DATASET_BYTES} bytes.")
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise ValueError("Invalid PSI S3 object key.")
        url = f"{self.PUBLIC_S3_URL}/{quote(key, safe='/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                async with client.stream("GET", url) as response:
                    self.last_http_status = response.status_code
                    if response.status_code != 200:
                        raise NasaPsiError(
                            f"NASA PSI S3 object retrieval returned HTTP {response.status_code}.",
                            response.status_code,
                        )
                    size = _optional_nonnegative_int(response.headers.get("content-length"))
                    if size is not None and size > max_bytes:
                        raise NasaPsiError(
                            f"The PSI S3 object is {size} bytes, above the configured {max_bytes}-byte download cap."
                        )
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(chunks) + len(chunk) > max_bytes:
                            raise NasaPsiError("PSI S3 object exceeded the configured byte cap.")
                        chunks.extend(chunk)
                    content = bytes(chunks)
                    if size is not None and len(content) != size:
                        raise NasaPsiError("PSI S3 object size does not match the HTTP content length.")
                    return {
                        "content": content,
                        "content_type": response.headers.get("content-type"),
                        "size_bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "source_url": url,
                        "key": key,
                    }
        except httpx.HTTPError as exc:
            raise NasaPsiError("NASA PSI S3 object retrieval failed due to a network error.") from exc


def _optional_nonnegative_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None
