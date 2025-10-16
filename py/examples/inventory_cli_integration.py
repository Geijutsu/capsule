#!/usr/bin/env python3
"""
Example CLI integration for XNode Inventory Management

This demonstrates how to integrate the inventory system into the capsule CLI
using Click commands.

Usage:
    python inventory_cli_integration.py list
    python inventory_cli_integration.py add xnode-001 --provider hivelocity --cost 0.15
    python inventory_cli_integration.py report
    python inventory_cli_integration.py stats
    python inventory_cli_integration.py export output.csv
"""

import sys
import click
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capsule_package.inventory import get_default_inventory
from capsule_package.openmesh import XNode


@click.group()
def inventory():
    """XNode inventory management commands."""
    pass


@inventory.command()
@click.option('--provider', help='Filter by provider')
@click.option('--status', help='Filter by status')
@click.option('--tags', help='Filter by tags (comma-separated)')
def list(provider, status, tags):
    """List xNodes in inventory."""
    inv = get_default_inventory()

    # Apply filters
    if provider:
        nodes = inv.list_by_provider(provider)
    elif status:
        nodes = inv.list_by_status(status)
    elif tags:
        tag_list = [t.strip() for t in tags.split(',')]
        nodes = inv.list_by_tags(tag_list)
    else:
        nodes = inv.list_all()

    if not nodes:
        click.echo("No xNodes found.")
        return

    # Display table
    click.echo("\n" + "=" * 100)
    click.echo(f"{'ID':<20} {'Name':<20} {'Provider':<15} {'Status':<10} {'Cost/hr':<10} {'Region':<15}")
    click.echo("=" * 100)

    for node in nodes:
        click.echo(
            f"{node['id']:<20} "
            f"{node['name']:<20} "
            f"{node.get('provider', 'N/A'):<15} "
            f"{node['status']:<10} "
            f"${node.get('cost_hourly', 0):<9.2f} "
            f"{node.get('region', 'N/A'):<15}"
        )

    click.echo("=" * 100)
    click.echo(f"Total: {len(nodes)} xNodes\n")


@inventory.command()
@click.argument('xnode_id')
@click.argument('name')
@click.option('--provider', required=True, help='Provider name')
@click.option('--ip', required=True, help='IP address')
@click.option('--region', default='us-east-1', help='Deployment region')
@click.option('--cost', type=float, default=0.0, help='Hourly cost')
@click.option('--template', default='default', help='Configuration template')
@click.option('--tags', help='Tags (comma-separated)')
def add(xnode_id, name, provider, ip, region, cost, template, tags):
    """Add xNode to inventory."""
    inv = get_default_inventory()

    # Parse tags
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(',')]

    # Create XNode
    xnode = XNode(
        id=xnode_id,
        name=name,
        status='running',
        ip_address=ip,
        region=region
    )

    try:
        inv.add_xnode(
            xnode=xnode,
            provider=provider,
            template=template,
            cost_hourly=cost,
            tags=tag_list
        )
        click.echo(f"✓ Added xNode: {name} ({xnode_id})")
        click.echo(f"  Provider: {provider}")
        click.echo(f"  Region: {region}")
        click.echo(f"  Cost: ${cost:.2f}/hour")
        if tag_list:
            click.echo(f"  Tags: {', '.join(tag_list)}")
    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@inventory.command()
@click.argument('xnode_id')
def remove(xnode_id):
    """Remove xNode from inventory."""
    inv = get_default_inventory()

    try:
        # Get xNode info before removal
        xnode = inv.get_xnode(xnode_id)
        name = xnode['name']

        # Confirm removal
        if not click.confirm(f"Remove xNode '{name}' ({xnode_id})?"):
            click.echo("Cancelled.")
            return

        inv.remove_xnode(xnode_id)
        click.echo(f"✓ Removed xNode: {name} ({xnode_id})")

    except KeyError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@inventory.command()
@click.argument('xnode_id')
def info(xnode_id):
    """Show detailed xNode information."""
    inv = get_default_inventory()

    try:
        xnode = inv.get_xnode(xnode_id)

        click.echo("\n" + "=" * 60)
        click.echo(f"XNODE DETAILS: {xnode['name']}")
        click.echo("=" * 60)
        click.echo(f"ID:           {xnode['id']}")
        click.echo(f"Name:         {xnode['name']}")
        click.echo(f"Provider:     {xnode.get('provider', 'N/A')}")
        click.echo(f"Template:     {xnode.get('template', 'N/A')}")
        click.echo(f"Status:       {xnode['status']}")
        click.echo(f"IP Address:   {xnode['ip_address']}")
        click.echo(f"SSH Port:     {xnode.get('ssh_port', 22)}")
        click.echo(f"Region:       {xnode.get('region', 'N/A')}")
        click.echo(f"Deployed:     {xnode.get('deployed_at', 'N/A')}")
        click.echo(f"Cost/hour:    ${xnode.get('cost_hourly', 0):.2f}")

        if xnode.get('tags'):
            click.echo(f"Tags:         {', '.join(xnode['tags'])}")

        # Calculate costs
        hourly = xnode.get('cost_hourly', 0)
        click.echo(f"\nCost Projections:")
        click.echo(f"  Daily:      ${hourly * 24:.2f}")
        click.echo(f"  Monthly:    ${hourly * 24 * 30:.2f}")
        click.echo(f"  Annual:     ${hourly * 24 * 365:.2f}")

        # Get deployment history
        history = inv.get_deployment_history(xnode_id=xnode_id)
        if history:
            record = history[0]
            uptime = record.calculate_uptime()
            click.echo(f"\nDeployment Info:")
            click.echo(f"  Uptime:     {uptime:.1f} hours ({uptime/24:.1f} days)")
            if not record.is_active():
                click.echo(f"  Total Cost: ${record.total_cost:.2f}")

        click.echo("=" * 60 + "\n")

    except KeyError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@inventory.command()
