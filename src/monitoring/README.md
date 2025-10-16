# Monitoring System Module

Complete monitoring and alerting system for OpenMesh xNodes with exact feature parity to the Python implementation.

## Module Overview

This directory contains the complete monitoring system with 5 core modules:

```
monitoring/
├── mod.rs          (16K)  # Main system, configuration, orchestration
├── health.rs       (8K)   # Health checks (ping, SSH, HTTP)
├── metrics.rs      (5K)   # Resource metrics (CPU, memory, disk)
├── alerts.rs       (11K)  # Alerting system with multi-channel delivery
└── commands.rs     (12K)  # CLI command implementations
```

**Total**: ~52K of production-ready Rust code

## Quick Start

### Import the module
```rust
use capsule::monitoring::{MonitoringSystem, commands};
```

### Initialize
```rust
let mut system = MonitoringSystem::new(None).await?;
```

### Perform health check
```rust
let health = system.check_health(
    "xnode-001".to_string(),
    Some("192.168.1.100"),
    false,
).await;
```

### Collect metrics
```rust
let metrics = system.collect_metrics(
    "xnode-001".to_string(),
    Some("192.168.1.100"),
    Some("~/.ssh/id_rsa"),
).await;
```

## Module Details

### mod.rs - Main System
**Key Components:**
- `MonitoringSystem` - Main orchestration struct
- `MonitoringConfig` - Configuration with thresholds
- `XNodeStatus` - Per-xNode status aggregation
- `DashboardData` - Dashboard view data

**Features:**
- Historical data management (24-hour retention)
- JSON persistence for health/metrics/alerts
- YAML configuration loading/saving
- Alert threshold evaluation
- Auto-remediation hooks

**Key Methods:**
```rust
pub async fn new(config_path: Option<PathBuf>) -> Result<Self>
pub async fn check_health(&mut self, xnode_id: String, ip: Option<&str>, has_web: bool) -> HealthCheck
pub async fn collect_metrics(&mut self, xnode_id: String, ip: Option<&str>, ssh_key: Option<&str>) -> Option<ResourceMetrics>
pub fn get_xnode_status(&self, xnode_id: &str) -> XNodeStatus
pub fn get_dashboard_data(&self) -> DashboardData
pub async fn save_history(&self) -> Result<()>
```

### health.rs - Health Checks
**Key Components:**
- `HealthChecker` - Performs health checks
- `HealthCheck` - Check results
- `HealthStatus` - Status enum (Healthy, Degraded, Unhealthy, Unknown)

**Features:**
- Async ping check (ICMP)
- Async SSH check (port 22 via netcat)
- Async HTTP check (optional, for web services)
- Response time tracking
- Error message collection
- Configurable timeouts

**Status Logic:**
- All checks pass → Healthy
- Some checks pass → Degraded
- No checks pass → Unhealthy
- No checks performed → Unknown

### metrics.rs - Resource Metrics
**Key Components:**
- `MetricsCollector` - SSH-based metrics collection
- `ResourceMetrics` - System resource data

**Features:**
- SSH command execution
- CPU percentage parsing
- Memory percentage parsing
- Disk usage parsing
- Load average parsing (1/5/15 min)
- Network I/O placeholders

**SSH Commands Used:**
```bash
top -bn1 | grep 'Cpu(s)' | awk '{print $2}'      # CPU
free | grep Mem | awk '{print ($3/$2) * 100}'    # Memory
df -h / | tail -1 | awk '{print $5}'             # Disk
uptime                                            # Load average
```

### alerts.rs - Alerting System
**Key Components:**
- `Alert` - Alert data structure
- `AlertType` - 7 alert types (HighCpu, HighMemory, LowDisk, etc.)
- `AlertSeverity` - Info, Warning, Critical
- `AlertManager` - Multi-channel delivery
- `AlertStore` - Alert persistence and querying

**Features:**
- Alert creation with metadata
- Duplicate prevention
- Multi-channel delivery:
  - Console (colored output)
  - Webhook (JSON POST)
  - Slack (formatted attachments)
  - Email (placeholder)
