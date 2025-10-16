#!/usr/bin/env python3
"""
Demonstration of XNode Inventory Management System

This script shows how to use the inventory management system for tracking
deployed xNodes, managing costs, and generating reports.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from capsule_package.inventory import (
    XNodeInventory,
    DeploymentRecord,
    CostReport,
    get_default_inventory,
    generate_cost_report
)
from capsule_package.openmesh import XNode


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def demo_basic_operations():
    """Demonstrate basic inventory operations."""
    print("\n" + "=" * 60)
    print("DEMO: Basic Inventory Operations")
    print("=" * 60 + "\n")

    # Initialize inventory
    inventory = XNodeInventory()

    # Create and add sample xNodes
    xnodes_data = [
        {
            'id': 'xnode-prod-web-1',
            'name': 'prod-web-1',
            'provider': 'hivelocity',
            'template': 'web-server',
            'cost_hourly': 0.15,
            'region': 'us-east-1',
            'tags': ['production', 'web']
        },
        {
            'id': 'xnode-prod-db-1',
            'name': 'prod-db-1',
            'provider': 'hivelocity',
            'template': 'database',
            'cost_hourly': 0.25,
            'region': 'us-east-1',
            'tags': ['production', 'database']
        },
        {
            'id': 'xnode-dev-test-1',
            'name': 'dev-test-1',
            'provider': 'aws',
            'template': 'development',
            'cost_hourly': 0.10,
            'region': 'us-west-2',
            'tags': ['development', 'testing']
        },
    ]

    for data in xnodes_data:
        try:
            xnode = XNode(
                id=data['id'],
                name=data['name'],
                status='running',
                ip_address=f"192.168.1.{xnodes_data.index(data) + 100}",
                region=data['region']
            )

            inventory.add_xnode(
                xnode=xnode,
                provider=data['provider'],
                template=data['template'],
                cost_hourly=data['cost_hourly'],
                tags=data['tags']
            )
            print(f"✓ Added: {xnode.name} ({xnode.id})")
        except ValueError as e:
            print(f"⚠ Skipped (already exists): {data['id']}")

    # List all xNodes
    print(f"\nTotal xNodes in inventory: {len(inventory.list_all())}")

    return inventory


def demo_filtering():
    """Demonstrate filtering and search capabilities."""
    print("\n" + "=" * 60)
    print("DEMO: Filtering and Search")
    print("=" * 60 + "\n")

    inventory = get_default_inventory()

    # Filter by provider
    print("xNodes on Hivelocity:")
    hivelocity_nodes = inventory.list_by_provider('hivelocity')
    for node in hivelocity_nodes:
        print(f"  - {node['name']} ({node['id']})")

    # Filter by status
    print("\nRunning xNodes:")
    running_nodes = inventory.list_by_status('running')
    for node in running_nodes:
        print(f"  - {node['name']} - {node['provider']}")

    # Filter by tags
    print("\nProduction xNodes:")
    prod_nodes = inventory.list_by_tags(['production'])
    for node in prod_nodes:
        print(f"  - {node['name']} - {', '.join(node.get('tags', []))}")

    # Search by name
    print("\nSearch for 'prod':")
    search_results = inventory.search('prod')
    for node in search_results:
        print(f"  - {node['name']} ({node['id']})")


def demo_cost_tracking():
    """Demonstrate cost tracking and reporting."""
    print("\n" + "=" * 60)
    print("DEMO: Cost Tracking and Reporting")
    print("=" * 60 + "\n")

    inventory = get_default_inventory()

    # Get total costs
    costs = inventory.get_total_cost()
    print("Cost Overview:")
    print(f"  Hourly:   ${costs['hourly']:.2f}")
    print(f"  Daily:    ${costs['daily']:.2f}")
    print(f"  Monthly:  ${costs['monthly']:.2f}")
    print(f"  Annual:   ${costs['annual']:.2f}")

    # Generate detailed cost report
    print("\n" + generate_cost_report())


def demo_statistics():
    """Demonstrate statistics and analytics."""
    print("\n" + "=" * 60)
    print("DEMO: Statistics and Analytics")
    print("=" * 60 + "\n")

    inventory = get_default_inventory()
    stats = inventory.get_statistics()

    print("Inventory Statistics:")
    print(f"  Total xNodes: {stats['total_xnodes']}")
    print(f"  Total Deployments: {stats['total_deployments']}")
    print(f"  Active Deployments: {stats['active_deployments']}")

    print("\nStatus Distribution:")
    for status, count in stats['status_distribution'].items():
        print(f"  {status}: {count}")

    print("\nProvider Distribution:")
    for provider, count in stats['provider_distribution'].items():
        print(f"  {provider}: {count}")

    if stats['most_expensive']:
        print("\nMost Expensive xNodes:")
        for node in stats['most_expensive']:
            print(f"  {node['name']}: ${node['cost_hourly']:.2f}/hour")

    if stats['longest_running']:
        print("\nLongest Running xNodes:")
        for node in stats['longest_running']:
            days = node['uptime_days']
            print(f"  {node['name']}: {days:.1f} days")


def demo_export_import():
    """Demonstrate CSV export/import."""
    print("\n" + "=" * 60)
    print("DEMO: Export/Import")
    print("=" * 60 + "\n")

    inventory = get_default_inventory()

    # Export to CSV
    export_file = "/tmp/xnode_inventory_export.csv"
    inventory.export_csv(export_file)
    print(f"✓ Exported inventory to {export_file}")

    # Show file contents
    with open(export_file, 'r') as f:
        lines = f.readlines()
        print(f"\nCSV Preview (first 5 lines):")
        for line in lines[:5]:
            print(f"  {line.rstrip()}")


def demo_deployment_history():
    """Demonstrate deployment history tracking."""
    print("\n" + "=" * 60)
    print("DEMO: Deployment History")
    print("=" * 60 + "\n")

    inventory = get_default_inventory()

    # Get all deployment history
    history = inventory.get_deployment_history(limit=10)

    print(f"Recent Deployments (last {len(history)}):")
    for record in history:
        uptime = record.calculate_uptime()
        status = "Active" if record.is_active() else "Terminated"
        print(f"\n  {record.name} ({record.xnode_id})")
        print(f"    Provider: {record.provider}")
        print(f"    Template: {record.template}")
        print(f"    Deployed: {record.deployed_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"    Uptime: {uptime:.1f} hours ({uptime/24:.1f} days)")
        print(f"    Status: {status}")
        if not record.is_active():
            print(f"    Total Cost: ${record.total_cost:.2f}")


def demo_update_operations():
    """Demonstrate update and removal operations."""
    print("\n" + "=" * 60)
    print("DEMO: Update and Removal Operations")
    print("=" * 60 + "\n")

    inventory = get_default_inventory()

    # Update xNode status
    test_nodes = inventory.search('dev')
    if test_nodes:
        node_id = test_nodes[0]['id']
        print(f"Updating status of {node_id}...")

        inventory.update_xnode(node_id, status='stopped')
        print(f"✓ Status updated to 'stopped'")

        updated_node = inventory.get_xnode(node_id)
        print(f"  Current status: {updated_node['status']}")

        # Update back to running
        inventory.update_xnode(node_id, status='running')
        print(f"✓ Status updated back to 'running'")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 60)
    print("XNODE INVENTORY MANAGEMENT SYSTEM - DEMONSTRATION")
    print("=" * 60)

    try:
        # Run demonstrations
        demo_basic_operations()
        demo_filtering()
        demo_cost_tracking()
        demo_statistics()
        demo_deployment_history()
        demo_update_operations()
        demo_export_import()

        print("\n" + "=" * 60)
        print("DEMONSTRATION COMPLETE")
        print("=" * 60 + "\n")

        print("Inventory file location:")
        inventory = get_default_inventory()
        print(f"  {inventory.inventory_file}")

    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
