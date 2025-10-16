use anyhow::Result;
use colored::Colorize;
use prettytable::{Cell, Row, Table};
use std::time::Duration;

use super::{MonitoringSystem, alerts::{AlertSeverity, Alert}, health::HealthStatus};

pub async fn show_dashboard(system: &MonitoringSystem) -> Result<()> {
    let data = system.get_dashboard_data();

    println!("\n{}", "MONITORING DASHBOARD".cyan().bold());
    println!("{}", "=".repeat(60));

    // Summary section
    println!("\n{}", "OVERVIEW".white().bold());
    println!("  Total xNodes:     {}", data.total_xnodes.to_string().cyan());
    println!(
        "  Healthy:          {}",
        data.healthy_xnodes.to_string().green()
    );
    println!(
        "  Unhealthy:        {}",
        data.unhealthy_xnodes.to_string().red()
    );
    println!(
        "  Critical Alerts:  {}",
        if data.critical_alerts > 0 {
            data.critical_alerts.to_string().red().bold()
        } else {
            data.critical_alerts.to_string().green()
        }
    );
    println!(
        "  Warning Alerts:   {}",
        if data.warning_alerts > 0 {
            data.warning_alerts.to_string().yellow()
        } else {
            data.warning_alerts.to_string().green()
        }
    );

    // Recent health checks
    if !data.recent_checks.is_empty() {
        println!("\n{}", "RECENT HEALTH CHECKS".white().bold());
        let mut table = Table::new();
        table.add_row(Row::new(vec![
            Cell::new("xNode ID"),
            Cell::new("Status"),
            Cell::new("Ping"),
            Cell::new("SSH"),
            Cell::new("HTTP"),
            Cell::new("Timestamp"),
        ]));

        for (xnode_id, check) in data.recent_checks.iter() {
            let status_str = match check.status {
                HealthStatus::Healthy => "HEALTHY".green(),
                HealthStatus::Degraded => "DEGRADED".yellow(),
                HealthStatus::Unhealthy => "UNHEALTHY".red(),
                HealthStatus::Unknown => "UNKNOWN".white(),
            };

            let ping_str = check_status_to_str(check.checks.get("ping").copied());
            let ssh_str = check_status_to_str(check.checks.get("ssh").copied());
            let http_str = check_status_to_str(check.checks.get("http").copied());

            table.add_row(Row::new(vec![
                Cell::new(xnode_id),
                Cell::new(&status_str.to_string()),
                Cell::new(&ping_str),
                Cell::new(&ssh_str),
                Cell::new(&http_str),
                Cell::new(&format_timestamp(&check.timestamp)),
            ]));
        }

        table.printstd();
    }

    // Active alerts
    if !data.active_alerts.is_empty() {
        println!("\n{}", "ACTIVE ALERTS".white().bold());
        for alert in &data.active_alerts {
            print_alert(alert);
        }
    }

    println!();
    Ok(())
}

pub async fn show_health_check(system: &mut MonitoringSystem, xnode_id: &str) -> Result<()> {
    println!("\n{} {}", "Checking health for xNode:".white().bold(), xnode_id.cyan());

    // For demonstration, using placeholder values
    // In real implementation, this would fetch from xnode database
    let health_check = system
        .check_health(
            xnode_id.to_string(),
            Some("192.168.1.100"),
            false,
        )
        .await;

    println!("\n{}", "HEALTH CHECK RESULTS".white().bold());
    println!("{}", "=".repeat(60));

    let status_str = match health_check.status {
        HealthStatus::Healthy => "HEALTHY".green().bold(),
        HealthStatus::Degraded => "DEGRADED".yellow().bold(),
        HealthStatus::Unhealthy => "UNHEALTHY".red().bold(),
        HealthStatus::Unknown => "UNKNOWN".white(),
    };
    println!("  Status: {}", status_str);
    println!("  Timestamp: {}", format_timestamp(&health_check.timestamp));

    println!("\n{}", "CHECKS".white().bold());
    for (check_name, passed) in &health_check.checks {
        let status = if *passed {
            "PASS".green()
        } else {
            "FAIL".red()
        };
        let response_time = health_check
            .response_times
            .get(check_name)
            .map(|ms| format!(" ({:.0}ms)", ms))
            .unwrap_or_default();
        println!("  {} {}{}", status, check_name, response_time);
    }

    if !health_check.error_messages.is_empty() {
        println!("\n{}", "ERRORS".red().bold());
        for error in &health_check.error_messages {
            println!("  ! {}", error.red());
        }
    }

    system.save_history().await?;
    println!();
    Ok(())
}

