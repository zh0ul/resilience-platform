"""S3-compatible data-path semantics against the Qumulo S3 endpoint."""

from __future__ import annotations

import io
import uuid

import pytest

from resilience_platform.checksums import deterministic_payload, sha256_hex
from resilience_platform.safety import assert_s3_key_allowed
from resilience_platform.settings import Settings

pytestmark = [pytest.mark.s3, pytest.mark.live, pytest.mark.destructive]


def _run_prefix(settings: Settings) -> str:
    return f"{settings.effective_run_id}/"


@pytest.mark.parametrize("size", [4096, 1024 * 1024])
def test_s3_put_head_get_checksum_roundtrip(
    s3_client,
    settings: Settings,
    size: int,
) -> None:
    """PUT/HEAD/GET must preserve bytes and content length."""
    key = f"{_run_prefix(settings)}put-get-{uuid.uuid4().hex}.bin"
    assert_s3_key_allowed(key, settings)
    payload = deterministic_payload(size, seed=101)
    digest = sha256_hex(payload)

    s3_client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=payload,
        Metadata={"sha256": digest, "resilience-seed": "101"},
    )

    head = s3_client.head_object(Bucket=settings.s3_bucket, Key=key)
    assert int(head["ContentLength"]) == size
    assert head["Metadata"].get("sha256") == digest

    got = s3_client.get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()
    assert sha256_hex(got) == digest

    s3_client.delete_object(Bucket=settings.s3_bucket, Key=key)


def test_s3_multipart_upload_integrity(s3_client, settings: Settings) -> None:
    """Multipart upload must assemble to the same checksum as a single PUT."""
    key = f"{_run_prefix(settings)}multipart-{uuid.uuid4().hex}.bin"
    assert_s3_key_allowed(key, settings)
    part_size = 5 * 1024 * 1024
    parts = [deterministic_payload(part_size, seed=200 + i) for i in range(3)]
    expected = b"".join(parts)
    expected_digest = sha256_hex(expected)

    upload = s3_client.create_multipart_upload(
        Bucket=settings.s3_bucket,
        Key=key,
        Metadata={"sha256": expected_digest},
    )
    upload_id = upload["UploadId"]
    etags: list[dict[str, str | int]] = []

    try:
        for index, part in enumerate(parts, start=1):
            response = s3_client.upload_part(
                Bucket=settings.s3_bucket,
                Key=key,
                PartNumber=index,
                UploadId=upload_id,
                Body=io.BytesIO(part),
            )
            etags.append({"ETag": response["ETag"], "PartNumber": index})

        s3_client.complete_multipart_upload(
            Bucket=settings.s3_bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": etags},
        )
    except Exception:
        s3_client.abort_multipart_upload(Bucket=settings.s3_bucket, Key=key, UploadId=upload_id)
        raise

    got = s3_client.get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()
    assert sha256_hex(got) == expected_digest
    s3_client.delete_object(Bucket=settings.s3_bucket, Key=key)


def test_s3_paginated_listing_and_cleanup(s3_client, settings: Settings) -> None:
    """ListObjectsV2 pagination must find seeded keys; cleanup removes only run prefix."""
    prefix = _run_prefix(settings)
    seeded_keys = [f"{prefix}list-{i:03d}.txt" for i in range(15)]
    for key in seeded_keys:
        assert_s3_key_allowed(key, settings)
        s3_client.put_object(Bucket=settings.s3_bucket, Key=key, Body=f"seed-{key}".encode())

    found: set[str] = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            found.add(obj["Key"])

    assert set(seeded_keys).issubset(found)

    for key in seeded_keys:
        s3_client.delete_object(Bucket=settings.s3_bucket, Key=key)

    remaining = s3_client.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
    assert remaining.get("KeyCount", 0) == 0

