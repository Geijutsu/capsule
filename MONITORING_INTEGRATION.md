# Monitoring System Integration Guide

This guide explains how to integrate the monitoring system into the Capsule CLI.

## Quick Start

The monitoring system is already built and ready to use. To integrate it into the main Capsule CLI:

### 1. Add Monitoring Commands to CLI

Edit `src/main.rs` and add monitoring commands to the `OpenMeshCommands` enum:

```rust
#[derive(Subcommand)]
enum OpenMeshCommands {
    // ... existing commands ...

    /// xNode monitoring and alerting
    Monitor {
        #[command(subcommand)]
        command: MonitorCommands,
    },
}

#[derive(Subcommand)]
enum MonitorCommands {
    /// Show monitoring dashboard
    Status,

    /// Check health of an xNode
    Health {
        /// xNode ID
        xnode_id: String,
    },

    /// Collect resource metrics
    Metrics {
        /// xNode ID
        xnode_id: String,
    },

    /// List active alerts
    Alerts,

    /// Acknowledge an alert
    Ack {
        /// Alert ID
        alert_id: String,
    },

    /// Resolve an alert
    Resolve {
        /// Alert ID
        alert_id: String,
    },

    /// Show monitoring configuration
    Config,

    /// Live dashboard (auto-refresh)
    Watch,
}
```

### 2. Add Command Handler

In the same file, handle the monitor commands:

```rust
#[tokio::main]
async fn main() -> Result<()> {
    // ... existing code ...
}

async fn handle_openmesh_command(command: OpenMeshCommands) -> Result<()> {
    match command {
        // ... existing handlers ...
        OpenMeshCommands::Monitor { command } => {
            handle_monitor_command(command).await?;
        }
    }
    Ok(())
}

async fn handle_monitor_command(command: MonitorCommands) -> Result<()> {
    use capsule::monitoring::{MonitoringSystem, commands};

    let mut system = MonitoringSystem::new(None).await?;

    match command {
        MonitorCommands::Status => {
            commands::show_dashboard(&system).await?;
        }
        MonitorCommands::Health { xnode_id } => {
            commands::show_health_check(&mut system, &xnode_id).await?;
        }
        MonitorCommands::Metrics { xnode_id } => {
            commands::show_metrics(&mut system, &xnode_id).await?;
        }
        MonitorCommands::Alerts => {
            commands::list_alerts(&system).await?;
        }
        MonitorCommands::Ack { alert_id } => {
            commands::acknowledge_alert(&mut system, &alert_id).await?;
        }
        MonitorCommands::Resolve { alert_id } => {
            commands::resolve_alert(&mut system, &alert_id).await?;
        }
        MonitorCommands::Config => {
            commands::show_config(&system).await?;
        }
        MonitorCommands::Watch => {
            commands::watch_dashboard(&mut system).await?;
        }
    }

    Ok(())
}
```

### 3. Update main() to async

If your main function is not already async, you need to update it:

```rust
#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        // ... existing handlers (make them async if needed) ...
        Some(Commands::Openmesh { command }) => {
            handle_openmesh_command(command).await?
        },
    }

    Ok(())
}
```

## Command Examples

Once integrated, you can use these commands:

```bash
# Show monitoring dashboard
capsule openmesh monitor status

# Check health of a specific xNode
capsule openmesh monitor health xnode-001

# Collect resource metrics
capsule openmesh monitor metrics xnode-001

# List all active alerts
capsule openmesh monitor alerts

# Acknowledge an alert
capsule openmesh monitor ack xnode-001_high_cpu_1234567890

# Resolve an alert
capsule openmesh monitor resolve xnode-001_high_cpu_1234567890

# Show monitoring configuration
capsule openmesh monitor config

# Live dashboard with auto-refresh
capsule openmesh monitor watch
```

## Integration with xNode Database

The monitoring system needs access to xNode data. You'll need to connect it with your xNode storage:

```rust
async fn handle_monitor_command(command: MonitorCommands) -> Result<()> {
    use capsule::monitoring::{MonitoringSystem, commands};
    use capsule::openmesh::storage::Storage;

    let mut system = MonitoringSystem::new(None).await?;
    let storage = Storage::new()?;

    match command {
        MonitorCommands::Health { xnode_id } => {
            // Get xNode data from storage
            let xnode = storage.get_xnode(&xnode_id)?;

            // Perform health check with actual data
            let health = system.check_health(
                xnode_id,
                xnode.ip_address.as_deref(),
                xnode.config.has_webserver,
            ).await;

            // Display results
            commands::show_health_check(&mut system, &xnode_id).await?;
        }
        MonitorCommands::Metrics { xnode_id } => {
            // Get xNode data from storage
            let xnode = storage.get_xnode(&xnode_id)?;

            // Collect metrics with actual data
            let metrics = system.collect_metrics(
                xnode_id,
                xnode.ip_address.as_deref(),
                xnode.ssh_key_path.as_deref(),
            ).await;

            // Display results
            commands::show_metrics(&mut system, &xnode_id).await?;
        }
        // ... other commands ...
    }

    Ok(())
}
```

