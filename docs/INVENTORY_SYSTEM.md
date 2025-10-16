# XNode Inventory Management System

Comprehensive inventory management for tracking deployed xNodes across all providers.

## Overview

The inventory system provides:
- **Centralized tracking** of all deployed xNodes
- **Cost monitoring** with hourly/daily/monthly projections
- **Deployment history** with uptime tracking
- **Advanced filtering** by provider, region, status, and tags
- **Analytics** with cost breakdowns and usage statistics
- **Export/Import** capabilities via CSV

## Installation

The inventory module is part of the capsule package:

```python
from capsule_package.inventory import (
    XNodeInventory,
    DeploymentRecord,
    CostReport,
    get_default_inventory,
    generate_cost_report
)
```

## Quick Start

### Basic Usage

```python
from capsule_package.inventory import get_default_inventory
from capsule_package.openmesh import XNode

# Initialize inventory
inventory = get_default_inventory()

# Create and add an xNode
xnode = XNode(
    id='xnode-001',
    name='prod-web-1',
    status='running',
    ip_address='192.168.1.100',
    region='us-east-1'
)

inventory.add_xnode(
    xnode=xnode,
    provider='hivelocity',
    template='web-server',
    cost_hourly=0.15,
    tags=['production', 'web']
)

# List all xNodes
all_nodes = inventory.list_all()
print(f"Total xNodes: {len(all_nodes)}")
```

### Generate Cost Report

```python
from capsule_package.inventory import generate_cost_report

# Quick cost report
print(generate_cost_report())

# Or get detailed cost data
inventory = get_default_inventory()
report = inventory.get_cost_report()
print(f"Monthly cost: ${report.total_monthly:.2f}")
print(f"Annual projection: ${report.projected_annual:.2f}")
```

## API Reference

### XNodeInventory Class

Main inventory management class.

#### Constructor

```python
inventory = XNodeInventory(inventory_file=None)
```

- `inventory_file`: Optional path to inventory JSON file (defaults to `~/.capsule/inventory.json`)

#### Adding/Removing xNodes

```python
# Add xNode
inventory.add_xnode(
    xnode: XNode,
    provider: str,
    template: str = "default",
    cost_hourly: float = 0.0,
    tags: List[str] = None
)

# Remove xNode (marks as terminated in history)
inventory.remove_xnode(xnode_id: str)

# Update xNode attributes
inventory.update_xnode(xnode_id: str, **kwargs)

# Get xNode by ID
xnode_data = inventory.get_xnode(xnode_id: str)
```

#### Listing and Filtering

```python
# List all xNodes
all_nodes = inventory.list_all()

# Filter by provider
hivelocity_nodes = inventory.list_by_provider('hivelocity')

# Filter by status
running_nodes = inventory.list_by_status('running')

# Filter by tags
prod_nodes = inventory.list_by_tags(['production'], match_all=False)

# Search by name/ID
results = inventory.search('web')
```

#### Cost Tracking

```python
# Get total costs
costs = inventory.get_total_cost()
# Returns: {'hourly': 0.50, 'daily': 12.0, 'monthly': 360.0, 'annual': 4380.0}

# Get detailed cost report
report = inventory.get_cost_report()
print(report.generate_report())  # Formatted text report
```

#### Analytics and Statistics

```python
# Get comprehensive statistics
stats = inventory.get_statistics()

# Available statistics:
# - total_xnodes
# - status_distribution
# - provider_distribution
# - region_distribution
# - total_deployments
# - active_deployments
# - average_uptime_hours
# - lifetime_cost
# - most_expensive (top 5)
# - longest_running (top 5)
```

#### Deployment History

```python
# Get all deployment history
history = inventory.get_deployment_history()

# Filter by xNode ID
xnode_history = inventory.get_deployment_history(xnode_id='xnode-001')

# Filter by provider
provider_history = inventory.get_deployment_history(provider='hivelocity')

# Limit results
recent = inventory.get_deployment_history(limit=10)

# Cleanup old terminated deployments
removed = inventory.cleanup_old_history(days=90)
```

#### Export/Import

```python
# Export to CSV
inventory.export_csv('xnodes.csv')

# Import from CSV
count = inventory.import_csv('xnodes.csv')
print(f"Imported {count} xNodes")
```

### DeploymentRecord Class

Tracks historical deployment data.

```python
@dataclass
class DeploymentRecord:
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

    def calculate_uptime() -> float
    def is_active() -> bool
```

