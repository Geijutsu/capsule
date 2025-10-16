# Capsule Monitoring & Alerting System

Comprehensive monitoring and alerting system for OpenMesh xNodes with exact feature parity to the Python implementation.

## Overview

The monitoring system provides:
- Real-time health checks (ping, SSH, HTTP)
- Resource usage tracking (CPU, memory, disk, load average)
- Configurable alert thresholds
- Multi-channel alert delivery (console, email, webhook, Slack)
- 24-hour historical data retention
- Live dashboard with auto-refresh

## Architecture

### Module Structure

```
src/monitoring/
├── mod.rs          # Main monitoring system & configuration
├── health.rs       # Health check functionality
├── metrics.rs      # Resource metrics collection
├── alerts.rs       # Alerting system & delivery
└── commands.rs     # CLI command implementations
```

### Core Components

#### 1. MonitoringSystem (`mod.rs`)
Main orchestration system that:
- Manages configuration and persistence
- Coordinates health checks and metrics collection
- Evaluates thresholds and triggers alerts
- Maintains historical data (24 hours)

#### 2. HealthChecker (`health.rs`)
Performs comprehensive health checks:
- **Ping Check**: ICMP reachability test
- **SSH Check**: Port 22 connectivity test
- **HTTP Check**: Web service availability test

Status levels:
- `Healthy`: All checks pass
- `Degraded`: Some checks pass
- `Unhealthy`: No checks pass
- `Unknown`: No data available

#### 3. MetricsCollector (`metrics.rs`)
Collects resource usage via SSH:
- CPU percentage
- Memory percentage
- Disk usage percentage
- Network I/O (Mbps)
- Load average (1min, 5min, 15min)

#### 4. AlertManager (`alerts.rs`)
Manages alert lifecycle:
- Alert creation with duplicate prevention
- Multi-channel delivery
- Acknowledgment and resolution tracking
- Severity levels: Info, Warning, Critical

## Configuration

Configuration file: `~/.capsule/monitoring.yml`

### Example Configuration

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

# Alert delivery channels
console_alerts: true
email_alerts: false
webhook_alerts: false
slack_alerts: false

# Alert endpoints
email_recipients: []
webhook_url: null
slack_webhook_url: null

# Auto-remediation
auto_restart_on_failure: false
auto_scale_on_high_load: false
```

## CLI Commands

### Status Dashboard
```bash
capsule openmesh monitor status
```
Shows overview with:
- Total xNodes count
- Healthy/unhealthy breakdown
- Active alert counts
- Recent health checks

### Health Check
```bash
capsule openmesh monitor health <xnode_id>
```
Performs comprehensive health check on specific xNode:
- Ping test with response time
- SSH connectivity test
- HTTP availability (if configured)
- Error messages

### Resource Metrics
```bash
capsule openmesh monitor metrics <xnode_id>
```
Collects and displays resource usage:
- CPU usage with visual bar
- Memory usage with visual bar
- Disk usage with visual bar
- Load averages

### Alert Management
```bash
# List all active alerts
capsule openmesh monitor alerts

# Acknowledge an alert
capsule openmesh monitor ack <alert_id>

# Resolve an alert
capsule openmesh monitor resolve <alert_id>
```

### Configuration
```bash
capsule openmesh monitor config
```
Displays current monitoring configuration:
- General settings
- Timeout values
- Alert thresholds
- Delivery channels
- Auto-remediation settings

### Live Dashboard
```bash
capsule openmesh monitor watch
```
Auto-refreshing dashboard (5-second intervals):
- Real-time health status
- Current metrics
- Active alerts
- Press Ctrl+C to exit

## Data Persistence

### Storage Location
`~/.capsule/monitoring_data/`

### Files
- `health_history.json`: Last 24 hours of health checks (288 entries @ 5min intervals)
- `metrics_history.json`: Last 24 hours of metrics (1440 entries @ 1min intervals)
- `active_alerts.json`: Current active alerts

### Data Retention
- Health checks: 288 entries (24 hours @ 5min intervals)
- Metrics: 1440 entries (24 hours @ 1min intervals)
- Alerts: Retained until resolved

## Alert Types

### Alert Types
- `HighCpu`: CPU usage exceeds threshold
- `HighMemory`: Memory usage exceeds threshold
- `LowDisk`: Disk usage exceeds threshold
- `ServiceDown`: xNode unreachable (ping fails)
- `SshUnreachable`: SSH port unreachable
- `HttpError`: HTTP service unavailable
- `CostThreshold`: Cost exceeds budget

### Severity Levels
- `Info`: Informational alerts
- `Warning`: Requires attention
- `Critical`: Immediate action required

### Alert Lifecycle
1. **Created**: Alert generated when threshold exceeded
2. **Delivered**: Sent via configured channels
3. **Acknowledged**: User has seen the alert
4. **Resolved**: Issue fixed, alert closed

### Duplicate Prevention
The system prevents alert spam by checking for similar active alerts before creating new ones. Only one alert per (xnode_id, alert_type) combination can be active.

## Alert Delivery Channels

### Console
```rust
// Enabled by default
console_alerts: true
```
Prints alerts to stderr with colored output.

### Email
```yaml
email_alerts: true
email_recipients:
  - admin@example.com
  - ops@example.com