## Automated Monitoring Loop

For continuous monitoring, you can create a background task:

```rust
use tokio::time::{interval, Duration};

async fn start_monitoring_loop() -> Result<()> {
    let mut system = MonitoringSystem::new(None).await?;
    let storage = Storage::new()?;

    let check_interval = system.get_config().check_interval_seconds;
    let mut interval = interval(Duration::from_secs(check_interval));

    loop {
        interval.tick().await;

        // Get all xNodes
        let xnodes = storage.list_xnodes()?;

        // Check each xNode
        for xnode in xnodes {
            // Health check
            system.check_health(
                xnode.id.clone(),
                xnode.ip_address.as_deref(),
                xnode.config.has_webserver,
            ).await;

            // Metrics collection
            system.collect_metrics(
                xnode.id.clone(),
                xnode.ip_address.as_deref(),
                xnode.ssh_key_path.as_deref(),
            ).await;
        }

        // Save history
        system.save_history().await?;
    }
}

// Start monitoring in background
tokio::spawn(async move {
    if let Err(e) = start_monitoring_loop().await {
        eprintln!("Monitoring loop error: {}", e);
    }
});
```

## Configuration

Users can configure monitoring by editing `~/.capsule/monitoring.yml`:

```yaml
enabled: true
check_interval_seconds: 60

# Health check timeouts
ping_timeout: 5
ssh_timeout: 10
http_timeout: 10

# Alert thresholds
cpu_warning_threshold: 75.0
cpu_critical_threshold: 90.0
memory_warning_threshold: 80.0
memory_critical_threshold: 95.0
disk_warning_threshold: 85.0
disk_critical_threshold: 95.0

# Alert delivery
console_alerts: true
email_alerts: false
webhook_alerts: true
webhook_url: "https://your-webhook-endpoint.com/alerts"
slack_alerts: true
slack_webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Auto-remediation
auto_restart_on_failure: false
auto_scale_on_high_load: false
```

## Testing

Test the monitoring system with the example CLI:

```bash
# Build the example
cargo build --example monitoring_cli

# Run commands
cargo run --example monitoring_cli -- status
cargo run --example monitoring_cli -- health test-node
cargo run --example monitoring_cli -- watch
```

## Data Storage

Monitoring data is stored in:
- `~/.capsule/monitoring.yml` - Configuration
- `~/.capsule/monitoring_data/health_history.json` - Health checks (24h)
- `~/.capsule/monitoring_data/metrics_history.json` - Metrics (24h)
- `~/.capsule/monitoring_data/active_alerts.json` - Active alerts

## Alert Channels

### Webhook Setup
```yaml
webhook_alerts: true
webhook_url: "https://your-endpoint.com/webhook"
```

The webhook receives POST requests with alert JSON:
```json
{
  "id": "xnode-001_high_cpu_1234567890",
  "xnode_id": "xnode-001",
  "alert_type": "high_cpu",
  "severity": "critical",
  "message": "Critical CPU usage: 95.2%",
  "timestamp": "2024-01-15T10:30:00Z",
  "acknowledged": false,
  "resolved": false,
  "metadata": { ... }
}
```

### Slack Setup
1. Create a Slack webhook at https://api.slack.com/messaging/webhooks
2. Add the webhook URL to your config:
```yaml
slack_alerts: true
slack_webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

Alerts appear in Slack with color-coded severity and formatted fields.

## Next Steps

1. Integrate with your xNode storage system
2. Set up alert delivery channels (webhook, Slack)
3. Configure thresholds for your use case
4. Create systemd service for continuous monitoring (optional)
5. Set up auto-remediation policies (optional)

## Troubleshooting

### "Cannot find function X"
Make sure you've enabled the monitoring module in `src/lib.rs`:
```rust
pub mod monitoring;
```

### "No such file or directory: monitoring_data"
The system automatically creates this directory on first run. Make sure the user has write permissions to `~/.capsule/`.

### "SSH connection failed"
Ensure:
1. SSH key is configured correctly
2. SSH service is running on the xNode
3. Firewall allows SSH connections
4. Correct IP address is configured

### "Metrics collection returned None"
Check:
1. SSH connection is working
2. Commands (top, free, df, uptime) are available on xNode
3. SSH timeout is sufficient

## Support

For issues or questions, refer to:
- Main documentation: `MONITORING.md`
- Python reference: `capsule_package/monitoring.py`
- Example implementation: `examples/monitoring_cli.rs`