### CostReport Class

Cost analysis and projections.

```python
@dataclass
class CostReport:
    total_hourly: float
    total_daily: float
    total_monthly: float
    projected_annual: float
    by_provider: Dict[str, float]
    by_region: Dict[str, float]
    active_count: int
    total_count: int

    def generate_report() -> str  # Formatted text report
    def to_dict() -> dict
```

## Data Storage

### Inventory File Location

Default: `~/.capsule/inventory.json`

### JSON Structure

```json
{
  "version": "1.0",
  "last_updated": "2025-10-16T12:00:00",
  "xnodes": {
    "xnode-001": {
      "id": "xnode-001",
      "name": "prod-web-1",
      "provider": "hivelocity",
      "template": "web-server",
      "status": "running",
      "ip_address": "192.168.1.100",
      "ssh_port": 22,
      "region": "us-east-1",
      "deployed_at": "2025-10-15T10:00:00",
      "cost_hourly": 0.15,
      "tags": ["production", "web"],
      "metadata": {}
    }
  },
  "history": [
    {
      "xnode_id": "xnode-001",
      "provider": "hivelocity",
      "template": "web-server",
      "deployed_at": "2025-10-15T10:00:00",
      "terminated_at": null,
      "total_cost": 0.0,
      "uptime_hours": 0.0,
      "region": "us-east-1",
      "name": "prod-web-1",
      "tags": ["production", "web"]
    }
  ],
  "metadata": {
    "total_deployed": 5,
    "total_running": 3,
    "total_lifetime_cost": 125.50
  }
}
```

### Backup System

- Automatic backup created before every modification
- Backup file: `~/.capsule/inventory.json.backup`
- Preserves previous state in case of corruption

## CSV Format

### Export Format

```csv
id,name,provider,status,ip_address,region,deployed_at,cost_hourly,tags
xnode-001,prod-web-1,hivelocity,running,192.168.1.100,us-east-1,2025-10-15T10:00:00,0.15,"production,web"
```

### Import Format

**Required columns:**
- `id`, `name`, `provider`, `status`, `ip_address`

**Optional columns:**
- `region`, `deployed_at`, `cost_hourly`, `tags`, `template`

## Examples

### Track Multi-Provider Deployment

```python
from capsule_package.inventory import get_default_inventory
from capsule_package.openmesh import XNode

inventory = get_default_inventory()

# Deploy across multiple providers
providers = [
    ('hivelocity', 'us-east-1', 0.15),
    ('aws', 'us-west-2', 0.12),
    ('gcp', 'europe-west1', 0.18),
]

for i, (provider, region, cost) in enumerate(providers):
    xnode = XNode(
        id=f'xnode-{provider}-{i}',
        name=f'{provider}-node-{i}',
        status='running',
        ip_address=f'192.168.1.{100+i}',
        region=region
    )

    inventory.add_xnode(
        xnode=xnode,
        provider=provider,
        cost_hourly=cost,
        tags=['production', provider]
    )

# Analyze by provider
stats = inventory.get_statistics()
for provider, count in stats['provider_distribution'].items():
    nodes = inventory.list_by_provider(provider)
    total_cost = sum(n.get('cost_hourly', 0) for n in nodes)
    print(f"{provider}: {count} nodes, ${total_cost:.2f}/hour")
```

### Monitor Production vs Development Costs

```python
inventory = get_default_inventory()

# Get production xNodes
prod_nodes = inventory.list_by_tags(['production'])
prod_cost = sum(n.get('cost_hourly', 0) for n in prod_nodes if n['status'] == 'running')

# Get development xNodes
dev_nodes = inventory.list_by_tags(['development'])
dev_cost = sum(n.get('cost_hourly', 0) for n in dev_nodes if n['status'] == 'running')

print(f"Production monthly cost: ${prod_cost * 24 * 30:.2f}")
print(f"Development monthly cost: ${dev_cost * 24 * 30:.2f}")
print(f"Total monthly cost: ${(prod_cost + dev_cost) * 24 * 30:.2f}")
```

### Track xNode Lifecycle

