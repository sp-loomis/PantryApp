"""
Ledger stream consumer — writes ledger events to S3 as partitioned JSONL.

Triggered by the ledger table's DynamoDB stream (NEW_IMAGE). Each INSERT is a new
append-only event; this flattens the DynamoDB-typed image to plain JSON and writes
it to ``s3://$ANALYTICS_BUCKET/$ANALYTICS_PREFIX/dt=YYYY-MM-DD/<uuid>.jsonl``,
partitioned by the event's ``occurred_at`` date so Athena (with partition
projection) can scan by date range.

Dependency-light: stdlib + boto3 (already in the Lambda runtime). No pyarrow /
Parquet — JSONL keeps packaging trivial and the pipeline scale-to-zero.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer

_s3 = boto3.client("s3")
_BUCKET = os.environ["ANALYTICS_BUCKET"]
_PREFIX = os.environ.get("ANALYTICS_PREFIX", "events").strip("/")
_deser = TypeDeserializer()


def _normalize(value):
    """Make a deserialized value JSON-serializable (Decimal -> int/float)."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    return value


def _plain(image):
    return {k: _normalize(_deser.deserialize(v)) for k, v in image.items()}


def handler(event, context):
    """Write new ledger events to S3, grouped into one object per event date."""
    by_date = {}
    for record in event.get("Records", []):
        # Append-only table: only INSERTs matter. (A future TTL would emit REMOVE
        # events, which we intentionally ignore.)
        if record.get("eventName") != "INSERT":
            continue
        image = record.get("dynamodb", {}).get("NewImage")
        if not image:
            continue
        row = _plain(image)
        occurred = row.get("occurred_at") or datetime.now(timezone.utc).isoformat()
        day = occurred[:10]
        by_date.setdefault(day, []).append(json.dumps(row, separators=(",", ":")))

    written = 0
    for day, lines in by_date.items():
        key = f"{_PREFIX}/dt={day}/{uuid.uuid4().hex}.jsonl"
        _s3.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=("\n".join(lines) + "\n").encode("utf-8"),
            ContentType="application/x-ndjson",
        )
        written += len(lines)

    return {"written": written, "dates": sorted(by_date)}