def report():
    """Generate cost report."""
    inv = get_default_inventory()
    report = inv.get_cost_report()
    click.echo("\n" + report.generate_report())


@inventory.command()
def stats():
    """Show inventory statistics."""
    inv = get_default_inventory()
    stats = inv.get_statistics()

    click.echo("\n" + "=" * 60)
    click.echo("INVENTORY STATISTICS")
    click.echo("=" * 60)

    click.echo(f"\nOverview:")
    click.echo(f"  Total xNodes:        {stats['total_xnodes']}")
    click.echo(f"  Total Deployments:   {stats['total_deployments']}")
    click.echo(f"  Active Deployments:  {stats['active_deployments']}")
    click.echo(f"  Lifetime Cost:       ${stats['lifetime_cost']:.2f}")

    if stats['status_distribution']:
        click.echo(f"\nStatus Distribution:")
        for status, count in stats['status_distribution'].items():
            click.echo(f"  {status:<15} {count:>5}")

    if stats['provider_distribution']:
        click.echo(f"\nProvider Distribution:")
        for provider, count in stats['provider_distribution'].items():
            click.echo(f"  {provider:<15} {count:>5}")

    if stats['region_distribution']:
        click.echo(f"\nRegion Distribution:")
        for region, count in stats['region_distribution'].items():
            click.echo(f"  {region:<15} {count:>5}")

    if stats['most_expensive']:
        click.echo(f"\nMost Expensive xNodes:")
        for node in stats['most_expensive']:
            click.echo(f"  {node['name']:<20} ${node['cost_hourly']:.2f}/hour")

    if stats['longest_running']:
        click.echo(f"\nLongest Running xNodes:")
        for node in stats['longest_running']:
            click.echo(f"  {node['name']:<20} {node['uptime_days']:.1f} days")

    click.echo("=" * 60 + "\n")


@inventory.command()
@click.argument('filename')
def export(filename):
    """Export inventory to CSV."""
    inv = get_default_inventory()

    try:
        inv.export_csv(filename)
        count = len(inv.list_all())
        click.echo(f"✓ Exported {count} xNodes to {filename}")
    except Exception as e:
        click.echo(f"❌ Export failed: {e}", err=True)
        sys.exit(1)


@inventory.command()
@click.argument('filename')
def import_csv(filename):
    """Import xNodes from CSV."""
    inv = get_default_inventory()

    try:
        count = inv.import_csv(filename)
        click.echo(f"✓ Imported {count} xNodes from {filename}")
    except FileNotFoundError:
        click.echo(f"❌ File not found: {filename}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Import failed: {e}", err=True)
        sys.exit(1)


@inventory.command()
@click.argument('xnode_id')
@click.option('--status', help='Update status')
@click.option('--cost', type=float, help='Update hourly cost')
@click.option('--tags', help='Update tags (comma-separated)')
def update(xnode_id, status, cost, tags):
    """Update xNode attributes."""
    inv = get_default_inventory()

    try:
        # Build update dict
        updates = {}
        if status:
            updates['status'] = status
        if cost is not None:
            updates['cost_hourly'] = cost
        if tags:
            updates['tags'] = [t.strip() for t in tags.split(',')]

        if not updates:
            click.echo("No updates specified. Use --status, --cost, or --tags.")
            return

        inv.update_xnode(xnode_id, **updates)
        click.echo(f"✓ Updated xNode: {xnode_id}")

        for key, value in updates.items():
            click.echo(f"  {key}: {value}")

    except KeyError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@inventory.command()
@click.argument('query')
def search(query):
    """Search xNodes by name or ID."""
    inv = get_default_inventory()
    results = inv.search(query)

    if not results:
        click.echo(f"No xNodes found matching '{query}'")
        return

    click.echo(f"\nSearch results for '{query}':\n")
    click.echo("=" * 80)
    click.echo(f"{'ID':<20} {'Name':<20} {'Provider':<15} {'Status':<10}")
    click.echo("=" * 80)

    for node in results:
        click.echo(
            f"{node['id']:<20} "
            f"{node['name']:<20} "
            f"{node.get('provider', 'N/A'):<15} "
            f"{node['status']:<10}"
        )

    click.echo("=" * 80)
    click.echo(f"Found {len(results)} matches\n")


@inventory.command()
@click.option('--days', type=int, default=90, help='Days to retain history')
def cleanup(days):
    """Cleanup old deployment history."""
    inv = get_default_inventory()

    if not click.confirm(f"Remove terminated deployments older than {days} days?"):
        click.echo("Cancelled.")
        return

    removed = inv.cleanup_old_history(days)
    click.echo(f"✓ Removed {removed} old deployment records")


if __name__ == '__main__':
    inventory()
