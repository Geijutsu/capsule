use anyhow::Result;
use clap::{Parser, Subcommand};
use capsule::monitoring::{MonitoringSystem, commands};

#[derive(Parser)]
#[command(name = "capsule-monitor")]
#[command(about = "OpenMesh xNode Monitoring CLI")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Show monitoring dashboard with overview
    Status,

    /// Perform health check on an xNode
    Health {
        /// xNode ID to check
        xnode_id: String,
    },

    /// Collect resource metrics from an xNode
    Metrics {
        /// xNode ID to check
        xnode_id: String,
    },

    /// List all active alerts
    Alerts,

    /// Acknowledge an alert
    Ack {
        /// Alert ID to acknowledge
        alert_id: String,
    },

    /// Resolve an alert
    Resolve {
        /// Alert ID to resolve
        alert_id: String,
    },

    /// Show monitoring configuration
    Config,

    /// Live dashboard with auto-refresh
    Watch,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Initialize monitoring system
    let mut system = MonitoringSystem::new(None).await?;

    match cli.command {
        Commands::Status => {
            commands::show_dashboard(&system).await?;
        }
        Commands::Health { xnode_id } => {
            commands::show_health_check(&mut system, &xnode_id).await?;
        }
        Commands::Metrics { xnode_id } => {
            commands::show_metrics(&mut system, &xnode_id).await?;
        }
        Commands::Alerts => {
            commands::list_alerts(&system).await?;
        }
        Commands::Ack { alert_id } => {
            commands::acknowledge_alert(&mut system, &alert_id).await?;
        }
        Commands::Resolve { alert_id } => {
            commands::resolve_alert(&mut system, &alert_id).await?;
        }
        Commands::Config => {
            commands::show_config(&system).await?;
        }
        Commands::Watch => {
            commands::watch_dashboard(&mut system).await?;
        }
    }

    Ok(())
}
