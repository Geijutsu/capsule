"""
XNode Inventory Management System for Capsule

This module provides comprehensive inventory management for tracking deployed xNodes
across all providers. It includes cost tracking, deployment history, analytics, and
export/import capabilities.

Classes:
    DeploymentRecord: Historical record of xNode deployments
    CostReport: Cost analysis and projections
    XNodeInventory: Main inventory management system
"""

import json
import csv
import logging
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import defaultdict

# Import XNode from openmesh module
from .openmesh_core import XNode


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DeploymentRecord:
    """
    Historical record of an xNode deployment.

    Tracks lifecycle information including deployment, termination, costs,
    and uptime for analytics and reporting purposes.

    Attributes:
        xnode_id: Unique identifier for the xNode
        provider: Cloud/infrastructure provider name
        template: Configuration template used for deployment
        deployed_at: Timestamp when xNode was deployed
        terminated_at: Timestamp when xNode was terminated (None if still running)
        total_cost: Accumulated cost for this deployment
        uptime_hours: Total hours xNode was running
        region: Deployment region
        name: Human-readable name
        tags: Organizational tags
    """
    xnode_id: str
    provider: str
    template: str
    deployed_at: datetime
    terminated_at: Optional[datetime] = None
    total_cost: float = 0.0
    uptime_hours: float = 0.0
    region: Optional[str] = None
    name: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper datetime serialization."""
        data = asdict(self)
        data['deployed_at'] = self.deployed_at.isoformat()
        if self.terminated_at:
            data['terminated_at'] = self.terminated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeploymentRecord':
        """Create instance from dictionary."""
        data = data.copy()
        if isinstance(data.get('deployed_at'), str):
            data['deployed_at'] = datetime.fromisoformat(data['deployed_at'])
        if data.get('terminated_at') and isinstance(data['terminated_at'], str):
            data['terminated_at'] = datetime.fromisoformat(data['terminated_at'])
        return cls(**data)

    def calculate_uptime(self) -> float:
        """Calculate current uptime in hours."""
        end_time = self.terminated_at or datetime.now()
        delta = end_time - self.deployed_at
        return delta.total_seconds() / 3600

    def is_active(self) -> bool:
        """Check if deployment is still active."""
        return self.terminated_at is None


@dataclass
class CostReport:
    """
    Cost analysis and projection report.

    Provides comprehensive cost breakdown by provider, region, and time period
    with projections for future spending.

    Attributes:
        total_hourly: Total hourly cost across all xNodes
        total_daily: Total daily cost (hourly * 24)
        total_monthly: Total monthly cost (daily * 30)
        by_provider: Cost breakdown by provider
        by_region: Cost breakdown by region
        projected_annual: Projected annual cost
        active_count: Number of active xNodes
        total_count: Total number of xNodes (including stopped)
    """
    total_hourly: float
    total_daily: float
    total_monthly: float
    by_provider: Dict[str, float]
    by_region: Dict[str, float]
    projected_annual: float
    active_count: int = 0
    total_count: int = 0

    def generate_report(self) -> str:
        """Generate formatted text report."""
        report_lines = [
            "=" * 60,
            "XNODE INVENTORY COST REPORT",
            "=" * 60,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "SUMMARY",
            "-" * 60,
            f"Active xNodes:    {self.active_count}",
            f"Total xNodes:     {self.total_count}",
            "",
            "COST OVERVIEW",
            "-" * 60,
            f"Hourly:           ${self.total_hourly:.2f}",
            f"Daily:            ${self.total_daily:.2f}",
            f"Monthly:          ${self.total_monthly:.2f}",
            f"Annual (proj.):   ${self.projected_annual:.2f}",
            "",
            "BY PROVIDER",
            "-" * 60,
        ]

        if self.by_provider:
            for provider, cost in sorted(self.by_provider.items(), key=lambda x: x[1], reverse=True):
                report_lines.append(f"  {provider:<20} ${cost:.2f}/hour")
        else:
            report_lines.append("  No data available")

        report_lines.extend([
            "",
            "BY REGION",
            "-" * 60,
        ])

        if self.by_region:
            for region, cost in sorted(self.by_region.items(), key=lambda x: x[1], reverse=True):
                report_lines.append(f"  {region:<20} ${cost:.2f}/hour")
        else:
            report_lines.append("  No data available")

        report_lines.append("=" * 60)

        return "\n".join(report_lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class XNodeInventory:
    """
    Main inventory management system for xNodes.

    Provides comprehensive tracking of all deployed xNodes including:
    - Current status and configuration
    - Deployment history
    - Cost tracking and analytics
    - Search and filter capabilities
    - Export/import functionality

    The inventory is persisted to ~/.capsule/inventory.json with automatic
    backups before modifications.

    Attributes:
        inventory_file: Path to inventory JSON file
        xnodes: Dictionary of active xNodes by ID
        history: List of deployment records
        metadata: General inventory metadata
    """

    VERSION = "1.0"

    def __init__(self, inventory_file: Optional[Path] = None):
        """
        Initialize XNodeInventory.

        Args:
            inventory_file: Path to inventory file, defaults to ~/.capsule/inventory.json
        """
        self.inventory_file = inventory_file or Path.home() / '.capsule' / 'inventory.json'
        self.xnodes: Dict[str, Dict[str, Any]] = {}
        self.history: List[DeploymentRecord] = []
        self.metadata: Dict[str, Any] = {
            'total_deployed': 0,
            'total_running': 0,
            'total_lifetime_cost': 0.0
        }

        self._ensure_directory()
        self.load()

        logger.info("Initialized XNodeInventory")

    def _ensure_directory(self):
        """Ensure inventory directory exists."""
        inventory_dir = self.inventory_file.parent
        try:
            inventory_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured inventory directory exists: {inventory_dir}")
        except Exception as e:
            logger.error(f"Failed to create inventory directory: {e}")
            raise

    def _backup_inventory(self):
        """Create backup of inventory file before modifications."""
        if not self.inventory_file.exists():
            return

        try:
            backup_file = self.inventory_file.with_suffix('.json.backup')
            shutil.copy2(self.inventory_file, backup_file)
            logger.debug(f"Created inventory backup: {backup_file}")
        except Exception as e:
            logger.warning(f"Failed to create inventory backup: {e}")

    def load(self):
        """
        Load inventory from JSON file.

        If file doesn't exist, initializes empty inventory.
        Handles format migrations and validation.
        """
        if not self.inventory_file.exists():
            logger.info("No existing inventory found, starting fresh")
            return

        try:
            with open(self.inventory_file, 'r') as f:
                data = json.load(f)

            # Load xnodes
            self.xnodes = data.get('xnodes', {})

            # Load history
            history_data = data.get('history', [])
            self.history = [DeploymentRecord.from_dict(record) for record in history_data]

            # Load metadata
            self.metadata = data.get('metadata', self.metadata)

            logger.info(f"Loaded inventory from {self.inventory_file}")
            logger.info(f"  xNodes: {len(self.xnodes)}, History: {len(self.history)}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse inventory JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load inventory: {e}")
            raise

    def save(self):
        """
        Save inventory to JSON file.

        Creates backup before saving and updates metadata.
        """
        try:
            # Backup existing file
            self._backup_inventory()

            # Prepare data
            data = {
                'version': self.VERSION,
                'last_updated': datetime.now().isoformat(),
                'xnodes': self.xnodes,
                'history': [record.to_dict() for record in self.history],
                'metadata': self.metadata
            }

            # Save to file
            with open(self.inventory_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved inventory to {self.inventory_file}")

        except Exception as e:
            logger.error(f"Failed to save inventory: {e}")
            raise

    def add_xnode(
        self,
        xnode: XNode,
        provider: str,
        template: str = "default",
        cost_hourly: float = 0.0,
        tags: Optional[List[str]] = None
    ) -> None:
        """
        Add xNode to inventory.

        Args:
            xnode: XNode instance to add
            provider: Provider name (e.g., 'hivelocity', 'aws', 'gcp')
            template: Template/configuration name used
            cost_hourly: Hourly cost for this xNode
            tags: Optional list of tags for organization

        Raises:
            ValueError: If xNode ID already exists in inventory
        """
        if xnode.id in self.xnodes:
            raise ValueError(f"XNode with ID {xnode.id} already exists in inventory")

        tags = tags or []

        # Create inventory entry
        entry = {
            'id': xnode.id,
            'name': xnode.name,
            'provider': provider,
            'template': template,
            'status': xnode.status,
            'ip_address': xnode.ip_address,
            'ssh_port': xnode.ssh_port,
            'region': xnode.region,
            'deployed_at': xnode.created_at.isoformat(),
            'cost_hourly': cost_hourly,
            'tags': tags,
            'metadata': xnode.metadata
        }

        self.xnodes[xnode.id] = entry

        # Create deployment record
        record = DeploymentRecord(
            xnode_id=xnode.id,
            provider=provider,
            template=template,
            deployed_at=xnode.created_at,
            region=xnode.region,
            name=xnode.name,
            tags=tags
        )
        self.history.append(record)

        # Update metadata
        self.metadata['total_deployed'] += 1
        if xnode.status == 'running':
            self.metadata['total_running'] += 1

        self.save()
        logger.info(f"Added xNode {xnode.id} ({xnode.name}) to inventory")

    def remove_xnode(self, xnode_id: str) -> None:
        """
        Remove xNode from inventory.

        Marks deployment as terminated in history and removes from active inventory.

        Args:
            xnode_id: Unique identifier of xNode to remove

        Raises:
            KeyError: If xNode ID not found in inventory
        """
        if xnode_id not in self.xnodes:
            raise KeyError(f"XNode {xnode_id} not found in inventory")

        entry = self.xnodes[xnode_id]

        # Update history record
        for record in self.history:
            if record.xnode_id == xnode_id and record.is_active():
                record.terminated_at = datetime.now()
                record.uptime_hours = record.calculate_uptime()
                record.total_cost = record.uptime_hours * entry.get('cost_hourly', 0.0)
                self.metadata['total_lifetime_cost'] += record.total_cost
                break

        # Remove from active inventory
        if entry['status'] == 'running':
            self.metadata['total_running'] -= 1

        del self.xnodes[xnode_id]

        self.save()
        logger.info(f"Removed xNode {xnode_id} from inventory")

    def get_xnode(self, xnode_id: str) -> Dict[str, Any]:
        """
        Get xNode data by ID.

        Args:
            xnode_id: Unique identifier of xNode

        Returns:
            Dictionary containing xNode data

        Raises:
            KeyError: If xNode ID not found
        """
        if xnode_id not in self.xnodes:
            raise KeyError(f"XNode {xnode_id} not found in inventory")

        return self.xnodes[xnode_id].copy()

    def update_xnode(self, xnode_id: str, **kwargs) -> None:
        """
        Update xNode attributes.

        Args:
            xnode_id: Unique identifier of xNode
            **kwargs: Attributes to update

        Raises:
            KeyError: If xNode ID not found
        """
        if xnode_id not in self.xnodes:
            raise KeyError(f"XNode {xnode_id} not found in inventory")

        # Track status changes
        old_status = self.xnodes[xnode_id].get('status')
        new_status = kwargs.get('status', old_status)

        # Update attributes
        self.xnodes[xnode_id].update(kwargs)

        # Update running count if status changed
        if old_status != new_status:
            if old_status == 'running':
                self.metadata['total_running'] -= 1
            if new_status == 'running':
                self.metadata['total_running'] += 1

        self.save()
        logger.debug(f"Updated xNode {xnode_id}")

    def list_all(self) -> List[Dict[str, Any]]:
        """
        List all xNodes in inventory.

        Returns:
            List of xNode dictionaries
        """
        return list(self.xnodes.values())

    def list_by_provider(self, provider: str) -> List[Dict[str, Any]]:
        """
        List xNodes by provider.

        Args:
            provider: Provider name to filter by

        Returns:
            List of xNode dictionaries from specified provider
        """
        return [
            xnode for xnode in self.xnodes.values()
            if xnode.get('provider') == provider
        ]

    def list_by_status(self, status: str) -> List[Dict[str, Any]]:
        """
        List xNodes by status.

        Args:
            status: Status to filter by (running, stopped, deploying, error)

        Returns:
            List of xNode dictionaries with specified status
        """
        return [
            xnode for xnode in self.xnodes.values()
            if xnode.get('status') == status
        ]

    def list_by_tags(self, tags: List[str], match_all: bool = False) -> List[Dict[str, Any]]:
        """
        List xNodes by tags.

        Args:
            tags: List of tags to filter by
            match_all: If True, xNode must have all tags; if False, any tag matches

        Returns:
            List of xNode dictionaries matching tag criteria
        """
        results = []
        for xnode in self.xnodes.values():
            xnode_tags = set(xnode.get('tags', []))
            search_tags = set(tags)

            if match_all:
                if search_tags.issubset(xnode_tags):
                    results.append(xnode)
            else:
                if xnode_tags.intersection(search_tags):
                    results.append(xnode)

        return results

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search xNodes by name or ID.

        Args:
            query: Search query string

        Returns:
            List of matching xNode dictionaries
        """
        query_lower = query.lower()
        return [
            xnode for xnode in self.xnodes.values()
            if query_lower in xnode.get('name', '').lower()
            or query_lower in xnode.get('id', '').lower()
        ]

    def get_total_cost(self) -> Dict[str, float]:
        """
        Calculate total costs across all time periods.

        Returns:
            Dictionary with hourly, daily, monthly costs
        """
        total_hourly = sum(
            xnode.get('cost_hourly', 0.0)
            for xnode in self.xnodes.values()
            if xnode.get('status') == 'running'
        )

        return {
            'hourly': total_hourly,
            'daily': total_hourly * 24,
            'monthly': total_hourly * 24 * 30,
            'annual': total_hourly * 24 * 365
        }

    def get_cost_report(self) -> CostReport:
        """
        Generate comprehensive cost report.

        Returns:
            CostReport instance with detailed cost analysis
        """
        by_provider = defaultdict(float)
        by_region = defaultdict(float)
        active_count = 0

        for xnode in self.xnodes.values():
            if xnode.get('status') == 'running':
                cost = xnode.get('cost_hourly', 0.0)
                provider = xnode.get('provider', 'unknown')
                region = xnode.get('region', 'unknown')

                by_provider[provider] += cost
                by_region[region] += cost
                active_count += 1

        costs = self.get_total_cost()

        return CostReport(
            total_hourly=costs['hourly'],
            total_daily=costs['daily'],
            total_monthly=costs['monthly'],
            projected_annual=costs['annual'],
            by_provider=dict(by_provider),
            by_region=dict(by_region),
            active_count=active_count,
            total_count=len(self.xnodes)
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive inventory statistics.

        Returns:
            Dictionary containing various statistics and metrics
        """
        # Status distribution
        status_counts = defaultdict(int)
        for xnode in self.xnodes.values():
            status_counts[xnode.get('status', 'unknown')] += 1

        # Provider distribution
        provider_counts = defaultdict(int)
        for xnode in self.xnodes.values():
            provider_counts[xnode.get('provider', 'unknown')] += 1

        # Region distribution
        region_counts = defaultdict(int)
        for xnode in self.xnodes.values():
            region = xnode.get('region', 'unknown')
            region_counts[region] += 1

        # Active deployments
        active_history = [r for r in self.history if r.is_active()]

        # Average uptime for terminated deployments
        terminated = [r for r in self.history if not r.is_active()]
        avg_uptime = (
            sum(r.uptime_hours for r in terminated) / len(terminated)
            if terminated else 0.0
        )

        # Most expensive xNodes
        sorted_by_cost = sorted(
            self.xnodes.values(),
            key=lambda x: x.get('cost_hourly', 0.0),
            reverse=True
        )
        most_expensive = [
            {'id': x['id'], 'name': x['name'], 'cost_hourly': x.get('cost_hourly', 0.0)}
            for x in sorted_by_cost[:5]
        ]

        # Longest running
        longest_running = []
        for record in sorted(active_history, key=lambda r: r.deployed_at):
            uptime = record.calculate_uptime()
            longest_running.append({
                'id': record.xnode_id,
                'name': record.name,
                'uptime_hours': uptime,
                'uptime_days': uptime / 24
            })
        longest_running = longest_running[:5]

        return {
            'total_xnodes': len(self.xnodes),
            'status_distribution': dict(status_counts),
            'provider_distribution': dict(provider_counts),
            'region_distribution': dict(region_counts),
            'total_deployments': len(self.history),
            'active_deployments': len(active_history),
            'terminated_deployments': len(terminated),
            'average_uptime_hours': avg_uptime,
            'lifetime_cost': self.metadata.get('total_lifetime_cost', 0.0),
            'most_expensive': most_expensive,
            'longest_running': longest_running
        }

    def export_csv(self, filename: str) -> None:
        """
        Export inventory to CSV file.

        Args:
            filename: Path to output CSV file

        Raises:
            Exception: On export failure
        """
        try:
            filepath = Path(filename)

            # Prepare rows
            rows = []
            for xnode in self.xnodes.values():
                rows.append({
                    'id': xnode['id'],
                    'name': xnode['name'],
                    'provider': xnode.get('provider', ''),
                    'status': xnode['status'],
                    'ip_address': xnode['ip_address'],
                    'region': xnode.get('region', ''),
                    'deployed_at': xnode.get('deployed_at', ''),
                    'cost_hourly': xnode.get('cost_hourly', 0.0),
                    'tags': ','.join(xnode.get('tags', []))
                })

            if not rows:
                logger.warning("No xNodes to export")
                return

            # Write CSV
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            logger.info(f"Exported {len(rows)} xNodes to {filename}")

        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            raise

    def import_csv(self, filename: str) -> int:
        """
        Import xNodes from CSV file.

        CSV must have columns: id, name, provider, status, ip_address
        Optional columns: region, deployed_at, cost_hourly, tags

        Args:
            filename: Path to input CSV file

        Returns:
            Number of xNodes imported

        Raises:
            Exception: On import failure
        """
        try:
            filepath = Path(filename)

            if not filepath.exists():
                raise FileNotFoundError(f"CSV file not found: {filename}")

            imported = 0

            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # Parse required fields
                    xnode_id = row['id']

                    # Skip if already exists
                    if xnode_id in self.xnodes:
                        logger.warning(f"Skipping duplicate xNode: {xnode_id}")
                        continue

                    # Parse optional fields
                    deployed_at = row.get('deployed_at')
                    if deployed_at:
                        try:
                            deployed_at = datetime.fromisoformat(deployed_at)
                        except ValueError:
                            deployed_at = datetime.now()
                    else:
                        deployed_at = datetime.now()

                    tags = row.get('tags', '')
                    tags = [t.strip() for t in tags.split(',') if t.strip()]

                    # Create XNode instance
                    xnode = XNode(
                        id=xnode_id,
                        name=row['name'],
                        status=row['status'],
                        ip_address=row['ip_address'],
                        region=row.get('region'),
                        created_at=deployed_at
                    )

                    # Add to inventory
                    self.add_xnode(
                        xnode=xnode,
                        provider=row['provider'],
                        template=row.get('template', 'imported'),
                        cost_hourly=float(row.get('cost_hourly', 0.0)),
                        tags=tags
                    )

                    imported += 1

            logger.info(f"Imported {imported} xNodes from {filename}")
            return imported

        except Exception as e:
            logger.error(f"Failed to import from CSV: {e}")
            raise

    def get_deployment_history(
        self,
        xnode_id: Optional[str] = None,
        provider: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[DeploymentRecord]:
        """
        Get deployment history with optional filtering.

        Args:
            xnode_id: Filter by specific xNode ID
            provider: Filter by provider
            limit: Maximum number of records to return

        Returns:
            List of DeploymentRecord instances
        """
        records = self.history

        # Apply filters
        if xnode_id:
            records = [r for r in records if r.xnode_id == xnode_id]

        if provider:
            records = [r for r in records if r.provider == provider]

        # Sort by deployment time (newest first)
        records = sorted(records, key=lambda r: r.deployed_at, reverse=True)

        # Apply limit
        if limit:
            records = records[:limit]

        return records

    def cleanup_old_history(self, days: int = 90) -> int:
        """
        Remove terminated deployments older than specified days.

        Args:
            days: Number of days to retain history

        Returns:
            Number of records removed
        """
        cutoff = datetime.now() - timedelta(days=days)

        original_count = len(self.history)

        self.history = [
            record for record in self.history
            if record.is_active() or
            (record.terminated_at and record.terminated_at > cutoff)
        ]

        removed = original_count - len(self.history)

        if removed > 0:
            self.save()
            logger.info(f"Cleaned up {removed} old history records")

        return removed


# Convenience functions

def get_default_inventory() -> XNodeInventory:
    """
    Get XNodeInventory instance with default configuration.

    Returns:
        XNodeInventory with default settings
    """
    return XNodeInventory()


def generate_cost_report() -> str:
    """
    Generate and return formatted cost report.

    Returns:
        Formatted cost report string
    """
    inventory = get_default_inventory()
    report = inventory.get_cost_report()
    return report.generate_report()


def export_inventory_csv(filename: str = "xnode_inventory.csv") -> None:
    """
    Quick export of inventory to CSV.

    Args:
        filename: Output CSV filename
    """
    inventory = get_default_inventory()
    inventory.export_csv(filename)


if __name__ == '__main__':
    # Example usage and testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize inventory
    inventory = XNodeInventory()

    # Example: Create sample xNode
    sample_xnode = XNode(
        id='xnode-test-001',
        name='test-node-1',
        status='running',
        ip_address='192.168.1.100',
        region='us-east-1'
    )

    # Add to inventory
    try:
        inventory.add_xnode(
            xnode=sample_xnode,
            provider='hivelocity',
            template='standard',
            cost_hourly=0.15,
            tags=['test', 'development']
        )
        print(f"Added xNode: {sample_xnode.id}")
    except ValueError as e:
        print(f"XNode already exists: {e}")

    # List all xNodes
    all_xnodes = inventory.list_all()
    print(f"\nTotal xNodes: {len(all_xnodes)}")

    # Generate cost report
    report = inventory.get_cost_report()
    print(f"\n{report.generate_report()}")

    # Get statistics
    stats = inventory.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total deployments: {stats['total_deployments']}")
    print(f"  Active deployments: {stats['active_deployments']}")
    print(f"  Lifetime cost: ${stats['lifetime_cost']:.2f}")
