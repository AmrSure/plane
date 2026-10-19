# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Keep uploaded Jira exports in object storage so the API and worker containers can share them."""

import io

from plane.settings.storage import S3Storage


def store_file(object_name: str, content: bytes) -> bool:
    return S3Storage(request=None).upload_file(io.BytesIO(content), object_name, content_type="text/csv")


def load_file(object_name: str) -> bytes:
    storage = S3Storage(request=None)
    response = storage.s3_client.get_object(Bucket=storage.aws_storage_bucket_name, Key=object_name)
    return response["Body"].read()


def delete_file(object_name: str) -> None:
    if object_name:
        S3Storage(request=None).delete_files([object_name])
