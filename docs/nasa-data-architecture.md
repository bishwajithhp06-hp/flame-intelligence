# NASA Data Architecture and Integration

## Access paths and limits

The NASA Physical Sciences Informatics (PSI) repository's current web client uses first-party JSON endpoints:

- Investigation search: `GET https://psi.nasa.gov/geode-py/ws/repo/search?term={query}&from={offset}&size={limit}`
- Investigation detail: `GET https://psi.nasa.gov/geode-py/ws/repo/investigations/{accession}`
- Selected-file download link: `GET https://psi.nasa.gov/geode-py/ws/studies/{accession}/download?file={name}&version={version}&redirect=false`

These are PSI web-application endpoints, not a separately versioned public API. Search may return partial shard results; consumers must inspect the response and may not treat a search count as complete retrieval. Investigation detail lists file names, access flags, versions and paths. File content is retrieved only when a user explicitly selects an accession and exact file name. Downloads are capped at 10 MiB by default (and never above that service limit). A short-lived signed URL is validated and used in memory; it is never written to logs or the database. Restricted files and files above the cap are rejected.

NASA also lists the public `nasa-psi` bucket in the [AWS Registry of Open Data](https://registry.opendata.aws/nasa-psi/). Its object listing is paginated. The CLI can save an object manifest; it does not imply object content was downloaded. File download requires an explicit key and the same byte cap. The PSI repository guide describes request workflows for large files, so this application does not attempt bulk downloads.

NASA NTRS metadata uses `POST https://ntrs.nasa.gov/api/citations/search` with `q` and `page.from/page.size`. The service follows result pages up to the requested bounded limit and deduplicates by the stable NTRS citation ID. It captures full abstracts and available author, publication-date, DOI and download-link metadata. It does not download reports. An NTRS citation is publication metadata, not provenance for a particular numerical measurement.

Official references: [NASA PSI repository](https://psi.nasa.gov/physci/repo), [NASA PSI Researcher Guide](https://www.nasa.gov/wp-content/uploads/2020/05/psi_researchers_guide-tagged.pdf), [NASA PSI database guide](https://assets.science.nasa.gov/content/dam/science/bps/bps-general/bps-data_osdr_psi/Complete_PSI_Database_Guide.pdf), [NASA large-file request workflow](https://science.nasa.gov/uncategorized/new-file-download-process-for-large-requestspsi-new-file-download-process/), and [NTRS API documentation](https://ntrs.nasa.gov/api/openapi/).

## Storage model

`source_references` remains the source register and retains its existing identifiers and columns. New fields track retrieval state, last retrieval time, HTTP status, data type, provenance classification and access limits. Startup adds missing fields to an existing SQLite database without replacing rows.

`raw_source_records` stores immutable hash-addressed source snapshots. It retains source identifier, stable source URL, retrieval timestamp, content type, SHA-256, byte length and either the original JSON response or explicitly retrieved file bytes. A duplicate retrieval of identical bytes/JSON reuses its raw snapshot.

`processed_research_records` stores normalized investigation, citation, dataset-file or public-object metadata and links to the raw snapshot. A record is upserted by source, record kind and source identifier. A changed response creates a new raw snapshot and updates the normalized row to point at it; earlier raw snapshots remain intact.

The ingestion service does **not** parse numeric rows from downloaded files into `combustion_datapoints`. For CSV files it records the header names and raw file hash only. It does not convert units or infer missing conditions. Existing local datapoints are not promoted by the presence of a NASA publication or an investigation citation.

## Data dictionary

| Table / field | Type | Meaning / units | Missing-value and allowed-value handling |
|---|---|---|---|
| `source_references.resource_id` | string | Stable register key, such as `NASA-PSI-REPO`, `NASA-PSI-S3`, `NASA-NTRS-API` | Unique by service-level upsert; never replaces unrelated source rows |
| `source_references.retrieval_status` | string | `not_attempted`, `retrieved`, `partial`, `retrieved_empty`, `failed`, or workflow-specific retrieval state | Updated only after that source workflow runs |
| `source_references.last_retrieved_at` | UTC datetime | Last source retrieval attempt | Null until a retrieval attempt |
| `source_references.last_http_status` | integer | Most recent observed HTTP status | Null for a failure before an HTTP response |
| `source_references.data_type` | string | Metadata, dataset, object listing or publication metadata | No claim of measurement validation |
| `source_references.provenance_status` | string | Source-level provenance category | Does not certify every measurement in a source |
| `source_references.access_limitations` | text | Restriction, pagination and size-limit notes | Empty only when none are known |
| `raw_source_records.record_kind` | string | `psi_investigation`, `psi_dataset_file`, `psi_s3_object_metadata`, `ntrs_publication` | A new kind is not a new measurement classification |
| `raw_source_records.source_record_id` | string | PSI accession, NTRS ID, object key or accession/file/version | Required; original source identifier is preserved |
| `raw_source_records.source_url` | string | Stable public record/object URL; never a pre-signed URL | Required; pre-signed tokens are not persisted |
| `raw_source_records.retrieved_at` | UTC datetime | Time source content was captured | Required |
| `raw_source_records.payload_json` | JSON text | Original retrieved metadata | Null for binary file snapshots |
| `raw_source_records.payload_bytes` | binary | Explicitly retrieved file bytes | Null for metadata-only snapshots |
| `raw_source_records.payload_sha256` | 64-character hex string | Content identity and deduplication key | Required for both JSON and file content |
| `raw_source_records.payload_size_bytes` | integer, bytes | Byte length of saved payload | Required; not an experimental value |
| `processed_research_records.record_kind` | string | Source-specific normalized record type | See raw record kinds |
| `processed_research_records.source_record_id` | string | Stable source identifier | Required |
| `processed_research_records.raw_record_id` | integer FK | Raw snapshot supporting normalized fields | Required; one current raw snapshot per normalized row |
| `processed_research_records.title`, `description` | text | Source-provided title and text | Null if the source omits the field; no synthesized source claims |
| `processed_research_records.investigators_json` | JSON text | Source-provided investigator/contact metadata | `[]` when absent |
| `processed_research_records.publication_references_json` | JSON text | Source-listed publication metadata | `[]` when absent; does not verify measurements |
| `processed_research_records.dataset_links_json` | JSON text | Source-listed files, access flags and paths | `[]` when absent; listing is not a retrieval |
| `processed_research_records.experiment_context_type` | string | `flight_experiment`, `ground_experiment`, `simulation`, or `unknown` | Conservative metadata classification; not a proof of flight provenance |
| `processed_research_records.material_classification` | string | Source-described material/fuel text | Null if not available; no inferred material testing |
| `processed_research_records.units_json` | JSON text | Source unit/header notes and conversion flags | Empty object if absent; no implicit conversion |
| `processed_research_records.normalized_metadata_json` | JSON text | Normalized source metadata and explicit non-validation flags | Source fields stay traceable to the raw snapshot |
| `processed_research_records.provenance_category` | string | One of the categories below | Required |
| `processed_research_records.retrieved_at` | UTC datetime | Time the normalized view was last updated | Required |

`experiment_context_type` is contextual metadata. The separate evidence provenance categories are:

- `nasa_origin_source_link_verified`: record was retrieved from a NASA-controlled PSI path or the NASA-listed public PSI bucket; this verifies linkage, not experimental conditions or measurements.
- `publication_metadata_only`: NTRS or PSI-linked publication citation; not measurement provenance.
- `measurement_provenance_unverified`: local numeric information without a verified path to its original experiment data.
- `local_seed_record_provenance_unverified`: existing application seed record that has not been independently source-verified.
- `user_provided_or_hypothetical`: scenario input; never NASA evidence.

The existing local 12 datapoints remain local/unverified. Their legacy `is_measured_flight_data` flag is not accepted as proof and the ingestion layer never reads or modifies it.

## Mission evidence behavior

The Mission Evidence Service includes source-linked PSI investigation metadata and citations from stored NTRS publication records. PSI investigation source links can be cited as NASA-origin records, but their condition text remains context until validated against the actual experiment data. NTRS remains publication context only. The service does not import PSI numeric file rows, combine conditions across investigations, infer lunar gravity from microgravity, or mark the full hypothetical combination as tested. User parameters are stored in the mission request/response contract, not rewritten as NASA test data.

## Phase 4 read-only explorer and reports

`GET /api/experiments` reads only persisted `psi_investigation` and `ntrs_publication` rows. Search uses source-provided titles and descriptions; material, gravity and environment filters are populated only when those fields are explicitly structured in normalized source metadata. Narrative text is not promoted to an experimental condition. `GET /api/experiments/{record_id}` includes source and citation links plus linked PSI file retrieval state. A raw file payload is reported as downloaded bytes; the explorer does not call it parsed measurement data unless the stored parsing flag says so.

`POST /api/experiments/compare` accepts two stored record IDs. It reports shared structured categorical fields and quantitative fields only when both records provide numeric values with recognized compatible units. It emits no similarity score and warns that field overlap does not establish scientific equivalence or a jointly tested scenario. The endpoint is read-only.

`POST /api/reports/mission` accepts the typed mission-analysis response and returns a PDF containing the supplied scenario, specialist outputs, evidence references, gaps, provenance limits, and generation time. It does not persist the report or mission history. The Mission Intelligence screen's parameter graphic plots only the user's input values against the UI control ranges; it is labeled as a data-derived input visualization, not a flame model or observation. Earth-impact display is informational because the stored record set does not contain validated scenario impact factors.

## Commands

Run from `backend/` after the Python environment and database are configured:

```powershell
python -m app.nasa_ingest --source psi --query FLEX --limit 5
python -m app.nasa_ingest --source ntrs --query "microgravity combustion" --limit 20
python -m app.nasa_ingest --source s3 --prefix DSI/ --limit 100
python -m app.nasa_ingest --source s3 --prefix DSI/ --limit 100 --continuation-token "TOKEN_FROM_PREVIOUS_PAGE"
python -m app.nasa_ingest --source s3 --download-key "DSI/example.csv" --max-bytes 10485760
python -m app.nasa_ingest --source psi --download-accession PSI-69 --file-name "PSI-69_Experimental table_FLEX.csv"
python -m unittest discover -s tests -v
```

The file-download command stores raw bytes only if the named file is listed, unrestricted, and within the configured cap. Repeating ingestion is safe: raw payloads are content-addressed and processed rows are upserted. Inspect `/api/sources` for source-register state. `/api/sources/check` tests availability only and does not mean records were ingested.

## Verification status and known limitations

NASA PSI search/detail/download endpoints and NTRS citation search were queried during implementation. A public PSI-69 experimental-table object was separately retrieved at the source layer under the 10 MiB limit; retrieval and hash/size were checked. These source-layer checks do not mean the current project database has completed a bulk PSI ingest. Use the CLI command above for an explicit, recorded ingest. PSI JSON endpoints are not separately versioned; partial search shards and access restrictions remain possible. Large-file request workflows are not automated. Live Gemini verification remains separate from NASA data retrieval and is still pending due to the previously reported quota exhaustion.
