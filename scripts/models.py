"""
Pydantic models for fleet.yaml configuration validation.

Validates fleet configuration before generating deployment configs,
catching logical errors early with clear error messages.
"""

import sys
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Import ASSET_TYPE_METADATA as the single source of truth for valid asset types
sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module
generate_configs = import_module('generate-configs')
ASSET_TYPE_METADATA = generate_configs.ASSET_TYPE_METADATA

# Tracked asset types (no agent, FC-managed only)
TrackedAssetType = Literal['supervisor_truck', 'service_truck', 'work_truck']


class OperatorConfig(BaseModel):
    """Configuration for an asset operator."""
    name: str = Field(..., min_length=1, description="Operator's full name")
    telegram: str = Field(..., pattern=r'^@?\w+$', description="Telegram username")
    consumption_rate: Optional[float] = Field(None, ge=0, description="Operator's typical consumption rate")
    notes: Optional[str] = None


class BaseSpecs(BaseModel):
    """Base specifications common to most assets."""
    tank_capacity: float = Field(0, ge=0, description="Fuel tank capacity in liters")
    avg_consumption: float = Field(0, ge=0, description="Average consumption rate")
    min_consumption: float = Field(0, ge=0, description="Minimum consumption rate")
    max_consumption: float = Field(0, ge=0, description="Maximum consumption rate")

    @model_validator(mode='after')
    def validate_consumption_order(self) -> 'BaseSpecs':
        """Ensure min <= avg <= max for consumption rates."""
        if self.min_consumption > 0 and self.avg_consumption > 0:
            if self.min_consumption > self.avg_consumption:
                raise ValueError(
                    f'min_consumption ({self.min_consumption}) cannot exceed '
                    f'avg_consumption ({self.avg_consumption})'
                )
        if self.avg_consumption > 0 and self.max_consumption > 0:
            if self.avg_consumption > self.max_consumption:
                raise ValueError(
                    f'avg_consumption ({self.avg_consumption}) cannot exceed '
                    f'max_consumption ({self.max_consumption})'
                )
        return self


class ExcavatorSpecs(BaseSpecs):
    """Specifications for excavator assets."""
    weight_tons: float = Field(0, ge=0)
    bucket_capacity: float = Field(0, ge=0)
    max_dig_depth: float = Field(0, ge=0)
    max_reach: float = Field(0, ge=0)


class LoaderSpecs(BaseSpecs):
    """Specifications for loader assets."""
    weight_tons: float = Field(0, ge=0)
    bucket_capacity: float = Field(0, ge=0)
    payload_tons: float = Field(0, ge=0)
    dump_clearance: float = Field(0, ge=0)
    max_reach: float = Field(0, ge=0)


class InitialState(BaseModel):
    """Initial state values for an asset."""
    hours: float = Field(0, ge=0)
    km: Optional[float] = Field(None, ge=0)
    lat: float = 0
    lon: float = 0


class MaterialConfig(BaseModel):
    """Material handling configuration."""
    primary: str = 'Unknown'


class AssetConfig(BaseModel):
    """Configuration for a single fleet asset."""
    asset_id: str = Field(..., min_length=1, pattern=r'^[A-Z0-9-]+$',
                          description="Unique asset identifier (e.g., EX-001)")
    type: str = Field(..., description="Asset type (validated against ASSET_TYPE_METADATA)")
    make: str = 'Unknown'
    model: str = 'Unknown'
    serial: Optional[str] = None
    year: Optional[int] = Field(None, ge=1900, le=2100)
    host: str = Field(..., min_length=1, description="Host name for deployment")

    specs: dict = Field(default_factory=dict)
    initial: InitialState = Field(default_factory=InitialState)
    material: Optional[MaterialConfig] = None
    operators: list[OperatorConfig] = Field(default_factory=list)

    telegram_group: str = Field('', description="Telegram group for this asset")
    language: str = 'English'
    timezone: str = 'UTC'
    nickname: Optional[str] = None

    @field_validator('type')
    @classmethod
    def validate_asset_type(cls, v: str) -> str:
        """Validate asset type against ASSET_TYPE_METADATA (single source of truth)."""
        if v not in ASSET_TYPE_METADATA:
            valid = sorted(ASSET_TYPE_METADATA.keys())
            raise ValueError(
                f"Invalid asset type '{v}'. Valid types: {valid[:10]}... "
                f"(see ASSET_TYPE_METADATA in generate-configs.py)"
            )
        return v

    @field_validator('telegram_group')
    @classmethod
    def validate_telegram_group(cls, v: str) -> str:
        """Ensure telegram group has proper format."""
        if v and not v.startswith('@'):
            return f'@{v}'
        return v


class ContactConfig(BaseModel):
    """Contact information for escalation."""
    name: Optional[str] = None
    telegram: str = Field('', pattern=r'^@?\w*$')


