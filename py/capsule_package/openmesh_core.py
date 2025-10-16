"""
OpenMesh Management Module for Capsule

This module provides comprehensive xnode management functionality for the OpenMesh
distributed infrastructure platform. It handles xnode deployment, lifecycle management,
tunneling, and configuration.

Classes:
    XNode: Represents an xnode instance with its properties and state
    OpenMeshConfig: Manages configuration and settings for OpenMesh operations
    XNodeManager: Core operations for xnode lifecycle and management
"""

import logging
import subprocess
import yaml
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import requests
import json


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class XNode:
    """
    Represents an OpenMesh xnode instance.

    An xnode is a distributed compute node in the OpenMesh network that can run
    containerized workloads and provide decentralized infrastructure services.

    Attributes:
        id: Unique identifier for the xnode
        name: Human-readable name for the xnode
        status: Current state (running, stopped, deploying, error)
        ip_address: Public IP address of the xnode
        ssh_port: SSH port for remote access (default: 22)
        tunnel_port: Local port for SSH tunnel (default: None)
        created_at: Timestamp when the xnode was created
        region: Geographical region where xnode is deployed
        metadata: Additional xnode metadata and properties
    """
    id: str
    name: str
    status: str
    ip_address: str
    ssh_port: int = 22
    tunnel_port: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    region: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert XNode instance to dictionary representation.

        Returns:
            Dictionary containing all xnode attributes with datetime serialized to ISO format
        """
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'XNode':
        """
        Create XNode instance from dictionary.

        Args:
            data: Dictionary containing xnode attributes

        Returns:
            XNode instance constructed from dictionary data
        """
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

    def is_running(self) -> bool:
        """Check if xnode is currently in running state."""
        return self.status == "running"

    def is_stopped(self) -> bool:
        """Check if xnode is currently stopped."""
        return self.status == "stopped"

    def is_deploying(self) -> bool:
        """Check if xnode is currently being deployed."""
        return self.status == "deploying"


class OpenMeshConfig:
    """
    Configuration management for OpenMesh operations.

    Handles loading, saving, and accessing configuration settings for xnode
    management including SSH keys, API endpoints, and default preferences.

    Attributes:
        config_file: Path to YAML configuration file
        default_ssh_key: Path to default SSH private key
        default_region: Default deployment region
        api_endpoint: OpenMesh API endpoint URL
        config_data: Loaded configuration dictionary
    """

    DEFAULT_CONFIG = {
        'default_ssh_key': '~/.ssh/id_rsa',
        'default_region': 'us-east-1',
        'api_endpoint': 'https://api.openmesh.network/v1',
        'timeout': 30,
        'max_retries': 3,
        'log_level': 'INFO'
    }

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize OpenMeshConfig.

        Args:
            config_file: Path to config file, defaults to ~/.capsule/openmesh.yml
        """
        self.config_file = config_file or Path.home() / '.capsule' / 'openmesh.yml'
        self.config_data = {}
        self._ensure_config_directory()
        self.load()

    def _ensure_config_directory(self):
        """Create configuration directory if it doesn't exist."""
        config_dir = self.config_file.parent
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured config directory exists: {config_dir}")
        except Exception as e:
            logger.error(f"Failed to create config directory: {e}")
            raise

    def load(self):
        """
        Load configuration from YAML file.

        If file doesn't exist, initializes with default configuration.
        Merges loaded config with defaults to ensure all required keys exist.
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded_config = yaml.safe_load(f) or {}
                    # Merge with defaults to ensure all keys exist
                    self.config_data = {**self.DEFAULT_CONFIG, **loaded_config}
                logger.info(f"Loaded configuration from {self.config_file}")
            else:
                logger.info(f"Config file not found, using defaults")
                self.config_data = self.DEFAULT_CONFIG.copy()
                self.save()
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_file}: {e}")
            self.config_data = self.DEFAULT_CONFIG.copy()

    def save(self):
        """
        Save current configuration to YAML file.

        Writes configuration data to file with proper formatting.
        """
        try:
            with open(self.config_file, 'w') as f:
                yaml.dump(self.config_data, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_file}: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key to retrieve
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config_data.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set configuration value and save.

        Args:
            key: Configuration key to set
            value: Value to assign
        """
        self.config_data[key] = value
        self.save()

    @property
    def default_ssh_key(self) -> str:
        """Get default SSH key path."""
        return str(Path(self.get('default_ssh_key')).expanduser())

    @property
    def default_region(self) -> str:
        """Get default deployment region."""
        return self.get('default_region')

    @property
    def api_endpoint(self) -> str:
        """Get API endpoint URL."""
        return self.get('api_endpoint')

    @property
    def timeout(self) -> int:
        """Get API request timeout in seconds."""
        return self.get('timeout', 30)

    @property
    def max_retries(self) -> int:
        """Get maximum number of API retries."""
        return self.get('max_retries', 3)