- Alert lifecycle (created → acknowledged → resolved)
- Alert querying by xNode, severity, status

**Alert Types:**
```rust
HighCpu         // CPU usage exceeds threshold
HighMemory      // Memory usage exceeds threshold
LowDisk         // Disk usage exceeds threshold
ServiceDown     // xNode unreachable (ping fails)
SshUnreachable  // SSH port unreachable
HttpError       // HTTP service error
CostThreshold   // Cost exceeds budget
```

### commands.rs - CLI Commands
**Key Components:**
- Command implementations for all 8 CLI commands
- Visual formatting (colors, tables, bars)
- Dashboard rendering

**Commands:**
```rust
pub async fn show_dashboard(&MonitoringSystem)         # Overview dashboard
pub async fn show_health_check(&mut MS, &str)          # Health check details
pub async fn show_metrics(&mut MS, &str)               # Resource metrics
pub async fn list_alerts(&MS)                          # Active alerts
pub async fn acknowledge_alert(&mut MS, &str)          # Acknowledge alert
pub async fn resolve_alert(&mut MS, &str)              # Resolve alert
pub async fn show_config(&MS)                          # Configuration
pub async fn watch_dashboard(&mut MS)                  # Live dashboard
```

**Visual Features:**
- Color-coded status indicators
- Prettytable formatting
- Usage bars with threshold colors
- Severity badges
- Timestamp formatting

## Configuration

### Default Configuration
```yaml
enabled: true
check_interval_seconds: 60

# Timeouts
ping_timeout: 5
ssh_timeout: 10
http_timeout: 10

# CPU Thresholds
cpu_warning_threshold: 75.0
cpu_critical_threshold: 90.0

# Memory Thresholds
memory_warning_threshold: 80.0
memory_critical_threshold: 95.0

# Disk Thresholds
disk_warning_threshold: 85.0
disk_critical_threshold: 95.0

# Alert Delivery
console_alerts: true
email_alerts: false
webhook_alerts: false
slack_alerts: false

email_recipients: []
webhook_url: null
slack_webhook_url: null

# Auto-remediation
auto_restart_on_failure: false
auto_scale_on_high_load: false
```

### Configuration Location
- File: `~/.capsule/monitoring.yml`
- Data: `~/.capsule/monitoring_data/`

## Data Persistence

### Storage Format
All data stored as JSON for easy debugging and portability.

### Files
1. **health_history.json** - Last 24 hours of health checks
   - Max 288 entries (5-minute intervals)
   - Per-xNode storage
   - Auto-pruned on save

2. **metrics_history.json** - Last 24 hours of metrics
   - Max 1440 entries (1-minute intervals)
   - Per-xNode storage
   - Auto-pruned on save

3. **active_alerts.json** - Current active alerts
   - All unresolved alerts
   - Keyed by alert ID
   - Persisted on changes

### Data Retention
```rust
const MAX_HEALTH_HISTORY: usize = 288;   // 24h @ 5min
const MAX_METRICS_HISTORY: usize = 1440; // 24h @ 1min
```

## Integration Example

### Standalone CLI
See `/examples/monitoring_cli.rs` for a complete example:

```rust
use capsule::monitoring::{MonitoringSystem, commands};
use clap::{Parser, Subcommand};

#[derive(Subcommand)]
enum Commands {
    Status,
    Health { xnode_id: String },
    Metrics { xnode_id: String },
    Alerts,
    // ... etc
}

#[tokio::main]
async fn main() -> Result<()> {
    let mut system = MonitoringSystem::new(None).await?;
    // Handle commands...
}
```

### Integration with Main CLI
See `/MONITORING_INTEGRATION.md` for detailed instructions on integrating with the main Capsule CLI.

## Testing

### Unit Tests
Run tests with:
```bash
cargo test --lib monitoring
```

Included tests:
- Health status determination
- Alert store operations
- Similar alert detection
- Load average parsing
- Metrics output parsing

