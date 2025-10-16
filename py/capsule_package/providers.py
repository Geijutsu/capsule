#!/usr/bin/env python3
"""Hardware provider management for OpenMesh xNode deployment

Supports multiple cloud and bare metal providers:
- Hivelocity (bare metal servers)
- DigitalOcean (cloud droplets)
- Vultr (cloud compute)
- AWS EC2 (cloud instances)
- Equinix Metal (bare metal)
- Linode (cloud and dedicated CPU)
- Scaleway (cloud, ARM, GPU, Apple Silicon)
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any
import yaml

# Import API clients
try:
    from .api_clients import (
        HivelocityAPIClient,
        DigitalOceanAPIClient,
        VultrAPIClient,
        EquinixMetalAPIClient,
        APIError,
        AuthenticationError
    )
except ImportError:
    # Fallback for when running as script
    from api_clients import (
        HivelocityAPIClient,
        DigitalOceanAPIClient,
        VultrAPIClient,
        EquinixMetalAPIClient,
        APIError,
        AuthenticationError
    )

# Optional boto3 import for AWS
try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    logger.warning("boto3 not installed. AWS provider will have limited functionality.")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProviderTemplate:
    """Template/instance type offered by a provider"""
    id: str
    name: str
    provider: str
    cpu: int
    memory_gb: int
    storage_gb: int
    bandwidth_tb: float
    price_hourly: float
    price_monthly: float
    gpu: Optional[str] = None
    regions: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)

    @property
    def price_annual(self) -> float:
        """Annual pricing estimate"""
        return self.price_monthly * 12

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'provider': self.provider,
            'cpu': self.cpu,
            'memory_gb': self.memory_gb,
            'storage_gb': self.storage_gb,
            'bandwidth_tb': self.bandwidth_tb,
            'price_hourly': self.price_hourly,
            'price_monthly': self.price_monthly,
            'gpu': self.gpu,
            'regions': self.regions,
            'features': self.features,
        }


class Provider(ABC):
    """Base class for hardware providers"""

    def __init__(self, name: str, api_key: Optional[str] = None):
        self.name = name
        self.api_key = api_key or os.environ.get(f"{name.upper()}_API_KEY")
        self.templates: List[ProviderTemplate] = []
        self.regions: List[str] = []
        self._initialize_templates()
        self._initialize_regions()

    @abstractmethod
    def _initialize_templates(self):
        """Initialize available templates for this provider"""
        pass

    @abstractmethod
    def _initialize_regions(self):
        """Initialize available regions for this provider"""
        pass

    @abstractmethod
    def deploy(self, template_id: str, config: dict) -> dict:
        """Deploy an xNode instance

        Args:
            template_id: Template identifier
            config: Deployment configuration (name, region, etc.)

        Returns:
            dict: Deployed instance information
        """
        pass

    @abstractmethod
    def list_instances(self) -> List[dict]:
        """List all instances for this provider

        Returns:
            List of instance dictionaries
        """
        pass

    @abstractmethod
    def get_instance(self, instance_id: str) -> dict:
        """Get details for a specific instance

        Args:
            instance_id: Instance identifier

        Returns:
            Instance information dictionary
        """
        pass

    @abstractmethod
    def delete_instance(self, instance_id: str) -> bool:
        """Delete an instance

        Args:
            instance_id: Instance identifier

        Returns:
            True if deletion was successful
        """
        pass

    @abstractmethod
    def start_instance(self, instance_id: str) -> bool:
        """Start a stopped instance

        Args:
            instance_id: Instance identifier

        Returns:
            True if start was successful
        """
        pass

    @abstractmethod
    def stop_instance(self, instance_id: str) -> bool:
        """Stop a running instance

        Args:
            instance_id: Instance identifier

        Returns:
            True if stop was successful
        """
        pass

    def get_template(self, template_id: str) -> Optional[ProviderTemplate]:
        """Get template by ID"""
        for template in self.templates:
            if template.id == template_id:
                return template
        return None

    def get_pricing(self, template_id: str) -> Optional[dict]:
        """Get pricing information for a template"""
        template = self.get_template(template_id)
        if not template:
            return None

        return {
            'hourly': template.price_hourly,
            'daily': template.price_hourly * 24,
            'monthly': template.price_monthly,
            'annual': template.price_annual,
        }

    def validate_credentials(self) -> bool:
        """Validate API credentials"""
        if not self.api_key:
            logger.warning(f"No API key configured for {self.name}")
            return False

        # TODO: Make actual API call to validate
        logger.info(f"Credentials validated for {self.name}")
        return True


class HivelocityProvider(Provider):
    """Hivelocity bare metal provider"""

    def __init__(self, name: str, api_key: Optional[str] = None):
        self.api_client = None
        super().__init__(name, api_key)
        if self.api_key:
            try:
                self.api_client = HivelocityAPIClient(self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Hivelocity API client: {e}")

    def _initialize_templates(self):
        """Initialize Hivelocity bare metal templates"""
        self.templates = [
            ProviderTemplate(
                id="hive-small",
                name="Small Bare Metal",
                provider="hivelocity",
                cpu=4,
                memory_gb=16,
                storage_gb=500,
                bandwidth_tb=10,
                price_hourly=0.12,
                price_monthly=85.00,
                regions=["atlanta", "tampa", "los-angeles"],
                features=["dedicated", "bare-metal", "ipmi"]
            ),
            ProviderTemplate(
                id="hive-medium",
                name="Medium Bare Metal",
                provider="hivelocity",
                cpu=8,
                memory_gb=32,
                storage_gb=1000,
                bandwidth_tb=20,
                price_hourly=0.25,
                price_monthly=180.00,
                regions=["atlanta", "tampa", "los-angeles", "new-york"],
                features=["dedicated", "bare-metal", "ipmi", "raid"]
            ),
            ProviderTemplate(
                id="hive-large",
                name="Large Bare Metal",
                provider="hivelocity",
                cpu=16,
                memory_gb=64,
                storage_gb=2000,
                bandwidth_tb=30,
                price_hourly=0.50,
                price_monthly=360.00,
                regions=["atlanta", "tampa", "los-angeles", "new-york"],
                features=["dedicated", "bare-metal", "ipmi", "raid", "redundant-power"]
            ),
            ProviderTemplate(
                id="hive-gpu",
                name="GPU Bare Metal",
                provider="hivelocity",
                cpu=12,
                memory_gb=96,
                storage_gb=1500,
                bandwidth_tb=20,
                price_hourly=0.80,
                price_monthly=575.00,
                gpu="NVIDIA RTX 4090",
                regions=["atlanta", "los-angeles"],
                features=["dedicated", "bare-metal", "gpu", "ipmi"]
            ),
        ]

    def _initialize_regions(self):
        """Initialize Hivelocity datacenter regions"""
        self.regions = ["atlanta", "tampa", "los-angeles", "new-york", "miami"]

    def deploy(self, template_id: str, config: dict) -> dict:
        """Deploy Hivelocity bare metal server"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if not self.api_client:
            raise RuntimeError("Hivelocity API client not initialized. Check API key.")

        try:
            logger.info(f"Deploying Hivelocity {template_id} in {config.get('region')}")

            # Map template to Hivelocity product code
            product_map = {
                'hive-small': 'BM-2020-1',
                'hive-medium': 'BM-2020-2',
                'hive-large': 'BM-2020-3',
                'hive-gpu': 'BM-GPU-1',
            }

            payload = {
                'product_id': product_map.get(template_id, 'BM-2020-1'),
                'location_id': config.get('region', 'atlanta'),
                'hostname': config.get('name', 'xnode'),
                'os_name': config.get('os', 'ubuntu-20.04'),
                'period': 'monthly',
            }

            response = self.api_client.post('/device/order', data=payload)

            return {
                'id': response.get('deviceId', f"hive-{config.get('name', 'instance')}"),
                'name': config.get('name', 'unnamed'),
                'provider': 'hivelocity',
                'template': template_id,
                'region': config.get('region', 'atlanta'),
                'status': response.get('status', 'deploying'),
                'ip_address': response.get('primaryIp', ''),
                'cost_hourly': template.price_hourly,
                'metadata': response
            }

        except APIError as e:
            logger.error(f"Hivelocity API error during deployment: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to deploy Hivelocity instance: {e}")
            raise

    def list_instances(self) -> List[dict]:
        """List Hivelocity instances"""
        if not self.api_client:
            logger.warning("Hivelocity API client not initialized")
            return []

        try:
            response = self.api_client.get('/device')
            devices = response.get('devices', [])

            instances = []
            for device in devices:
                instances.append({
                    'id': device.get('deviceId'),
                    'name': device.get('hostname'),
                    'provider': 'hivelocity',
                    'status': device.get('status'),
                    'ip_address': device.get('primaryIp'),
                    'region': device.get('location'),
                    'created_at': device.get('createdAt'),
                })

            return instances

        except APIError as e:
            logger.error(f"Hivelocity API error listing instances: {e}")
            return []

    def get_instance(self, instance_id: str) -> dict:
        """Get Hivelocity instance details"""
        if not self.api_client:
            raise RuntimeError("Hivelocity API client not initialized")

        try:
            response = self.api_client.get(f'/device/{instance_id}')
            device = response.get('device', {})

            return {
                'id': device.get('deviceId'),
                'name': device.get('hostname'),
                'provider': 'hivelocity',
                'status': device.get('status'),
                'ip_address': device.get('primaryIp'),
                'region': device.get('location'),
                'created_at': device.get('createdAt'),
                'metadata': device
            }

        except APIError as e:
            logger.error(f"Failed to get Hivelocity instance {instance_id}: {e}")
            raise

    def delete_instance(self, instance_id: str) -> bool:
        """Delete Hivelocity instance"""
        if not self.api_client:
            raise RuntimeError("Hivelocity API client not initialized")

        try:
            logger.info(f"Deleting Hivelocity instance {instance_id}")
            self.api_client.delete(f'/device/{instance_id}')
            return True

        except APIError as e:
            logger.error(f"Failed to delete Hivelocity instance {instance_id}: {e}")
            return False

    def start_instance(self, instance_id: str) -> bool:
        """Start Hivelocity instance"""
        if not self.api_client:
            raise RuntimeError("Hivelocity API client not initialized")

        try:
            logger.info(f"Starting Hivelocity instance {instance_id}")
            self.api_client.post(f'/device/{instance_id}/power', data={'action': 'on'})
            return True

        except APIError as e:
            logger.error(f"Failed to start Hivelocity instance {instance_id}: {e}")
            return False

    def stop_instance(self, instance_id: str) -> bool:
        """Stop Hivelocity instance"""
        if not self.api_client:
            raise RuntimeError("Hivelocity API client not initialized")

        try:
            logger.info(f"Stopping Hivelocity instance {instance_id}")
            self.api_client.post(f'/device/{instance_id}/power', data={'action': 'off'})
            return True

        except APIError as e:
            logger.error(f"Failed to stop Hivelocity instance {instance_id}: {e}")
            return False