pub async fn show_metrics(system: &mut MonitoringSystem, xnode_id: &str) -> Result<()> {
    println!("\n{} {}", "Collecting metrics for xNode:".white().bold(), xnode_id.cyan());

    // For demonstration, using placeholder values
    let metrics = system
        .collect_metrics(
            xnode_id.to_string(),
            Some("192.168.1.100"),
            None,
        )
        .await;

    if let Some(metrics) = metrics {
        println!("\n{}", "RESOURCE METRICS".white().bold());
        println!("{}", "=".repeat(60));

        println!("  Timestamp: {}", format_timestamp(&metrics.timestamp));
        println!("\n{}", "CPU".white().bold());
        println!("  Usage: {:.1}%", metrics.cpu_percent);
        print_usage_bar(metrics.cpu_percent, 75.0, 90.0);

        println!("\n{}", "MEMORY".white().bold());
        println!("  Usage: {:.1}%", metrics.memory_percent);
        print_usage_bar(metrics.memory_percent, 80.0, 95.0);

        println!("\n{}", "DISK".white().bold());
        println!("  Usage: {:.1}%", metrics.disk_percent);
        print_usage_bar(metrics.disk_percent, 85.0, 95.0);

        println!("\n{}", "LOAD AVERAGE".white().bold());
        println!(
            "  1min: {:.2}  5min: {:.2}  15min: {:.2}",
            metrics.load_average.0, metrics.load_average.1, metrics.load_average.2
        );

        system.save_history().await?;
    } else {
        println!("{}", "  Failed to collect metrics".red());
    }

    println!();
    Ok(())
}

pub async fn list_alerts(system: &MonitoringSystem) -> Result<()> {
    println!("\n{}", "ACTIVE ALERTS".cyan().bold());
    println!("{}", "=".repeat(60));

    let active_alerts: Vec<_> = system
        .get_dashboard_data()
        .active_alerts
        .into_iter()
        .filter(|a| !a.resolved)
        .collect();

    if active_alerts.is_empty() {
        println!("{}", "  No active alerts".green());
    } else {
        let mut critical = Vec::new();
        let mut warning = Vec::new();
        let mut info = Vec::new();

        for alert in active_alerts {
            match alert.severity {
                AlertSeverity::Critical => critical.push(alert),
                AlertSeverity::Warning => warning.push(alert),
                AlertSeverity::Info => info.push(alert),
            }
        }

        if !critical.is_empty() {
            println!("\n{}", "CRITICAL".red().bold());
            for alert in critical {
                print_alert(&alert);
            }
        }

        if !warning.is_empty() {
            println!("\n{}", "WARNING".yellow().bold());
            for alert in warning {
                print_alert(&alert);
            }
        }

        if !info.is_empty() {
            println!("\n{}", "INFO".blue().bold());
            for alert in info {
                print_alert(&alert);
            }
        }
    }

    println!();
    Ok(())
}

pub async fn acknowledge_alert(system: &mut MonitoringSystem, alert_id: &str) -> Result<()> {
    if system.acknowledge_alert(alert_id) {
        system.save_history().await?;
        println!("{}", format!("Alert {} acknowledged", alert_id).green());
    } else {
        println!("{}", format!("Alert {} not found", alert_id).red());
    }
    Ok(())
}

pub async fn resolve_alert(system: &mut MonitoringSystem, alert_id: &str) -> Result<()> {
    if system.resolve_alert(alert_id) {
        system.save_history().await?;
        println!("{}", format!("Alert {} resolved", alert_id).green());
    } else {
        println!("{}", format!("Alert {} not found", alert_id).red());
    }
    Ok(())
}