```
Requires SMTP configuration (placeholder in current implementation).

### Webhook
```yaml
webhook_alerts: true
webhook_url: "https://your-webhook-endpoint.com/alerts"
```
POSTs alert data as JSON to the specified URL.

### Slack
```yaml
slack_alerts: true
slack_webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```
Sends formatted messages to Slack with:
- Color-coded severity
- xNode ID
- Alert message
- Severity and type fields
- Timestamp

## API Usage

### Initialize System
```rust
use capsule::monitoring::MonitoringSystem;

let mut system = MonitoringSystem::new(None).await?;
```

### Perform Health Check
```rust
let health = system.check_health(
    "xnode-001".to_string(),
    Some("192.168.1.100"),
    false, // has_webserver
).await;

println!("Status: {:?}", health.status);
```

### Collect Metrics
```rust
let metrics = system.collect_metrics(
    "xnode-001".to_string(),
    Some("192.168.1.100"),
    Some("~/.ssh/id_rsa"),
).await;

if let Some(m) = metrics {
    println!("CPU: {:.1}%", m.cpu_percent);
    println!("Memory: {:.1}%", m.memory_percent);
}
```

### Get Dashboard Data
```rust
let data = system.get_dashboard_data();

println!("Total xNodes: {}", data.total_xnodes);
println!("Healthy: {}", data.healthy_xnodes);
println!("Critical Alerts: {}", data.critical_alerts);
```

### Save History
```rust
system.save_history().await?;
```

## Threshold Configuration

### CPU Thresholds
- **Warning**: 75% (default)
- **Critical**: 90% (default)

### Memory Thresholds
- **Warning**: 80% (default)
- **Critical**: 95% (default)

### Disk Thresholds
- **Warning**: 85% (default)
- **Critical**: 95% (default)

## Auto-Remediation

Configure automatic responses to alerts:

```yaml
auto_restart_on_failure: false
auto_scale_on_high_load: false
```

When enabled:
- `auto_restart_on_failure`: Automatically restarts xNode on `ServiceDown` alert
- `auto_scale_on_high_load`: Triggers scaling on high resource usage

## Visual Elements

### Status Indicators
- `HEALTHY`: Green
- `DEGRADED`: Yellow
- `UNHEALTHY`: Red
- `UNKNOWN`: White

### Alert Badges
- `[CRITICAL]`: Red, bold
- `[WARNING]`: Yellow
- `[INFO]`: Blue
- `[ACK]`: White (for acknowledged alerts)

### Usage Bars
```
CPU Usage: 85.5%
  [=====================================     ]
```
Color-coded based on thresholds:
- Green: Below warning
- Yellow: Warning to critical
- Red: Above critical

## Testing

Run the example CLI:
```bash
cargo run --example monitoring_cli -- status
cargo run --example monitoring_cli -- health xnode-001
cargo run --example monitoring_cli -- metrics xnode-001
cargo run --example monitoring_cli -- alerts
cargo run --example monitoring_cli -- watch
```

## Dependencies

### Required
- `tokio`: Async runtime
- `serde`: Serialization
- `serde_json`: JSON persistence
- `serde_yaml`: YAML configuration
- `chrono`: Timestamp handling
- `reqwest`: HTTP client for webhooks
- `anyhow`: Error handling
- `colored`: Terminal colors
- `prettytable-rs`: Table formatting
- `dirs`: Home directory detection

### System Commands
- `ping`: ICMP connectivity test
- `nc` (netcat): TCP port checking
- `ssh`: Remote metrics collection

## Comparison with Python Implementation

### Feature Parity
✅ Health checks (ping, SSH, HTTP)
✅ Resource metrics collection
✅ Alert thresholds and severity levels
✅ Multi-channel alert delivery
✅ 24-hour data retention
✅ Duplicate alert prevention
✅ Alert acknowledgment and resolution
✅ Dashboard visualization
✅ Live watch mode
✅ JSON persistence
✅ YAML configuration

### Improvements
- ✨ Async/await for better performance
- ✨ Type-safe configuration
- ✨ Better error handling with Result types
- ✨ Modular architecture
- ✨ Comprehensive tests
- ✨ Example CLI included

## Future Enhancements

- [ ] Email delivery implementation (SMTP)
- [ ] Network I/O metrics collection
- [ ] Alert history and analytics
- [ ] Grafana/Prometheus integration
- [ ] Web dashboard
- [ ] Alert rules engine
- [ ] Notification rate limiting
- [ ] Multi-user support
- [ ] Alert escalation policies

## License

MIT License - See LICENSE file for details