class DigitalOceanProvider(Provider):
    """DigitalOcean cloud provider"""

    def __init__(self, name: str, api_key: Optional[str] = None):
        self.api_client = None
        super().__init__(name, api_key)
        if self.api_key:
            try:
                self.api_client = DigitalOceanAPIClient(self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize DigitalOcean API client: {e}")

    def _initialize_templates(self):
        """Initialize DigitalOcean droplet sizes"""
        self.templates = [
            ProviderTemplate(
                id="do-basic-1",
                name="Basic (1 vCPU)",
                provider="digitalocean",
                cpu=1,
                memory_gb=1,
                storage_gb=25,
                bandwidth_tb=1,
                price_hourly=0.007,
                price_monthly=5.00,
                regions=["nyc1", "nyc3", "sfo3", "lon1", "fra1"],
                features=["ssd", "cloud"]
            ),
            ProviderTemplate(
                id="do-basic-2",
                name="Basic (2 vCPU)",
                provider="digitalocean",
                cpu=2,
                memory_gb=2,
                storage_gb=50,
                bandwidth_tb=2,
                price_hourly=0.015,
                price_monthly=12.00,
                regions=["nyc1", "nyc3", "sfo3", "lon1", "fra1", "sgp1"],
                features=["ssd", "cloud"]
            ),
            ProviderTemplate(
                id="do-standard-4",
                name="Standard (4 vCPU)",
                provider="digitalocean",
                cpu=4,
                memory_gb=8,
                storage_gb=160,
                bandwidth_tb=5,
                price_hourly=0.071,
                price_monthly=48.00,
                regions=["nyc1", "nyc3", "sfo3", "lon1", "fra1", "sgp1", "tor1"],
                features=["ssd", "cloud", "monitoring"]
            ),
            ProviderTemplate(
                id="do-cpu-8",
                name="CPU Optimized (8 vCPU)",
                provider="digitalocean",
                cpu=8,
                memory_gb=16,
                storage_gb=200,
                bandwidth_tb=6,
                price_hourly=0.238,
                price_monthly=160.00,
                regions=["nyc1", "sfo3", "lon1", "fra1"],
                features=["ssd", "cloud", "cpu-optimized"]
            ),
        ]

    def _initialize_regions(self):
        """Initialize DigitalOcean regions"""
        self.regions = ["nyc1", "nyc3", "sfo3", "lon1", "fra1", "sgp1", "tor1", "ams3"]

    def deploy(self, template_id: str, config: dict) -> dict:
        """Deploy DigitalOcean droplet"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if not self.api_client:
            raise RuntimeError("DigitalOcean API client not initialized. Check API key.")

        try:
            logger.info(f"Deploying DigitalOcean droplet {template_id}")

            # Map template to DigitalOcean size slug
            size_map = {
                'do-basic-1': 's-1vcpu-1gb',
                'do-basic-2': 's-2vcpu-2gb',
                'do-standard-4': 's-4vcpu-8gb',
                'do-cpu-8': 'c-8',
            }

            payload = {
                'name': config.get('name', 'xnode'),
                'region': config.get('region', 'nyc1'),
                'size': size_map.get(template_id, 's-1vcpu-1gb'),
                'image': config.get('image', 'ubuntu-20-04-x64'),
                'ssh_keys': config.get('ssh_keys', []),
                'backups': config.get('backups', False),
                'ipv6': config.get('ipv6', True),
                'monitoring': config.get('monitoring', True),
                'tags': ['xnode', 'openmesh'],
            }

            response = self.api_client.post('/droplets', data=payload)
            droplet = response.get('droplet', {})

            return {
                'id': str(droplet.get('id')),
                'name': droplet.get('name'),
                'provider': 'digitalocean',
                'template': template_id,
                'region': droplet.get('region', {}).get('slug'),
                'status': droplet.get('status', 'new'),
                'ip_address': '',  # IP assigned after creation
                'cost_hourly': template.price_hourly,
                'metadata': droplet
            }

        except APIError as e:
            logger.error(f"DigitalOcean API error during deployment: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to deploy DigitalOcean droplet: {e}")
            raise

    def list_instances(self) -> List[dict]:
        """List DigitalOcean droplets"""
        if not self.api_client:
            logger.warning("DigitalOcean API client not initialized")
            return []

        try:
            response = self.api_client.get('/droplets')
            droplets = response.get('droplets', [])

            instances = []
            for droplet in droplets:
                # Get public IPv4 address
                ip_address = ''
                for network in droplet.get('networks', {}).get('v4', []):
                    if network.get('type') == 'public':
                        ip_address = network.get('ip_address')
                        break

                instances.append({
                    'id': str(droplet.get('id')),
                    'name': droplet.get('name'),
                    'provider': 'digitalocean',
                    'status': droplet.get('status'),
                    'ip_address': ip_address,
                    'region': droplet.get('region', {}).get('slug'),
                    'created_at': droplet.get('created_at'),
                })

            return instances

        except APIError as e:
            logger.error(f"DigitalOcean API error listing instances: {e}")
            return []

    def get_instance(self, instance_id: str) -> dict:
        """Get DigitalOcean droplet details"""
        if not self.api_client:
            raise RuntimeError("DigitalOcean API client not initialized")

        try:
            response = self.api_client.get(f'/droplets/{instance_id}')
            droplet = response.get('droplet', {})

            # Get public IPv4 address
            ip_address = ''
            for network in droplet.get('networks', {}).get('v4', []):
                if network.get('type') == 'public':
                    ip_address = network.get('ip_address')
                    break

            return {
                'id': str(droplet.get('id')),
                'name': droplet.get('name'),
                'provider': 'digitalocean',
                'status': droplet.get('status'),
                'ip_address': ip_address,
                'region': droplet.get('region', {}).get('slug'),
                'created_at': droplet.get('created_at'),
                'metadata': droplet
            }

        except APIError as e:
            logger.error(f"Failed to get DigitalOcean droplet {instance_id}: {e}")
            raise

    def delete_instance(self, instance_id: str) -> bool:
        """Delete DigitalOcean droplet"""
        if not self.api_client:
            raise RuntimeError("DigitalOcean API client not initialized")

        try:
            logger.info(f"Deleting DigitalOcean droplet {instance_id}")
            self.api_client.delete(f'/droplets/{instance_id}')
            return True

        except APIError as e:
            logger.error(f"Failed to delete DigitalOcean droplet {instance_id}: {e}")
            return False

    def start_instance(self, instance_id: str) -> bool:
        """Start DigitalOcean droplet"""
        if not self.api_client:
            raise RuntimeError("DigitalOcean API client not initialized")

        try:
            logger.info(f"Starting DigitalOcean droplet {instance_id}")
            self.api_client.post(f'/droplets/{instance_id}/actions', data={'type': 'power_on'})
            return True

        except APIError as e:
            logger.error(f"Failed to start DigitalOcean droplet {instance_id}: {e}")
            return False

    def stop_instance(self, instance_id: str) -> bool:
        """Stop DigitalOcean droplet"""
        if not self.api_client:
            raise RuntimeError("DigitalOcean API client not initialized")

        try:
            logger.info(f"Stopping DigitalOcean droplet {instance_id}")
            self.api_client.post(f'/droplets/{instance_id}/actions', data={'type': 'power_off'})
            return True

        except APIError as e:
            logger.error(f"Failed to stop DigitalOcean droplet {instance_id}: {e}")
            return False


class VultrProvider(Provider):
    """Vultr cloud provider"""

    def __init__(self, name: str, api_key: Optional[str] = None):
        self.api_client = None
        super().__init__(name, api_key)
        if self.api_key:
            try:
                self.api_client = VultrAPIClient(self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Vultr API client: {e}")

    def _initialize_templates(self):
        """Initialize Vultr compute instances"""
        self.templates = [
            ProviderTemplate(
                id="vultr-vc2-1",
                name="VC2 1 vCPU",
                provider="vultr",
                cpu=1,
                memory_gb=1,
                storage_gb=25,
                bandwidth_tb=1,
                price_hourly=0.004,
                price_monthly=2.50,
                regions=["ewr", "ord", "dfw", "sea", "lax"],
                features=["ssd", "cloud"]
            ),
            ProviderTemplate(
                id="vultr-vc2-2",
                name="VC2 2 vCPU",
                provider="vultr",
                cpu=2,
                memory_gb=4,
                storage_gb=80,
                bandwidth_tb=3,
                price_hourly=0.018,
                price_monthly=12.00,
                regions=["ewr", "ord", "dfw", "sea", "lax", "ams"],
                features=["ssd", "cloud"]
            ),
            ProviderTemplate(
                id="vultr-hf-4",
                name="High Frequency 4 vCPU",
                provider="vultr",
                cpu=4,
                memory_gb=8,
                storage_gb=128,
                bandwidth_tb=4,
                price_hourly=0.060,
                price_monthly=42.00,
                regions=["ewr", "ord", "lax", "ams", "sgp"],
                features=["nvme", "cloud", "high-performance"]
            ),
            ProviderTemplate(
                id="vultr-bare-4",
                name="Bare Metal 4 Core",
                provider="vultr",
                cpu=4,
                memory_gb=32,
                storage_gb=240,
                bandwidth_tb=5,
                price_hourly=0.34,
                price_monthly=240.00,
                regions=["ewr", "dfw"],
                features=["bare-metal", "nvme", "dedicated"]
            ),
        ]

    def _initialize_regions(self):
        """Initialize Vultr regions"""
        self.regions = ["ewr", "ord", "dfw", "sea", "lax", "ams", "fra", "sgp", "syd"]

    def deploy(self, template_id: str, config: dict) -> dict:
        """Deploy Vultr instance"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if not self.api_client:
            raise RuntimeError("Vultr API client not initialized. Check API key.")

        try:
            logger.info(f"Deploying Vultr instance {template_id}")

            # Map template to Vultr plan ID
            plan_map = {
                'vultr-vc2-1': 'vc2-1c-1gb',
                'vultr-vc2-2': 'vc2-2c-4gb',
                'vultr-hf-4': 'vhf-4c-8gb',
                'vultr-bare-4': 'vbm-4c-32gb',
            }

            payload = {
                'region': config.get('region', 'ewr'),
                'plan': plan_map.get(template_id, 'vc2-1c-1gb'),
                'label': config.get('name', 'xnode'),
                'os_id': config.get('os_id', 387),  # Ubuntu 20.04 x64
                'hostname': config.get('name', 'xnode'),
                'enable_ipv6': config.get('ipv6', True),
                'backups': 'disabled',
                'ddos_protection': config.get('ddos_protection', False),
                'tag': 'xnode',
            }

            response = self.api_client.post('/instances', data=payload)
            instance = response.get('instance', {})

            return {
                'id': instance.get('id'),
                'name': instance.get('label'),
                'provider': 'vultr',
                'template': template_id,
                'region': instance.get('region'),
                'status': instance.get('status', 'pending'),
                'ip_address': instance.get('main_ip', ''),
                'cost_hourly': template.price_hourly,
                'metadata': instance
            }

        except APIError as e:
            logger.error(f"Vultr API error during deployment: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to deploy Vultr instance: {e}")
            raise

    def list_instances(self) -> List[dict]:
        """List Vultr instances"""
        if not self.api_client:
            logger.warning("Vultr API client not initialized")
            return []

        try:
            response = self.api_client.get('/instances')
            instances_data = response.get('instances', [])

            instances = []
            for instance in instances_data:
                instances.append({
                    'id': instance.get('id'),
                    'name': instance.get('label'),
                    'provider': 'vultr',
                    'status': instance.get('status'),
                    'ip_address': instance.get('main_ip'),
                    'region': instance.get('region'),
                    'created_at': instance.get('date_created'),
                })

            return instances

        except APIError as e:
            logger.error(f"Vultr API error listing instances: {e}")
            return []

    def get_instance(self, instance_id: str) -> dict:
        """Get Vultr instance details"""
        if not self.api_client:
            raise RuntimeError("Vultr API client not initialized")

        try:
            response = self.api_client.get(f'/instances/{instance_id}')
            instance = response.get('instance', {})

            return {
                'id': instance.get('id'),
                'name': instance.get('label'),
                'provider': 'vultr',
                'status': instance.get('status'),
                'ip_address': instance.get('main_ip'),
                'region': instance.get('region'),
                'created_at': instance.get('date_created'),
                'metadata': instance
            }

        except APIError as e:
            logger.error(f"Failed to get Vultr instance {instance_id}: {e}")
            raise

    def delete_instance(self, instance_id: str) -> bool:
        """Delete Vultr instance"""
        if not self.api_client:
            raise RuntimeError("Vultr API client not initialized")

        try:
            logger.info(f"Deleting Vultr instance {instance_id}")
            self.api_client.delete(f'/instances/{instance_id}')
            return True

        except APIError as e:
            logger.error(f"Failed to delete Vultr instance {instance_id}: {e}")
            return False

    def start_instance(self, instance_id: str) -> bool:
        """Start Vultr instance"""
        if not self.api_client:
            raise RuntimeError("Vultr API client not initialized")

        try:
            logger.info(f"Starting Vultr instance {instance_id}")
            self.api_client.post(f'/instances/{instance_id}/start')
            return True

        except APIError as e:
            logger.error(f"Failed to start Vultr instance {instance_id}: {e}")
            return False

    def stop_instance(self, instance_id: str) -> bool:
        """Stop Vultr instance"""
        if not self.api_client:
            raise RuntimeError("Vultr API client not initialized")

        try:
            logger.info(f"Stopping Vultr instance {instance_id}")
            self.api_client.post(f'/instances/{instance_id}/halt')
            return True

        except APIError as e:
            logger.error(f"Failed to stop Vultr instance {instance_id}: {e}")
            return False


class AWSProvider(Provider):
    """AWS EC2 provider"""

    def __init__(self, name: str, api_key: Optional[str] = None):
        self.ec2_client = None
        self.ec2_resource = None
        super().__init__(name, api_key)
        if HAS_BOTO3:
            try:
                # AWS uses AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env vars
                # or ~/.aws/credentials file by default
                self.ec2_client = boto3.client('ec2')
                self.ec2_resource = boto3.resource('ec2')
            except Exception as e:
                logger.error(f"Failed to initialize AWS EC2 client: {e}")
        else:
            logger.warning("boto3 not installed. Install with: pip install boto3")

    def _initialize_templates(self):
        """Initialize AWS EC2 instance types"""
        self.templates = [
            ProviderTemplate(
                id="aws-t3-micro",
                name="t3.micro",
                provider="aws",
                cpu=2,
                memory_gb=1,
                storage_gb=30,
                bandwidth_tb=0.1,
                price_hourly=0.0104,
                price_monthly=7.50,
                regions=["us-east-1", "us-west-2", "eu-west-1"],
                features=["burstable", "cloud"]
            ),
            ProviderTemplate(
                id="aws-t3-medium",
                name="t3.medium",
                provider="aws",
                cpu=2,
                memory_gb=4,
                storage_gb=50,
                bandwidth_tb=0.5,
                price_hourly=0.0416,
                price_monthly=30.00,
                regions=["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
                features=["burstable", "cloud"]
            ),
            ProviderTemplate(
                id="aws-m5-large",
                name="m5.large",
                provider="aws",
                cpu=2,
                memory_gb=8,
                storage_gb=100,
                bandwidth_tb=1,
                price_hourly=0.096,
                price_monthly=70.00,
                regions=["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
                features=["cloud", "general-purpose"]
            ),
            ProviderTemplate(
                id="aws-c5-2xlarge",
                name="c5.2xlarge",
                provider="aws",
                cpu=8,
                memory_gb=16,
                storage_gb=200,
                bandwidth_tb=2,
                price_hourly=0.34,
                price_monthly=248.00,
                regions=["us-east-1", "us-west-2", "eu-west-1"],
                features=["cloud", "compute-optimized"]
            ),
        ]

    def _initialize_regions(self):
        """Initialize AWS regions"""
        self.regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "ap-northeast-1"]

    def deploy(self, template_id: str, config: dict) -> dict:
        """Deploy AWS EC2 instance"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if not self.ec2_client:
            raise RuntimeError("AWS EC2 client not initialized. Check boto3 installation and AWS credentials.")

        try:
            logger.info(f"Deploying AWS EC2 {template_id}")

            # Map template to AWS instance type
            instance_type_map = {
                'aws-t3-micro': 't3.micro',
                'aws-t3-medium': 't3.medium',
                'aws-m5-large': 'm5.large',
                'aws-c5-2xlarge': 'c5.2xlarge',
            }

            # Get AMI ID for Ubuntu 20.04 in region (example)
            ami_id = config.get('ami_id', 'ami-0c55b159cbfafe1f0')  # Ubuntu 20.04 in us-east-1

            launch_params = {
                'ImageId': ami_id,
                'InstanceType': instance_type_map.get(template_id, 't3.micro'),
                'MinCount': 1,
                'MaxCount': 1,
                'TagSpecifications': [
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': config.get('name', 'xnode')},
                            {'Key': 'Project', 'Value': 'openmesh'},
                            {'Key': 'Type', 'Value': 'xnode'},
                        ]
                    }
                ],
            }

            # Add security group if provided
            if 'security_group_ids' in config:
                launch_params['SecurityGroupIds'] = config['security_group_ids']

            # Add key pair if provided
            if 'key_name' in config:
                launch_params['KeyName'] = config['key_name']

            # Add subnet if provided
            if 'subnet_id' in config:
                launch_params['SubnetId'] = config['subnet_id']

            response = self.ec2_client.run_instances(**launch_params)
            instance = response['Instances'][0]

            return {
                'id': instance['InstanceId'],
                'name': config.get('name', 'unnamed'),
                'provider': 'aws',
                'template': template_id,
                'region': config.get('region', 'us-east-1'),
                'status': instance['State']['Name'],
                'ip_address': instance.get('PublicIpAddress', ''),
                'cost_hourly': template.price_hourly,
                'metadata': instance
            }

        except ClientError as e:
            logger.error(f"AWS EC2 API error during deployment: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to deploy AWS EC2 instance: {e}")
            raise

    def list_instances(self) -> List[dict]:
        """List AWS EC2 instances"""
        if not self.ec2_client:
            logger.warning("AWS EC2 client not initialized")
            return []
    def get_instance(self, instance_id: str) -> dict:
        """Get details for a specific AWS instance"""
        # TODO: Actual API call
        logger.info(f"Getting AWS instance {instance_id}")
        return {
            'id': instance_id,
            'status': 'running',
            'provider': 'aws',
        }

    def delete_instance(self, instance_id: str) -> bool:
        """Delete a AWS instance"""
        # TODO: Actual API call
        logger.info(f"Deleting AWS instance {instance_id}")
        return True

    def start_instance(self, instance_id: str) -> bool:
        """Start a stopped AWS instance"""
        # TODO: Actual API call
        logger.info(f"Starting AWS instance {instance_id}")
        return True

    def stop_instance(self, instance_id: str) -> bool:
        """Stop a running AWS instance"""
        # TODO: Actual API call
        logger.info(f"Stopping AWS instance {instance_id}")
        return True


        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {'Name': 'tag:Project', 'Values': ['openmesh']},
                    {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopping', 'stopped']}
                ]
            )

            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    # Get instance name from tags
                    name = ''
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                            break

                    instances.append({
                        'id': instance['InstanceId'],
                        'name': name,
                        'provider': 'aws',
                        'status': instance['State']['Name'],
                        'ip_address': instance.get('PublicIpAddress', ''),
                        'region': instance['Placement']['AvailabilityZone'],
                        'created_at': instance['LaunchTime'].isoformat(),
                    })

            return instances

        except ClientError as e:
            logger.error(f"AWS EC2 API error listing instances: {e}")
            return []

    def get_instance(self, instance_id: str) -> dict:
        """Get AWS EC2 instance details"""
        if not self.ec2_client:
            raise RuntimeError("AWS EC2 client not initialized")

        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]

            # Get instance name from tags
            name = ''
            for tag in instance.get('Tags', []):
                if tag['Key'] == 'Name':
                    name = tag['Value']
                    break

            return {
                'id': instance['InstanceId'],
                'name': name,
                'provider': 'aws',
                'status': instance['State']['Name'],
                'ip_address': instance.get('PublicIpAddress', ''),
                'region': instance['Placement']['AvailabilityZone'],
                'created_at': instance['LaunchTime'].isoformat(),
                'metadata': instance
            }

        except ClientError as e:
            logger.error(f"Failed to get AWS EC2 instance {instance_id}: {e}")
            raise

    def delete_instance(self, instance_id: str) -> bool:
        """Delete AWS EC2 instance (terminate)"""
        if not self.ec2_client:
            raise RuntimeError("AWS EC2 client not initialized")

        try:
            logger.info(f"Terminating AWS EC2 instance {instance_id}")
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            return True

        except ClientError as e:
            logger.error(f"Failed to terminate AWS EC2 instance {instance_id}: {e}")
            return False

    def start_instance(self, instance_id: str) -> bool:
        """Start AWS EC2 instance"""
        if not self.ec2_client:
            raise RuntimeError("AWS EC2 client not initialized")

        try:
            logger.info(f"Starting AWS EC2 instance {instance_id}")
            self.ec2_client.start_instances(InstanceIds=[instance_id])
            return True

        except ClientError as e:
            logger.error(f"Failed to start AWS EC2 instance {instance_id}: {e}")
            return False

    def stop_instance(self, instance_id: str) -> bool:
        """Stop AWS EC2 instance"""
        if not self.ec2_client:
            raise RuntimeError("AWS EC2 client not initialized")

        try:
            logger.info(f"Stopping AWS EC2 instance {instance_id}")
            self.ec2_client.stop_instances(InstanceIds=[instance_id])
            return True

        except ClientError as e:
            logger.error(f"Failed to stop AWS EC2 instance {instance_id}: {e}")
            return False


class EquinixMetalProvider(Provider):
    """Equinix Metal (formerly Packet) bare metal provider"""

    def _initialize_templates(self):
        """Initialize Equinix Metal bare metal configurations"""
        self.templates = [
            ProviderTemplate(
                id="equinix-c3-small",
                name="c3.small.x86",
                provider="equinix",
                cpu=8,
                memory_gb=32,
                storage_gb=240,
                bandwidth_tb=20,
                price_hourly=0.50,
                price_monthly=350.00,
                regions=["da", "sv", "ny", "am"],
                features=["bare-metal", "nvme"]
            ),
            ProviderTemplate(
                id="equinix-c3-medium",
                name="c3.medium.x86",
                provider="equinix",
                cpu=24,
                memory_gb=64,
                storage_gb=960,
                bandwidth_tb=20,
                price_hourly=1.00,
                price_monthly=700.00,
                regions=["da", "sv", "ny", "am", "sg"],
                features=["bare-metal", "nvme", "high-memory"]
            ),
            ProviderTemplate(
                id="equinix-g2-large",
                name="g2.large.x86 (GPU)",
                provider="equinix",
                cpu=24,
                memory_gb=128,
                storage_gb=1920,
                bandwidth_tb=20,
                price_hourly=3.00,
                price_monthly=2100.00,
                gpu="NVIDIA Tesla V100",
                regions=["da", "sv", "ny"],
                features=["bare-metal", "gpu", "nvme"]
            ),
        ]

    def _initialize_regions(self):
        """Initialize Equinix Metal regions"""
        self.regions = ["da", "sv", "ny", "am", "sg", "ty", "fr"]

    def deploy(self, template_id: str, config: dict) -> dict:
        """Deploy Equinix Metal bare metal"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        logger.info(f"Deploying Equinix Metal {template_id}")

        return {
            'id': f"equinix-{config.get('name', 'instance')}",
            'name': config.get('name', 'unnamed'),
            'provider': 'equinix',
            'template': template_id,
            'region': config.get('region', 'da'),
            'status': 'deploying',
            'ip_address': '147.75.0.100',
            'cost_hourly': template.price_hourly,
        }

    def list_instances(self) -> List[dict]:
        """List Equinix Metal instances"""
        return []
    def get_instance(self, instance_id: str) -> dict:
        """Get details for a specific Equinix instance"""
        # TODO: Actual API call
        logger.info(f"Getting Equinix instance {instance_id}")
        return {
            'id': instance_id,
            'status': 'running',
            'provider': 'equinix',
        }

    def delete_instance(self, instance_id: str) -> bool:
        """Delete a Equinix instance"""
        # TODO: Actual API call
        logger.info(f"Deleting Equinix instance {instance_id}")
        return True

    def start_instance(self, instance_id: str) -> bool:
        """Start a stopped Equinix instance"""
        # TODO: Actual API call
        logger.info(f"Starting Equinix instance {instance_id}")
        return True

    def stop_instance(self, instance_id: str) -> bool:
        """Stop a running Equinix instance"""
        # TODO: Actual API call
        logger.info(f"Stopping Equinix instance {instance_id}")
        return True



class LinodeProvider(Provider):
    """Linode cloud provider"""

    def _initialize_templates(self):
        """Initialize Linode instance types"""
        self.templates = [
            ProviderTemplate(
                id="linode-nanode-1gb",
                name="Nanode 1GB",
                provider="linode",
                cpu=1,
                memory_gb=1,
                storage_gb=25,
                bandwidth_tb=1,
                price_hourly=0.0075,
                price_monthly=5.00,
                regions=["us-east", "us-west", "eu-west", "eu-central", "ap-south"],
                features=["ssd", "cloud"]
            ),
            ProviderTemplate(
                id="linode-2gb",
                name="Linode 2GB",
                provider="linode",
                cpu=1,
                memory_gb=2,
                storage_gb=50,
                bandwidth_tb=2,
                price_hourly=0.015,
                price_monthly=10.00,
                regions=["us-east", "us-west", "us-central", "eu-west", "eu-central", "ap-south", "ap-northeast"],
                features=["ssd", "cloud"]
            ),
            ProviderTemplate(
                id="linode-4gb",
                name="Linode 4GB",
                provider="linode",
                cpu=2,
                memory_gb=4,
                storage_gb=80,
                bandwidth_tb=4,
                price_hourly=0.030,
                price_monthly=20.00,
                regions=["us-east", "us-west", "us-central", "eu-west", "eu-central", "ap-south", "ap-northeast", "ap-southeast"],
                features=["ssd", "cloud"]
            ),
            ProviderTemplate(
                id="linode-dedicated-4gb",
                name="Dedicated 4GB",
                provider="linode",
                cpu=2,
                memory_gb=4,
                storage_gb=80,
                bandwidth_tb=4,
                price_hourly=0.045,
                price_monthly=30.00,
                regions=["us-east", "us-west", "eu-west", "ap-south"],
                features=["ssd", "cloud", "dedicated-cpu"]
            ),
            ProviderTemplate(
                id="linode-dedicated-8gb",
                name="Dedicated 8GB",
                provider="linode",
                cpu=4,
                memory_gb=8,
                storage_gb=160,
                bandwidth_tb=5,
                price_hourly=0.090,
                price_monthly=60.00,
                regions=["us-east", "us-west", "us-central", "eu-west", "eu-central", "ap-south"],
                features=["ssd", "cloud", "dedicated-cpu", "high-memory"]
            ),
            ProviderTemplate(
                id="linode-gpu-rtx6000",
                name="GPU RTX6000",
                provider="linode",
                cpu=24,
                memory_gb=64,
                storage_gb=640,
                bandwidth_tb=10,
                price_hourly=1.50,
                price_monthly=1000.00,
                gpu="NVIDIA RTX 6000",
                regions=["us-east", "eu-west"],
                features=["ssd", "cloud", "gpu", "dedicated-cpu"]
            ),
        ]

    def _initialize_regions(self):
        """Initialize Linode datacenter regions"""
        self.regions = [
            "us-east", "us-west", "us-central", "us-southeast",
            "eu-west", "eu-central",
            "ap-south", "ap-northeast", "ap-southeast",
            "ca-central", "au-sydney"
        ]

    def deploy(self, template_id: str, config: dict) -> dict:
        """Deploy Linode instance"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        logger.info(f"Deploying Linode {template_id} in {config.get('region')}")

        return {
            'id': f"linode-{config.get('name', 'instance')}",
            'name': config.get('name', 'unnamed'),
            'provider': 'linode',
            'template': template_id,
            'region': config.get('region', 'us-east'),
            'status': 'deploying',
            'ip_address': '172.105.0.100',
            'cost_hourly': template.price_hourly,
        }

    def list_instances(self) -> List[dict]:
        """List Linode instances"""
        return []
    def get_instance(self, instance_id: str) -> dict:
        """Get details for a specific Linode instance"""
        # TODO: Actual API call
        logger.info(f"Getting Linode instance {instance_id}")
        return {
            'id': instance_id,
            'status': 'running',
            'provider': 'linode',
        }

    def delete_instance(self, instance_id: str) -> bool:
        """Delete a Linode instance"""
        # TODO: Actual API call
        logger.info(f"Deleting Linode instance {instance_id}")
        return True

    def start_instance(self, instance_id: str) -> bool:
        """Start a stopped Linode instance"""
        # TODO: Actual API call
        logger.info(f"Starting Linode instance {instance_id}")
        return True

    def stop_instance(self, instance_id: str) -> bool:
        """Stop a running Linode instance"""
        # TODO: Actual API call
        logger.info(f"Stopping Linode instance {instance_id}")
        return True



class ScalewayProvider(Provider):
    """Scaleway cloud provider"""

    def _initialize_templates(self):
        """Initialize Scaleway instance types"""
        self.templates = [
            ProviderTemplate(
                id="scaleway-dev1-s",
                name="DEV1-S",
                provider="scaleway",
                cpu=2,
                memory_gb=2,
                storage_gb=20,
                bandwidth_tb=0.2,
                price_hourly=0.0045,
                price_monthly=3.00,
                regions=["par1", "ams1", "waw1"],
                features=["ssd", "cloud", "x86"]
            ),
            ProviderTemplate(
                id="scaleway-dev1-m",
                name="DEV1-M",
                provider="scaleway",
                cpu=3,
                memory_gb=4,
                storage_gb=40,
                bandwidth_tb=0.5,
                price_hourly=0.0090,
                price_monthly=6.00,
                regions=["par1", "ams1", "waw1"],
                features=["ssd", "cloud", "x86"]
            ),
            ProviderTemplate(
                id="scaleway-gp1-xs",
                name="GP1-XS",
                provider="scaleway",
                cpu=4,
                memory_gb=16,
                storage_gb=150,
                bandwidth_tb=1,
                price_hourly=0.11,
                price_monthly=73.00,
                regions=["par1", "ams1", "waw1"],
                features=["ssd", "cloud", "x86", "high-memory"]
            ),
            ProviderTemplate(
                id="scaleway-gp1-s",
                name="GP1-S",
                provider="scaleway",
                cpu=8,
                memory_gb=32,
                storage_gb=300,
                bandwidth_tb=2,
                price_hourly=0.22,
                price_monthly=147.00,
                regions=["par1", "ams1", "waw1"],
                features=["ssd", "cloud", "x86", "high-memory"]
            ),
            ProviderTemplate(
                id="scaleway-render-s",
                name="RENDER-S",
                provider="scaleway",
                cpu=10,
                memory_gb=45,
                storage_gb=200,
                bandwidth_tb=2,
                price_hourly=0.44,
                price_monthly=294.00,
                gpu="NVIDIA T4",
                regions=["par1", "ams1"],
                features=["nvme", "cloud", "gpu", "x86"]
            ),
            ProviderTemplate(
                id="scaleway-h100-1-80g",
                name="H100-1-80G",
                provider="scaleway",
                cpu=26,
                memory_gb=200,
                storage_gb=400,
                bandwidth_tb=5,
                price_hourly=3.30,
                price_monthly=2200.00,
                gpu="NVIDIA H100 80GB",
                regions=["par1"],
                features=["ssd", "cloud", "gpu", "x86", "high-memory"]
            ),
        ]

    def _initialize_regions(self):
        """Initialize Scaleway datacenter regions"""
        self.regions = ["par1", "par2", "ams1", "ams2", "waw1"]

    def deploy(self, template_id: str, config: dict) -> dict:
        """Deploy Scaleway instance"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        logger.info(f"Deploying Scaleway {template_id} in {config.get('region')}")

        return {
            'id': f"scaleway-{config.get('name', 'instance')}",
            'name': config.get('name', 'unnamed'),
            'provider': 'scaleway',
            'template': template_id,
            'region': config.get('region', 'par1'),
            'status': 'deploying',
            'ip_address': '51.159.0.100',
            'cost_hourly': template.price_hourly,
        }

    def list_instances(self) -> List[dict]:
        """List Scaleway instances"""
        return []
    def get_instance(self, instance_id: str) -> dict:
        """Get details for a specific Scaleway instance"""
        # TODO: Actual API call
        logger.info(f"Getting Scaleway instance {instance_id}")
        return {
            'id': instance_id,
            'status': 'running',
            'provider': 'scaleway',
        }

    def delete_instance(self, instance_id: str) -> bool:
        """Delete a Scaleway instance"""
        # TODO: Actual API call
        logger.info(f"Deleting Scaleway instance {instance_id}")
        return True

    def start_instance(self, instance_id: str) -> bool:
        """Start a stopped Scaleway instance"""
        # TODO: Actual API call
        logger.info(f"Starting Scaleway instance {instance_id}")
        return True

    def stop_instance(self, instance_id: str) -> bool:
        """Stop a running Scaleway instance"""
        # TODO: Actual API call
        logger.info(f"Stopping Scaleway instance {instance_id}")
        return True



class ProviderManager:
    """Manager for all hardware providers"""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or Path.home() / ".capsule" / "providers.yml"
        self.providers: Dict[str, Provider] = {}
        self._load_config()
        self._initialize_providers()

    def _load_config(self):
        """Load provider configuration"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = {}
            self._save_config()

    def _save_config(self):
        """Save provider configuration"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f)

    def _initialize_providers(self):
        """Initialize all providers"""
        self.providers = {
            'hivelocity': HivelocityProvider('hivelocity',
                                            self.config.get('hivelocity', {}).get('api_key')),
            'digitalocean': DigitalOceanProvider('digitalocean',
                                                self.config.get('digitalocean', {}).get('api_key')),
            'vultr': VultrProvider('vultr',
                                  self.config.get('vultr', {}).get('api_key')),
            'aws': AWSProvider('aws',
                             self.config.get('aws', {}).get('api_key')),
            'equinix': EquinixMetalProvider('equinix',
                                           self.config.get('equinix', {}).get('api_key')),
            'linode': LinodeProvider('linode',
                                    self.config.get('linode', {}).get('api_key')),
            'scaleway': ScalewayProvider('scaleway',
                                        self.config.get('scaleway', {}).get('api_key')),
        }

    def list_providers(self) -> List[str]:
        """List all available providers"""
        return list(self.providers.keys())

    def get_provider(self, name: str) -> Optional[Provider]:
        """Get provider by name"""
        return self.providers.get(name)

    def get_all_templates(self) -> List[ProviderTemplate]:
        """Get all templates from all providers"""
        templates = []
        for provider in self.providers.values():
            templates.extend(provider.templates)
        return templates

    def compare_templates(self, min_cpu: int = 0, min_memory: int = 0,
                         max_price: float = float('inf')) -> List[ProviderTemplate]:
        """Compare templates across providers based on specs

        Args:
            min_cpu: Minimum CPU cores
            min_memory: Minimum memory in GB
            max_price: Maximum hourly price

        Returns:
            List of matching templates sorted by price
        """
        matching = []
        for template in self.get_all_templates():
            if (template.cpu >= min_cpu and
                template.memory_gb >= min_memory and
                template.price_hourly <= max_price):
                matching.append(template)

        # Sort by price (hourly)
        return sorted(matching, key=lambda t: t.price_hourly)

    def get_cheapest_option(self, min_cpu: int = 1, min_memory: int = 1) -> Optional[ProviderTemplate]:
        """Get the cheapest template matching requirements"""
        options = self.compare_templates(min_cpu=min_cpu, min_memory=min_memory)
        return options[0] if options else None

    def deploy_to_provider(self, provider_name: str, template_id: str, config: dict) -> dict:
        """Deploy to a specific provider

        Args:
            provider_name: Provider identifier
            template_id: Template/instance type ID
            config: Deployment configuration

        Returns:
            Deployed instance information
        """
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not found")

        return provider.deploy(template_id, config)

    def configure_provider(self, provider_name: str, api_key: str):
        """Configure provider API credentials"""
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        self.config.setdefault(provider_name, {})['api_key'] = api_key
        self._save_config()
        self._initialize_providers()

        logger.info(f"Configured {provider_name} provider")


def get_default_manager() -> ProviderManager:
    """Get default provider manager instance"""
    return ProviderManager()


if __name__ == "__main__":
    # Demo usage
    manager = ProviderManager()

    print("Available Providers:")
    for provider_name in manager.list_providers():
        provider = manager.get_provider(provider_name)
        print(f"  {provider_name}: {len(provider.templates)} templates, {len(provider.regions)} regions")

    print("\nCheapest 4 CPU / 8 GB option:")
    cheapest = manager.get_cheapest_option(min_cpu=4, min_memory=8)
    if cheapest:
        print(f"  {cheapest.name} ({cheapest.provider}): ${cheapest.price_hourly}/hr")

    print("\nAll templates under $0.10/hr:")
    cheap_templates = manager.compare_templates(max_price=0.10)
    for t in cheap_templates[:5]:
        print(f"  {t.provider:12} {t.name:20} ${t.price_hourly:.3f}/hr")
