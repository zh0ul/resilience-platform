"""Typed configuration loaded from environment variables."""

from __future__ import annotations

import os
import uuid
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for resilience tests."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Safety
    enable_live_tests: bool = Field(default=False, alias="RESILIENCE_ENABLE_LIVE_TESTS")
    ack_disposable_target: bool = Field(default=False, alias="RESILIENCE_ACK_DISPOSABLE_TARGET")
    env_label: str = Field(default="", alias="RESILIENCE_ENV_LABEL")
    allowed_env_labels: str = Field(
        default="disposable-vm,sandbox,lab-vm",
        alias="RESILIENCE_ALLOWED_ENV_LABELS",
    )

    # Qumulo REST
    qumulo_host: str = Field(default="", alias="QUMULO_HOST")
    qumulo_user: str = Field(default="", alias="QUMULO_USER")
    qumulo_password: str = Field(default="", alias="QUMULO_PASSWORD")
    qumulo_rest_port: int = Field(default=8000, alias="QUMULO_REST_PORT")
    qumulo_ca_bundle: str = Field(default="", alias="QUMULO_CA_BUNDLE")
    qumulo_verify_tls: bool = Field(default=True, alias="QUMULO_VERIFY_TLS")

    # Fixture namespace
    fixture_root: str = Field(default="/resilience-fixtures", alias="RESILIENCE_FIXTURE_ROOT")
    s3_bucket: str = Field(default="resilience-fixtures", alias="RESILIENCE_S3_BUCKET")
    run_id: str = Field(default="", alias="RESILIENCE_RUN_ID")

    # S3
    qumulo_s3_endpoint: str = Field(default="", alias="QUMULO_S3_ENDPOINT")
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_default_region: str = Field(default="us-east-1", alias="AWS_DEFAULT_REGION")

    # NFS
    qumulo_nfs_export: str = Field(default="", alias="QUMULO_NFS_EXPORT")
    nfs_mount_path: Path = Field(default=Path("/mnt/qumulo-nfs"), alias="RESILIENCE_NFS_MOUNT")

    # SMB
    qumulo_smb_server: str = Field(default="", alias="QUMULO_SMB_SERVER")
    qumulo_smb_share: str = Field(default="", alias="QUMULO_SMB_SHARE")
    qumulo_smb_user: str = Field(default="", alias="QUMULO_SMB_USER")
    qumulo_smb_password: str = Field(default="", alias="QUMULO_SMB_PASSWORD")
    qumulo_smb_domain: str = Field(default="", alias="QUMULO_SMB_DOMAIN")
    smb_mount_path: Path = Field(default=Path("/mnt/qumulo-smb"), alias="RESILIENCE_SMB_MOUNT")

    # Evidence
    evidence_dir: Path = Field(default=Path("evidence"), alias="RESILIENCE_EVIDENCE_DIR")

    @field_validator("fixture_root")
    @classmethod
    def fixture_root_must_not_be_root(cls, value: str) -> str:
        normalized = value.rstrip("/") or "/"
        if normalized == "/":
            msg = "fixture_root must not be filesystem root"
            raise ValueError(msg)
        return value.rstrip("/")

    @property
    def allowed_env_label_set(self) -> set[str]:
        return {label.strip() for label in self.allowed_env_labels.split(",") if label.strip()}

    @property
    def effective_run_id(self) -> str:
        return self.run_id or os.environ.get("RESILIENCE_RUN_ID") or uuid.uuid4().hex[:12]

    @property
    def rest_base_url(self) -> str:
        return f"https://{self.qumulo_host}:{self.qumulo_rest_port}"

    @property
    def run_namespace(self) -> str:
        return f"{self.fixture_root}/{self.effective_run_id}"

    @property
    def tls_verify(self) -> bool | str:
        if not self.qumulo_verify_tls:
            return False
        if self.qumulo_ca_bundle:
            return self.qumulo_ca_bundle
        return True

    def live_rest_configured(self) -> bool:
        return bool(self.qumulo_host and self.qumulo_user and self.qumulo_password)

    def live_s3_configured(self) -> bool:
        return bool(
            self.qumulo_s3_endpoint
            and self.aws_access_key_id
            and self.aws_secret_access_key
            and self.s3_bucket
        )

    def live_nfs_configured(self) -> bool:
        return bool(self.qumulo_nfs_export and self.nfs_mount_path.exists())

    def live_smb_configured(self) -> bool:
        return bool(
            self.qumulo_smb_server
            and self.qumulo_smb_share
            and self.qumulo_smb_user
            and self.qumulo_smb_password
            and self.smb_mount_path.exists()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
