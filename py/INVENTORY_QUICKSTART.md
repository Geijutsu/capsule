# XNode Inventory - Quick Start Guide

## 30-Second Start

```python
from capsule_package.inventory import get_default_inventory
from capsule_package.openmesh import XNode

# Initialize
inventory = get_default_inventory()

# Add an xNode
xnode = XNode(id='node-1', name='web-1', status='running',
              ip_address='192.168.1.100', region='us-east-1')
inventory.add_xnode(xnode, provider='hivelocity', cost_hourly=0.15,
                   tags=['production', 'web'])

# Get cost report
print(inventory.get_cost_report().generate_report())
```

## Essential Operations

### Add xNode
```python
inventory.add_xnode(xnode, provider='hivelocity', cost_hourly=0.15)
```

### List xNodes
```python
all_nodes = inventory.list_all()
prod_nodes = inventory.list_by_tags(['production'])
running_nodes = inventory.list_by_status('running')
```

### Cost Report
```python
report = inventory.get_cost_report()
print(f"Monthly: ${report.total_monthly:.2f}")
```

### Statistics
```python
stats = inventory.get_statistics()
print(f"Total: {stats['total_xnodes']}")
```

### Export
```python
inventory.export_csv('backup.csv')
```

## CLI Usage

```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/capsule

# List all xNodes
python3 examples/inventory_cli_integration.py list

# Add xNode
python3 examples/inventory_cli_integration.py add xnode-001 prod-web-1 \
  --provider hivelocity --ip 192.168.1.100 --cost 0.15 --tags production,web

# Cost report
python3 examples/inventory_cli_integration.py report

# Statistics
python3 examples/inventory_cli_integration.py stats

# Search
python3 examples/inventory_cli_integration.py search prod

# Export
python3 examples/inventory_cli_integration.py export backup.csv
```

## Key Files

- **Module**: `/Users/joshkornreich/Documents/Projects/CLIs/capsule/capsule_package/inventory.py`
- **Demo**: `/Users/joshkornreich/Documents/Projects/CLIs/capsule/examples/inventory_demo.py`
- **CLI**: `/Users/joshkornreich/Documents/Projects/CLIs/capsule/examples/inventory_cli_integration.py`
- **Docs**: `/Users/joshkornreich/Documents/Projects/CLIs/capsule/docs/INVENTORY_SYSTEM.md`
- **Data**: `~/.capsule/inventory.json`

## Run Demo

```bash
python3 /Users/joshkornreich/Documents/Projects/CLIs/capsule/examples/inventory_demo.py
```

## API Reference (Quick)

```python
# XNodeInventory class
inventory.add_xnode(xnode, provider, template, cost_hourly, tags)
inventory.remove_xnode(xnode_id)
inventory.get_xnode(xnode_id)
inventory.update_xnode(xnode_id, **kwargs)
inventory.list_all()
inventory.list_by_provider(provider)
inventory.list_by_status(status)
inventory.list_by_tags(tags, match_all=False)
inventory.search(query)
inventory.get_total_cost()
inventory.get_cost_report()
inventory.get_statistics()
inventory.export_csv(filename)
inventory.import_csv(filename)
```

## Common Patterns

### Track New Deployment
```python
xnode = XNode(id='node-1', name='web-1', status='running',
              ip_address='10.0.0.1', region='us-east-1')
inventory.add_xnode(xnode, provider='hivelocity', cost_hourly=0.15,
                   tags=['production'])
```

### Find Production xNodes
```python
prod_nodes = inventory.list_by_tags(['production'])
for node in prod_nodes:
    print(f"{node['name']}: ${node['cost_hourly']}/hr")
```

### Calculate Monthly Costs
```python
costs = inventory.get_total_cost()
print(f"Monthly: ${costs['monthly']:.2f}")
```

### Get Provider Breakdown
```python
report = inventory.get_cost_report()
for provider, cost in report.by_provider.items():
    print(f"{provider}: ${cost * 24 * 30:.2f}/month")
```

### Export for Backup
```python
from datetime import datetime
inventory.export_csv(f"backup_{datetime.now().date()}.csv")
```

## Need More Help?

- **Full Docs**: `docs/INVENTORY_SYSTEM.md`
- **Examples**: `examples/inventory_demo.py`
- **Verification**: `INVENTORY_VERIFICATION.md`
- **Summary**: `INVENTORY_SUMMARY.md`