pub async fn show_config(system: &MonitoringSystem) -> Result<()> {
    let config = system.get_config();

    println!("\n{}", "MONITORING CONFIGURATION".cyan().bold());
    println!("{}", "=".repeat(60));

    println!("\n{}", "GENERAL".white().bold());
    println!("  Enabled: {}", config.enabled);
    println!("  Check Interval: {}s", config.check_interval_seconds);

    println!("\n{}", "TIMEOUTS".white().bold());
    println!("  Ping: {}s", config.ping_timeout);
    println!("  SSH: {}s", config.ssh_timeout);
    println!("  HTTP: {}s", config.http_timeout);

    println!("\n{}", "ALERT THRESHOLDS".white().bold());
    println!("  CPU Warning: {:.0}%", config.cpu_warning_threshold);
    println!("  CPU Critical: {:.0}%", config.cpu_critical_threshold);
    println!("  Memory Warning: {:.0}%", config.memory_warning_threshold);
    println!("  Memory Critical: {:.0}%", config.memory_critical_threshold);
    println!("  Disk Warning: {:.0}%", config.disk_warning_threshold);
    println!("  Disk Critical: {:.0}%", config.disk_critical_threshold);

    println!("\n{}", "ALERT DELIVERY".white().bold());
    println!("  Console: {}", config.alert_delivery.console_alerts);
    println!("  Email: {}", config.alert_delivery.email_alerts);
    println!("  Webhook: {}", config.alert_delivery.webhook_alerts);
    println!("  Slack: {}", config.alert_delivery.slack_alerts);

    println!("\n{}", "AUTO-REMEDIATION".white().bold());
    println!("  Auto Restart on Failure: {}", config.auto_restart_on_failure);
    println!("  Auto Scale on High Load: {}", config.auto_scale_on_high_load);

    println!();
    Ok(())
}

pub async fn watch_dashboard(system: &mut MonitoringSystem) -> Result<()> {
    println!("{}", "Starting live dashboard (Press Ctrl+C to exit)...".cyan());

    let mut interval = tokio::time::interval(Duration::from_secs(5));

    loop {
        // Clear screen (ANSI escape code)
        print!("\x1B[2J\x1B[1;1H");

        show_dashboard(system).await?;

        println!("{}", "Refreshing in 5 seconds...".white().italic());

        interval.tick().await;
    }
}

// Helper functions

fn check_status_to_str(status: Option<bool>) -> String {
    match status {
        Some(true) => "OK".green().to_string(),
        Some(false) => "FAIL".red().to_string(),
        None => "N/A".white().to_string(),
    }
}

fn format_timestamp(timestamp: &str) -> String {
    if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(timestamp) {
        dt.format("%Y-%m-%d %H:%M:%S").to_string()
    } else {
        timestamp.to_string()
    }
}

fn print_alert(alert: &Alert) {
    let severity_badge = match alert.severity {
        AlertSeverity::Critical => "[CRITICAL]".red().bold(),
        AlertSeverity::Warning => "[WARNING]".yellow(),
        AlertSeverity::Info => "[INFO]".blue(),
    };

    let ack_badge = if alert.acknowledged {
        " [ACK]".white()
    } else {
        "".white()
    };

    println!(
        "  {} {} {}{}",
        severity_badge,
        alert.xnode_id.cyan(),
        alert.message.white(),
        ack_badge
    );
    println!("    ID: {} | {}", alert.id.white().italic(), format_timestamp(&alert.timestamp));
}

fn print_usage_bar(usage: f64, warning_threshold: f64, critical_threshold: f64) {
    let bar_width = 40;
    let filled = ((usage / 100.0) * bar_width as f64) as usize;
    let empty = bar_width - filled;

    let bar_color = if usage >= critical_threshold {
        "red"
    } else if usage >= warning_threshold {
        "yellow"
    } else {
        "green"
    };

    let bar = match bar_color {
        "red" => format!("{}{}", "=".repeat(filled).red(), " ".repeat(empty)),
        "yellow" => format!("{}{}", "=".repeat(filled).yellow(), " ".repeat(empty)),
        _ => format!("{}{}", "=".repeat(filled).green(), " ".repeat(empty)),
    };

    println!("  [{}]", bar);
}
