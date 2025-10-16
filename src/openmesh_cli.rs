use anyhow::Result;
use colored::Colorize;
use prettytable::{Table, Row, Cell, format};

use crate::inventory::XNodeInventory;
use crate::ui::{header, success};

pub fn list_inventory(provider: Option<String>, status: Option<String>) -> Result<()> {
    let inventory = XNodeInventory::new(None)?;

    let entries = if let Some(prov) = provider {
        inventory.list_by_provider(&prov)
    } else if let Some(stat) = status {
        inventory.list_by_status(&stat)
    } else {
        inventory.list_all()
    };

    if entries.is_empty() {
        println!("No xNodes found in inventory");
        return Ok(());
    }

    let mut table = Table::new();
    table.set_format(*format::consts::FORMAT_BOX_CHARS);

    table.set_titles(Row::new(vec![
        Cell::new("ID").style_spec("Fc"),
        Cell::new("Name").style_spec("Fc"),
        Cell::new("Provider").style_spec("Fc"),
        Cell::new("Status").style_spec("Fc"),
        Cell::new("IP Address").style_spec("Fc"),
        Cell::new("Region").style_spec("Fc"),
        Cell::new("Cost/Hour").style_spec("Fc"),
    ]));

    for entry in &entries {
        let status_colored = match entry.status.as_str() {
            "running" => entry.status.green().to_string(),
            "stopped" => entry.status.yellow().to_string(),
            "deploying" => entry.status.cyan().to_string(),
            "error" => entry.status.red().to_string(),
            _ => entry.status.white().to_string(),
        };

        table.add_row(Row::new(vec![
            Cell::new(&entry.id),
            Cell::new(&entry.name),
            Cell::new(&entry.provider),
            Cell::new(&status_colored),
            Cell::new(&entry.ip_address),
            Cell::new(entry.region.as_deref().unwrap_or("-")),
            Cell::new(&format!("${:.2}", entry.cost_hourly)),
        ]));
    }

    header("XNODE INVENTORY");
    table.printstd();
    println!("\nTotal xNodes: {}", entries.len());

    Ok(())
}

pub fn show_cost_report() -> Result<()> {
    let inventory = XNodeInventory::new(None)?;
    let report = inventory.get_cost_report();

    println!("\n{}", report.generate_report());

    Ok(())
}

pub fn list_xnodes(status: Option<String>, provider: Option<String>) -> Result<()> {
    list_inventory(provider, status)
}

pub fn show_statistics() -> Result<()> {
    let inventory = XNodeInventory::new(None)?;
    let stats = inventory.get_statistics();

    header("INVENTORY STATISTICS");

    println!("\n{}", "SUMMARY".cyan().bold());
    println!("  Total xNodes: {}", stats.total_xnodes);
    println!("  Active Deployments: {}", stats.active_deployments);
    println!("  Terminated Deployments: {}", stats.terminated_deployments);
    println!("  Lifetime Cost: ${:.2}", stats.lifetime_cost);
    println!("  Average Uptime: {:.1} hours", stats.average_uptime_hours);

    if !stats.status_distribution.is_empty() {
        println!("\n{}", "STATUS DISTRIBUTION".cyan().bold());
        for (status, count) in &stats.status_distribution {
            println!("  {}: {}", status, count);
        }
    }

    if !stats.provider_distribution.is_empty() {
        println!("\n{}", "PROVIDER DISTRIBUTION".cyan().bold());
        for (provider, count) in &stats.provider_distribution {
            println!("  {}: {}", provider, count);
        }
    }

    if !stats.region_distribution.is_empty() {
        println!("\n{}", "REGION DISTRIBUTION".cyan().bold());
        for (region, count) in &stats.region_distribution {
            println!("  {}: {}", region, count);
        }
    }

    if !stats.most_expensive.is_empty() {
        println!("\n{}", "MOST EXPENSIVE XNODES".cyan().bold());
        for xnode in &stats.most_expensive {
            println!("  {} ({}): ${:.2}/hour", xnode.name, xnode.id, xnode.cost_hourly);
        }
    }

    if !stats.longest_running.is_empty() {
        println!("\n{}", "LONGEST RUNNING XNODES".cyan().bold());
        for xnode in &stats.longest_running {
            println!(
                "  {} ({}): {:.1} hours ({:.1} days)",
                xnode.name, xnode.id, xnode.uptime_hours, xnode.uptime_days
            );
        }
    }

    Ok(())
}

pub fn export_inventory(filename: &str) -> Result<()> {
    let inventory = XNodeInventory::new(None)?;
    inventory.export_csv(filename)?;
    success(&format!("Exported inventory to {}", filename));
    Ok(())
}

pub fn import_inventory(filename: &str) -> Result<()> {
    let mut inventory = XNodeInventory::new(None)?;
    let count = inventory.import_csv(filename)?;
    success(&format!("Imported {} xNodes from {}", count, filename));
    Ok(())
}

pub fn show_deployment_history(
    xnode_id: Option<String>,
    provider: Option<String>,
    limit: Option<usize>,
) -> Result<()> {
    let inventory = XNodeInventory::new(None)?;
    let records = inventory.get_deployment_history(
        xnode_id.as_deref(),
        provider.as_deref(),
        limit,
    );

    if records.is_empty() {
        println!("No deployment history found");
        return Ok(());
    }

    let mut table = Table::new();
    table.set_format(*format::consts::FORMAT_BOX_CHARS);

    table.set_titles(Row::new(vec![
        Cell::new("XNode ID").style_spec("Fc"),
        Cell::new("Name").style_spec("Fc"),
        Cell::new("Provider").style_spec("Fc"),
        Cell::new("Deployed At").style_spec("Fc"),
        Cell::new("Uptime (hrs)").style_spec("Fc"),
        Cell::new("Total Cost").style_spec("Fc"),
        Cell::new("Status").style_spec("Fc"),
    ]));

    for record in &records {
        let status = if record.is_active() {
            "Active".green().to_string()
        } else {
            "Terminated".yellow().to_string()
        };

        let uptime = if record.uptime_hours > 0.0 {
            format!("{:.1}", record.uptime_hours)
        } else {
            format!("{:.1}", record.calculate_uptime())
        };

        table.add_row(Row::new(vec![
            Cell::new(&record.xnode_id),
            Cell::new(record.name.as_deref().unwrap_or("-")),
            Cell::new(&record.provider),
            Cell::new(&record.deployed_at.format("%Y-%m-%d %H:%M").to_string()),
            Cell::new(&uptime),
            Cell::new(&format!("${:.2}", record.total_cost)),
            Cell::new(&status),
        ]));
    }

    header("DEPLOYMENT HISTORY");
    table.printstd();
    println!("\nTotal records: {}", records.len());

    Ok(())
}

pub fn cleanup_history(days: u64) -> Result<()> {
    let mut inventory = XNodeInventory::new(None)?;
    let removed = inventory.cleanup_old_history(days)?;
    success(&format!(
        "Cleaned up {} old deployment record(s) older than {} days",
        removed, days
    ));
    Ok(())
}
