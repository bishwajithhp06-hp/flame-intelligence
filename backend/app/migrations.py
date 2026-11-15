"""Small additive migrations for the existing SQLAlchemy database."""

from sqlalchemy import inspect


SOURCE_REFERENCE_COLUMNS = {
    "retrieval_status": "VARCHAR(50) NOT NULL DEFAULT 'not_attempted'",
    "last_retrieved_at": "DATETIME NULL",
    "last_http_status": "INTEGER NULL",
    "data_type": "VARCHAR(150) NULL",
    "provenance_status": "VARCHAR(100) NOT NULL DEFAULT 'unclassified'",
    "access_limitations": "TEXT NULL",
}


def apply_additive_migrations(engine):
    """Add source-register columns without rewriting or dropping existing rows."""

    inspector = inspect(engine)
    if "source_references" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("source_references")}
    missing = [
        (name, definition)
        for name, definition in SOURCE_REFERENCE_COLUMNS.items()
        if name not in existing
    ]
    if not missing:
        return

    # Names and SQL fragments come only from the constant above.
    with engine.begin() as connection:
        for name, definition in missing:
            connection.exec_driver_sql(
                f"ALTER TABLE source_references ADD COLUMN {name} {definition}"
            )