class CoordinatorConfig(BaseModel):
    """Fleet Coordinator configuration."""
    asset_id: str = 'FLEET-COORD'
    telegram_group: str = ''
    telegram_user: str = ''
    host: str = Field(..., min_length=1)

    hourly_summary: bool = True
    daily_report_time: str = Field('18:00', pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    shift_start: str = Field('06:00', pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    shift_end: str = Field('18:00', pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

    manager: ContactConfig = Field(default_factory=ContactConfig)
    safety: ContactConfig = Field(default_factory=ContactConfig)
    owner: ContactConfig = Field(default_factory=ContactConfig)


class HostConfig(BaseModel):
    """Host deployment configuration."""
    name: str = Field(..., min_length=1, pattern=r'^[a-z0-9-]+$')
    assets: list[str] = Field(default_factory=list)
    redis: bool = False


class RedisConfig(BaseModel):
    """Redis configuration."""
    host: str = 'redis'
    port: int = Field(6379, ge=1, le=65535)
    password: Optional[str] = None


class EscalationConfig(BaseModel):
    """Escalation contacts configuration."""
    supervisor: ContactConfig = Field(default_factory=ContactConfig)
    safety: ContactConfig = Field(default_factory=ContactConfig)
    owner: ContactConfig = Field(default_factory=ContactConfig)


class IdleConfig(BaseModel):
    """Idle management configuration."""
    enabled: bool = True
    threshold_days: int = Field(7, ge=1, le=365, description="Days without activity before idling")
    nightly_check_time: str = Field('00:00', pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    activity_types: list[str] = Field(
        default_factory=lambda: ['fuel_log', 'pre_op', 'operator_message'],
        description="Activity types that reset idle timer"
    )


class TrackedAsset(BaseModel):
    """Light vehicle tracked by FC (no dedicated agent)."""
    asset_id: str = Field(..., min_length=1, pattern=r'^[A-Z0-9-]+$',
                          description="Unique asset identifier")
    type: TrackedAssetType = Field(..., description="Asset type")
    make: str = 'Unknown'
    model: str = 'Unknown'
    year: Optional[int] = Field(None, ge=1900, le=2100)

    # Compliance tracking
    registration_due: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    insurance_due: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    pm_interval_months: int = Field(6, ge=1, le=24)
    last_pm: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')


class FleetInfo(BaseModel):
    """Basic fleet information."""
    name: str = 'Unnamed Fleet'
    site: str = 'Unknown Site'
    timezone: str = 'UTC'


class FleetConfig(BaseModel):
    """Root configuration model for fleet.yaml."""
    fleet: FleetInfo = Field(default_factory=FleetInfo)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    coordinator: CoordinatorConfig
    assets: list[AssetConfig] = Field(default_factory=list)
    hosts: list[HostConfig] = Field(..., min_length=1)
    escalation: EscalationConfig = Field(default_factory=EscalationConfig)
    idle_management: IdleConfig = Field(default_factory=IdleConfig)
    tracked_assets: list[TrackedAsset] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_references(self) -> 'FleetConfig':
        """Validate cross-references between config sections."""
        errors = []

        # Collect all host names
        host_names = {h.name for h in self.hosts}

        # Collect all asset IDs
        asset_ids = {a.asset_id for a in self.assets}

        # Check for duplicate asset IDs
        if len(asset_ids) != len(self.assets):
            seen = set()
            for asset in self.assets:
                if asset.asset_id in seen:
                    errors.append(f"Duplicate asset_id: {asset.asset_id}")
                seen.add(asset.asset_id)

        # Check that each asset's host exists
        for asset in self.assets:
            if asset.host not in host_names:
                errors.append(
                    f"Asset {asset.asset_id} references unknown host: {asset.host}"
                )

        # Check that coordinator host exists
        if self.coordinator.host not in host_names:
            errors.append(
                f"Coordinator references unknown host: {self.coordinator.host}"
            )

        # Check that hosts list valid assets
        for host in self.hosts:
            for asset_id in host.assets:
                if asset_id != 'FLEET-COORD' and asset_id not in asset_ids:
                    errors.append(
                        f"Host {host.name} lists unknown asset: {asset_id}"
                    )

        # Check that exactly one host has Redis
        redis_hosts = [h.name for h in self.hosts if h.redis]
        if len(redis_hosts) == 0:
            errors.append("No host is configured to run Redis (redis: true)")
        elif len(redis_hosts) > 1:
            errors.append(f"Multiple hosts configured for Redis: {redis_hosts}")

        if errors:
            raise ValueError('\n'.join(errors))

        return self


def validate_fleet_config(config: dict) -> FleetConfig:
    """Validate a fleet configuration dictionary.

    Args:
        config: Raw configuration dictionary from YAML

    Returns:
        Validated FleetConfig model

    Raises:
        pydantic.ValidationError: If validation fails
    """
    return FleetConfig.model_validate(config)