```python
# Deploy xNode
xnode = XNode(id='xnode-test', name='test-node', status='running',
              ip_address='192.168.1.200', region='us-east-1')
inventory.add_xnode(xnode, provider='hivelocity', cost_hourly=0.10,
                   tags=['testing'])

# Update status during lifecycle
inventory.update_xnode('xnode-test', status='stopped')
inventory.update_xnode('xnode-test', status='running')

# Eventually remove/terminate
inventory.remove_xnode('xnode-test')

# Check history
history = inventory.get_deployment_history(xnode_id='xnode-test')
record = history[0]
print(f"Uptime: {record.uptime_hours:.1f} hours")
print(f"Total cost: ${record.total_cost:.2f}")
```

### Generate Monthly Report

```python
from datetime import datetime

inventory = get_default_inventory()
report = inventory.get_cost_report()

print(f"""
Monthly Infrastructure Report
Generated: {datetime.now().strftime('%Y-%m-%d')}

Active xNodes: {report.active_count}
Total xNodes: {report.total_count}

Cost Breakdown:
  Hourly:  ${report.total_hourly:.2f}
  Daily:   ${report.total_daily:.2f}
  Monthly: ${report.total_monthly:.2f}
  Annual:  ${report.projected_annual:.2f}

By Provider:
""")

for provider, cost in sorted(report.by_provider.items(),
                            key=lambda x: x[1], reverse=True):
    monthly = cost * 24 * 30
    print(f"  {provider:20} ${monthly:8.2f}/month")
```

## Error Handling

The inventory system includes comprehensive error handling:

```python
from capsule_package.inventory import XNodeInventory

inventory = XNodeInventory()

# Handle duplicate additions
try:
    inventory.add_xnode(existing_xnode, provider='test')
except ValueError as e:
    print(f"XNode already exists: {e}")

# Handle missing xNodes
try:
    data = inventory.get_xnode('nonexistent-id')
except KeyError as e:
    print(f"XNode not found: {e}")

# Handle import errors
try:
    count = inventory.import_csv('missing_file.csv')
except FileNotFoundError as e:
    print(f"File not found: {e}")
```

## Best Practices

1. **Tag Consistently**: Use standardized tags for easy filtering
   ```python
   tags=['production', 'web', 'us-east-1']
   ```

2. **Regular Backups**: Export inventory periodically
   ```python
   inventory.export_csv(f'backup_{datetime.now().date()}.csv')
   ```

3. **Cost Tracking**: Always specify accurate hourly costs
   ```python
   inventory.add_xnode(xnode, provider='hivelocity', cost_hourly=0.15)
   ```

4. **Cleanup History**: Remove old terminated deployments
   ```python
   inventory.cleanup_old_history(days=90)  # Keep 90 days
   ```

5. **Monitor Status**: Update xNode status when it changes
   ```python
   inventory.update_xnode(xnode_id, status='stopped')
   ```

## Troubleshooting

### Inventory file corrupted

```python
# Restore from backup
import shutil
backup = Path.home() / '.capsule' / 'inventory.json.backup'
main = Path.home() / '.capsule' / 'inventory.json'
shutil.copy2(backup, main)
```

### Reset inventory

```python
inventory_file = Path.home() / '.capsule' / 'inventory.json'
inventory_file.unlink(missing_ok=True)
inventory = XNodeInventory()  # Fresh start
```

### Export before major changes

```python
# Always backup before bulk operations
inventory.export_csv('pre_cleanup_backup.csv')
# ... perform operations ...
```

## Integration with XNodeManager

The inventory system integrates seamlessly with the XNodeManager:

```python
from capsule_package.openmesh import XNodeManager
from capsule_package.inventory import get_default_inventory

# Deploy and track
manager = XNodeManager()
inventory = get_default_inventory()

# Deploy new xNode
xnode = manager.deploy_xnode('prod-api-1', region='us-east-1')

# Add to inventory
inventory.add_xnode(
    xnode=xnode,
    provider='openmesh',
    template='api-server',
    cost_hourly=0.20,
    tags=['production', 'api']
)

# Later: terminate and update inventory
manager.delete_xnode(xnode.id)
inventory.remove_xnode(xnode.id)
```

## Running the Demo

A comprehensive demonstration script is included:

```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/capsule
python3 examples/inventory_demo.py
```

The demo showcases:
- Adding xNodes
- Filtering and searching
- Cost tracking and reporting
- Statistics and analytics
- Deployment history
- Export/Import functionality

## Support

For issues or questions:
- Check the examples in `examples/inventory_demo.py`
- Review the module documentation in `inventory.py`
- Examine the generated `~/.capsule/inventory.json` file