class XNodeManager:
    """
    Core xnode management operations.

    Provides comprehensive functionality for xnode lifecycle management including
    deployment, status monitoring, starting/stopping, and SSH tunnel creation.

    Attributes:
        config: OpenMeshConfig instance for settings
        active_tunnels: Dictionary tracking active SSH tunnels
    """

    def __init__(self, config: Optional[OpenMeshConfig] = None):
        """
        Initialize XNodeManager.

        Args:
            config: OpenMeshConfig instance, creates default if not provided
        """
        self.config = config or OpenMeshConfig()
        self.active_tunnels: Dict[str, subprocess.Popen] = {}
        logger.info("Initialized XNodeManager")

    def _api_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make authenticated API request to OpenMesh API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            JSON response data

        Raises:
            requests.RequestException: On API request failure
        """
        url = f"{self.config.api_endpoint}/{endpoint.lstrip('/')}"

        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=self.config.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"API request failed: {method} {url} - {e}")
            raise

    def list_available_xnodes(self) -> List[Dict[str, Any]]:
        """
        List all available xnode configurations and templates.

        Retrieves the catalog of available xnode types, configurations,
        and deployment options from the OpenMesh platform.

        Returns:
            List of available xnode configuration dictionaries

        Raises:
            Exception: On API communication failure
        """
        try:
            logger.info("Fetching available xnode configurations")
            response = self._api_request('GET', '/xnodes/available')
            xnodes = response.get('xnodes', [])
            logger.info(f"Found {len(xnodes)} available xnode configurations")
            return xnodes
        except Exception as e:
            logger.error(f"Failed to list available xnodes: {e}")
            raise

    def list_running_xnodes(self) -> List[XNode]:
        """
        List all currently running xnode instances.

        Queries the OpenMesh API for all active xnodes and returns
        them as XNode objects with current status information.

        Returns:
            List of XNode instances representing running xnodes

        Raises:
            Exception: On API communication failure
        """
        try:
            logger.info("Fetching running xnodes")
            response = self._api_request('GET', '/xnodes/running')
            xnodes_data = response.get('xnodes', [])

            xnodes = []
            for data in xnodes_data:
                try:
                    xnode = XNode(
                        id=data['id'],
                        name=data['name'],
                        status=data['status'],
                        ip_address=data['ip_address'],
                        ssh_port=data.get('ssh_port', 22),
                        region=data.get('region'),
                        metadata=data.get('metadata', {})
                    )
                    xnodes.append(xnode)
                except KeyError as e:
                    logger.warning(f"Skipping xnode with missing field: {e}")
                    continue

            logger.info(f"Found {len(xnodes)} running xnodes")
            return xnodes
        except Exception as e:
            logger.error(f"Failed to list running xnodes: {e}")
            raise

    def deploy_xnode(
        self,
        name: str,
        region: Optional[str] = None,
        config_template: Optional[str] = None,
        **kwargs
    ) -> XNode:
        """
        Deploy a new xnode instance.

        Creates and deploys a new xnode with the specified configuration.
        Returns immediately with deploying status; use get_xnode_status to
        monitor deployment progress.

        Args:
            name: Name for the new xnode
            region: Deployment region (uses default if not specified)
            config_template: Template name for xnode configuration
            **kwargs: Additional deployment parameters

        Returns:
            XNode instance representing the newly deployed xnode

        Raises:
            Exception: On deployment failure
        """
        region = region or self.config.default_region

        try:
            logger.info(f"Deploying xnode '{name}' in region {region}")

            payload = {
                'name': name,
                'region': region,
                'config_template': config_template,
                **kwargs
            }

            response = self._api_request('POST', '/xnodes/deploy', json=payload)

            xnode = XNode(
                id=response['id'],
                name=response['name'],
                status=response.get('status', 'deploying'),
                ip_address=response.get('ip_address', ''),
                ssh_port=response.get('ssh_port', 22),
                region=region,
                metadata=response.get('metadata', {})
            )

            logger.info(f"Successfully deployed xnode '{name}' with ID: {xnode.id}")
            return xnode

        except Exception as e:
            logger.error(f"Failed to deploy xnode '{name}': {e}")
            raise

    def start_xnode(self, xnode_id: str) -> bool:
        """
        Start a stopped xnode.

        Args:
            xnode_id: Unique identifier of the xnode to start

        Returns:
            True if start command was successful

        Raises:
            Exception: On start failure
        """
        try:
            logger.info(f"Starting xnode {xnode_id}")
            response = self._api_request('POST', f'/xnodes/{xnode_id}/start')
            success = response.get('success', False)

            if success:
                logger.info(f"Successfully started xnode {xnode_id}")
            else:
                logger.warning(f"Start command sent but success unclear for {xnode_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to start xnode {xnode_id}: {e}")
            raise

    def stop_xnode(self, xnode_id: str) -> bool:
        """
        Stop a running xnode.

        Args:
            xnode_id: Unique identifier of the xnode to stop

        Returns:
            True if stop command was successful

        Raises:
            Exception: On stop failure
        """
        try:
            logger.info(f"Stopping xnode {xnode_id}")
            response = self._api_request('POST', f'/xnodes/{xnode_id}/stop')
            success = response.get('success', False)

            if success:
                logger.info(f"Successfully stopped xnode {xnode_id}")
            else:
                logger.warning(f"Stop command sent but success unclear for {xnode_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to stop xnode {xnode_id}: {e}")
            raise

    def restart_xnode(self, xnode_id: str) -> bool:
        """
        Restart an xnode (stop then start).

        Args:
            xnode_id: Unique identifier of the xnode to restart

        Returns:
            True if restart was successful

        Raises:
            Exception: On restart failure
        """
        try:
            logger.info(f"Restarting xnode {xnode_id}")
            response = self._api_request('POST', f'/xnodes/{xnode_id}/restart')
            success = response.get('success', False)

            if success:
                logger.info(f"Successfully restarted xnode {xnode_id}")
            else:
                logger.warning(f"Restart command sent but success unclear for {xnode_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to restart xnode {xnode_id}: {e}")
            raise

    def create_tunnel(
        self,
        xnode_id: str,
        local_port: int,
        remote_port: Optional[int] = None,
        ssh_key: Optional[str] = None
    ) -> subprocess.Popen:
        """
        Create SSH tunnel to an xnode.

        Establishes an SSH tunnel for secure access to xnode services.
        The tunnel process runs in the background and can be terminated
        using the returned Popen object.

        Args:
            xnode_id: Unique identifier of the target xnode
            local_port: Local port for tunnel endpoint
            remote_port: Remote port on xnode (defaults to local_port)
            ssh_key: Path to SSH key (uses default if not specified)

        Returns:
            subprocess.Popen object representing the tunnel process

        Raises:
            Exception: On tunnel creation failure
        """
        remote_port = remote_port or local_port
        ssh_key = ssh_key or self.config.default_ssh_key

        try:
            # Get xnode details
            xnode_status = self.get_xnode_status(xnode_id)
            ip_address = xnode_status.get('ip_address')
            ssh_port = xnode_status.get('ssh_port', 22)

            if not ip_address:
                raise ValueError(f"No IP address found for xnode {xnode_id}")

            logger.info(f"Creating SSH tunnel: localhost:{local_port} -> {ip_address}:{remote_port}")

            # Build SSH command
            ssh_cmd = [
                'ssh',
                '-i', ssh_key,
                '-L', f'{local_port}:localhost:{remote_port}',
                '-N',  # Don't execute remote command
                '-p', str(ssh_port),
                f'root@{ip_address}'
            ]

            # Start tunnel process
            process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Track active tunnel
            self.active_tunnels[xnode_id] = process

            logger.info(f"SSH tunnel established (PID: {process.pid})")
            return process

        except Exception as e:
            logger.error(f"Failed to create tunnel to xnode {xnode_id}: {e}")
            raise

    def get_xnode_status(self, xnode_id: str) -> Dict[str, Any]:
        """
        Get detailed status information for an xnode.

        Retrieves comprehensive status including state, resource usage,
        network configuration, and health metrics.

        Args:
            xnode_id: Unique identifier of the xnode

        Returns:
            Dictionary containing detailed xnode status and metrics

        Raises:
            Exception: On status retrieval failure
        """
        try:
            logger.debug(f"Fetching status for xnode {xnode_id}")
            response = self._api_request('GET', f'/xnodes/{xnode_id}/status')
            logger.debug(f"Retrieved status for xnode {xnode_id}: {response.get('status')}")
            return response
        except Exception as e:
            logger.error(f"Failed to get status for xnode {xnode_id}: {e}")
            raise

    def close_tunnel(self, xnode_id: str) -> bool:
        """
        Close active SSH tunnel to an xnode.

        Args:
            xnode_id: Unique identifier of the xnode

        Returns:
            True if tunnel was closed successfully
        """
        if xnode_id in self.active_tunnels:
            try:
                process = self.active_tunnels[xnode_id]
                process.terminate()
                process.wait(timeout=5)
                del self.active_tunnels[xnode_id]
                logger.info(f"Closed tunnel to xnode {xnode_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to close tunnel to xnode {xnode_id}: {e}")
                return False
        else:
            logger.warning(f"No active tunnel found for xnode {xnode_id}")
            return False

    def close_all_tunnels(self):
        """Close all active SSH tunnels."""
        xnode_ids = list(self.active_tunnels.keys())
        for xnode_id in xnode_ids:
            self.close_tunnel(xnode_id)
        logger.info("Closed all active tunnels")

    def delete_xnode(self, xnode_id: str, force: bool = False) -> bool:
        """
        Delete an xnode instance.

        Permanently removes an xnode from the OpenMesh platform.
        Use with caution as this operation is irreversible.

        Args:
            xnode_id: Unique identifier of the xnode to delete
            force: Force deletion even if xnode is running

        Returns:
            True if deletion was successful

        Raises:
            Exception: On deletion failure
        """
        try:
            logger.warning(f"Deleting xnode {xnode_id} (force={force})")

            payload = {'force': force}
            response = self._api_request('DELETE', f'/xnodes/{xnode_id}', json=payload)
            success = response.get('success', False)

            if success:
                logger.info(f"Successfully deleted xnode {xnode_id}")
                # Close any active tunnels
                self.close_tunnel(xnode_id)
            else:
                logger.warning(f"Delete command sent but success unclear for {xnode_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to delete xnode {xnode_id}: {e}")
            raise


# Convenience functions for common operations

def get_default_manager() -> XNodeManager:
    """
    Get XNodeManager instance with default configuration.

    Returns:
        XNodeManager with default OpenMeshConfig
    """
    return XNodeManager()


def quick_deploy(name: str, region: Optional[str] = None) -> XNode:
    """
    Quick xnode deployment with default settings.

    Args:
        name: Name for the xnode
        region: Optional deployment region

    Returns:
        Deployed XNode instance
    """
    manager = get_default_manager()
    return manager.deploy_xnode(name, region)


def quick_tunnel(xnode_id: str, local_port: int) -> subprocess.Popen:
    """
    Quick SSH tunnel creation with default settings.

    Args:
        xnode_id: Target xnode identifier
        local_port: Local port for tunnel

    Returns:
        subprocess.Popen for the tunnel process
    """
    manager = get_default_manager()
    return manager.create_tunnel(xnode_id, local_port)


if __name__ == '__main__':
    # Example usage and testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize manager
    manager = XNodeManager()

    # Example: List available xnodes
    try:
        available = manager.list_available_xnodes()
        print(f"Available xnode types: {len(available)}")
    except Exception as e:
        print(f"Error listing available xnodes: {e}")

    # Example: List running xnodes
    try:
        running = manager.list_running_xnodes()
        print(f"Running xnodes: {len(running)}")
        for xnode in running:
            print(f"  - {xnode.name} ({xnode.id}): {xnode.status}")
    except Exception as e:
        print(f"Error listing running xnodes: {e}")
