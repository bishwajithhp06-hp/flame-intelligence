"""Command-line entry point for explicit NASA metadata/file ingestion.

Run from the backend directory, for example:
    python -m app.nasa_ingest --source psi --query FLEX --limit 5
    python -m app.nasa_ingest --source ntrs --query microgravity combustion --limit 20
    python -m app.nasa_ingest --source psi --download-accession PSI-69 --file-name "PSI-69_Experimental table_FLEX.csv"
    python -m app.nasa_ingest --source s3 --prefix DSI/ --limit 100
"""

import argparse
import asyncio
import json
import logging

from app.database import Base, SessionLocal, engine
from app.migrations import apply_additive_migrations
from app.services.nasa_data_ingestion_service import NasaDataIngestionService


def parser():
    command = argparse.ArgumentParser(description="Retrieve and persist public NASA PSI/NTRS metadata.")
    command.add_argument("--source", choices=("psi", "ntrs", "s3"), required=True)
    command.add_argument("--query", default="combustion", help="Search term for PSI or NTRS.")
    command.add_argument("--limit", type=int, default=20, help="Maximum metadata records or S3 objects.")
    command.add_argument("--prefix", default="", help="Prefix when listing the public PSI S3 bucket.")
    command.add_argument("--continuation-token", help="Continue a public PSI S3 object listing.")
    command.add_argument("--download-key", help="Explicit key for one bounded public PSI S3 object download.")
    command.add_argument("--download-accession", help="Explicit PSI accession for one bounded file download.")
    command.add_argument("--file-name", help="Exact PSI file name listed in its investigation metadata.")
    command.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    command.add_argument("--verbose", action="store_true")
    return command


async def run(args):
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    db = SessionLocal()
    service = NasaDataIngestionService()
    try:
        service.ensure_source_register(db)
        db.commit()
        if args.source == "psi" and args.download_accession:
            if not args.file_name:
                raise ValueError("--file-name is required with --download-accession.")
            return await service.ingest_psi_dataset(
                db, args.download_accession, args.file_name, max_bytes=args.max_bytes
            )
        if args.source == "psi":
            return await service.ingest_psi_investigations(db, args.query, args.limit)
        if args.source == "ntrs":
            return await service.ingest_ntrs(db, args.query, args.limit)
        if args.download_key:
            return await service.ingest_psi_s3_object(db, args.download_key, max_bytes=args.max_bytes)
        return await service.ingest_psi_s3_listing(
            db, args.prefix, args.limit, continuation_token=args.continuation_token
        )
    finally:
        db.close()


def main():
    args = parser().parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    try:
        result = asyncio.run(run(args))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "message": str(exc)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