### Manual Testing
```bash
# Build and run example
cargo run --example monitoring_cli -- status
cargo run --example monitoring_cli -- health test-node
cargo run --example monitoring_cli -- watch
```

## API Examples

### Get xNode Status
```rust
let status = system.get_xnode_status("xnode-001");
println!("Current health: {:?}", status.current_health);
println!("Current metrics: {:?}", status.current_metrics);
println!("Active alerts: {}", status.active_alerts.len());
```

### Get Dashboard Data
```rust
let data = system.get_dashboard_data();
println!("Total: {}", data.total_xnodes);
println!("Healthy: {}", data.healthy_xnodes);
println!("Critical: {}", data.critical_alerts);
```

### Acknowledge Alert
```rust
if system.acknowledge_alert(&alert_id) {
    system.save_history().await?;
    println!("Alert acknowledged");
}
```

### Resolve Alert
```rust
if system.resolve_alert(&alert_id) {
    system.save_history().await?;
    println!("Alert resolved");
}
```

## Alert Delivery

### Console
Enabled by default. Prints to stderr with colors:
```
ALERT [CRITICAL] xnode-001 Critical CPU usage: 95.2%
```

### Webhook
Configure webhook URL, receives POST with alert JSON:
```json
{
  "id": "xnode-001_high_cpu_1234567890",
  "xnode_id": "xnode-001",
  "alert_type": "high_cpu",
  "severity": "critical",
  "message": "Critical CPU usage: 95.2%",
  "timestamp": "2024-01-15T10:30:00Z",
  "acknowledged": false,
  "resolved": false
}
```

### Slack
Configure webhook URL, sends formatted attachment:
- Color-coded by severity (red/yellow/green)
- Title with xNode ID
- Message text
- Fields for severity and type
- Timestamp

## Dependencies

### Required Crates
- `tokio` - Async runtime
- `serde` / `serde_json` / `serde_yaml` - Serialization
- `chrono` - Timestamp handling
- `reqwest` - HTTP client
- `anyhow` - Error handling
- `colored` - Terminal colors
- `prettytable-rs` - Tables
- `dirs` - Home directory

### System Commands
- `ping` - ICMP checks
- `nc` (netcat) - Port checks
- `ssh` - Metrics collection

## Performance Considerations

### Async Operations
All I/O operations are async to prevent blocking:
- Health checks run concurrently
- Metrics collection uses timeout
- Alert delivery is non-blocking

### Memory Management
- Historical data auto-pruned to limits
- Resolved alerts kept in storage
- JSON files rewritten on save (consider optimization for high-frequency updates)

### Scalability
- Current design: serial checks per xNode
- For many xNodes: batch checks with `tokio::spawn`
- Alert delivery: fire-and-forget (errors logged)

## Future Enhancements

### Planned
- [ ] Email SMTP implementation
- [ ] Network I/O metrics
- [ ] Alert rate limiting
- [ ] Alert history beyond active
- [ ] Prometheus/Grafana integration

### Possible
- [ ] Web dashboard
- [ ] Alert rules engine
- [ ] Escalation policies
- [ ] Multi-user support
- [ ] Custom check scripts

## Troubleshooting

### "Cannot compile monitoring module"
- Check that `pub mod monitoring;` is in `src/lib.rs`
- Ensure all dependencies are in Cargo.toml
- Run `cargo clean && cargo build`

### "Failed to collect metrics"
- Verify SSH access to xNode
- Check SSH key path
- Ensure commands exist on remote system
- Increase timeout if network is slow

### "Alerts not delivered"
- Check delivery flags in config
- Verify webhook/Slack URLs
- Check console output for errors
- Test webhook endpoint separately

## Documentation

- **Main Documentation**: `/MONITORING.md`
- **Integration Guide**: `/MONITORING_INTEGRATION.md`
- **Summary**: `/MONITORING_SUMMARY.md`
- **This File**: `/src/monitoring/README.md`

## License

MIT License - Part of Capsule project
