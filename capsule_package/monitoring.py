"""
OpenMesh xNode Monitoring and Alerting System

Provides real-time health checks, resource monitoring, and configurable alerts
for deployed xNodes across all cloud providers.

Features:
- Health check monitoring (ping, SSH, HTTP)
- Resource usage tracking (CPU, memory, disk, network)
- Alert system with configurable thresholds
- Alert delivery (console, email, webhook, Slack)
- Monitoring dashboard with historical data
- Auto-remediation triggers
"""

import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status values"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of monitoring alerts"""
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    LOW_DISK = "low_disk"
    SERVICE_DOWN = "service_down"
    SSH_UNREACHABLE = "ssh_unreachable"
    HTTP_ERROR = "http_error"
    COST_THRESHOLD = "cost_threshold"


@dataclass
class HealthCheck:
    """Result of a health check"""
    xnode_id: str
    timestamp: str
    status: HealthStatus
    checks: Dict[str, bool]  # ping, ssh, http, etc.
    response_times: Dict[str, float]  # milliseconds
    error_messages: List[str]


@dataclass
class ResourceMetrics:
    """Resource usage metrics for an xNode"""
    xnode_id: str
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_in_mbps: float
    network_out_mbps: float
    load_average: Tuple[float, float, float]


@dataclass
class Alert:
    """Monitoring alert"""
    id: str
    xnode_id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: str
    acknowledged: bool = False
    resolved: bool = False
    metadata: Optional[Dict] = None


@dataclass
class MonitoringConfig:
    """Monitoring configuration and thresholds"""
    enabled: bool = True
    check_interval_seconds: int = 60

    # Health check settings
    ping_timeout: int = 5
    ssh_timeout: int = 10
    http_timeout: int = 10

    # Alert thresholds
    cpu_warning_threshold: float = 75.0
    cpu_critical_threshold: float = 90.0
    memory_warning_threshold: float = 80.0
    memory_critical_threshold: float = 95.0
    disk_warning_threshold: float = 85.0
    disk_critical_threshold: float = 95.0

    # Alert delivery
    console_alerts: bool = True
    email_alerts: bool = False
    webhook_alerts: bool = False
    slack_alerts: bool = False

    # Alert delivery endpoints
    email_recipients: List[str] = None
    webhook_url: Optional[str] = None
    slack_webhook_url: Optional[str] = None

    # Auto-remediation
    auto_restart_on_failure: bool = False
    auto_scale_on_high_load: bool = False


class MonitoringSystem:
    """
    Main monitoring system for OpenMesh xNodes

    Tracks health, collects metrics, generates alerts, and provides
    monitoring dashboard functionality.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize monitoring system"""
        self.config_path = config_path or Path.home() / ".capsule" / "monitoring.yml"
        self.data_dir = Path.home() / ".capsule" / "monitoring_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.config = self._load_config()
        self.health_history: Dict[str, List[HealthCheck]] = {}
        self.metrics_history: Dict[str, List[ResourceMetrics]] = {}
        self.active_alerts: Dict[str, Alert] = {}

        self._load_history()

    def _load_config(self) -> MonitoringConfig:
        """Load monitoring configuration"""
        if self.config_path.exists():
            try:
                import yaml
                with open(self.config_path) as f:
                    data = yaml.safe_load(f) or {}
                return MonitoringConfig(**data)
            except Exception as e:
                logger.warning(f"Failed to load monitoring config: {e}")

        return MonitoringConfig()

    def _save_config(self):
        """Save monitoring configuration"""
        try:
            import yaml
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(asdict(self.config), f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Failed to save monitoring config: {e}")

    def _load_history(self):
        """Load historical monitoring data"""
        # Load last 24 hours of health checks
        health_file = self.data_dir / "health_history.json"
        if health_file.exists():
            try:
                with open(health_file) as f:
                    data = json.load(f)
                for xnode_id, checks in data.items():
                    self.health_history[xnode_id] = [
                        HealthCheck(**check) for check in checks[-288:]  # Last 24h at 5min intervals
                    ]
            except Exception as e:
                logger.warning(f"Failed to load health history: {e}")

        # Load last 24 hours of metrics
        metrics_file = self.data_dir / "metrics_history.json"
        if metrics_file.exists():
            try:
                with open(metrics_file) as f:
                    data = json.load(f)
                for xnode_id, metrics in data.items():
                    self.metrics_history[xnode_id] = [
                        ResourceMetrics(**m) for m in metrics[-1440:]  # Last 24h at 1min intervals
                    ]
            except Exception as e:
                logger.warning(f"Failed to load metrics history: {e}")

        # Load active alerts
        alerts_file = self.data_dir / "active_alerts.json"
        if alerts_file.exists():
            try:
                with open(alerts_file) as f:
                    data = json.load(f)
                self.active_alerts = {
                    alert_id: Alert(**alert_data)
                    for alert_id, alert_data in data.items()
                    if not alert_data.get('resolved', False)
                }
            except Exception as e:
                logger.warning(f"Failed to load alerts: {e}")

    def _save_history(self):
        """Save monitoring history to disk"""
        try:
            # Save health history
            health_data = {
                xnode_id: [asdict(check) for check in checks[-288:]]
                for xnode_id, checks in self.health_history.items()
            }
            with open(self.data_dir / "health_history.json", 'w') as f:
                json.dump(health_data, f, indent=2, default=str)

            # Save metrics history
            metrics_data = {
                xnode_id: [asdict(m) for m in metrics[-1440:]]
                for xnode_id, metrics in self.metrics_history.items()
            }
            with open(self.data_dir / "metrics_history.json", 'w') as f:
                json.dump(metrics_data, f, indent=2, default=str)

            # Save active alerts
            alerts_data = {
                alert_id: asdict(alert)
                for alert_id, alert in self.active_alerts.items()
            }
            with open(self.data_dir / "active_alerts.json", 'w') as f:
                json.dump(alerts_data, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to save monitoring history: {e}")

    def check_health(self, xnode_id: str, xnode_data: Dict) -> HealthCheck:
        """
        Perform comprehensive health check on an xNode

        Checks:
        - Ping (ICMP reachability)
        - SSH (port 22 connectivity)
        - HTTP (web service if applicable)
        """
        import subprocess

        checks = {}
        response_times = {}
        errors = []

        ip_address = xnode_data.get('ip_address')
        if not ip_address:
            return HealthCheck(
                xnode_id=xnode_id,
                timestamp=datetime.now().isoformat(),
                status=HealthStatus.UNKNOWN,
                checks={},
                response_times={},
                error_messages=["No IP address available"]
            )

        # Ping check
        try:
            start = time.time()
            result = subprocess.run(
                ['ping', '-c', '1', '-W', str(self.config.ping_timeout), ip_address],
                capture_output=True,
                timeout=self.config.ping_timeout + 1
            )
            response_times['ping'] = (time.time() - start) * 1000
            checks['ping'] = result.returncode == 0
            if result.returncode != 0:
                errors.append(f"Ping failed: {result.stderr.decode()[:100]}")
        except Exception as e:
            checks['ping'] = False
            errors.append(f"Ping error: {str(e)}")

        # SSH check
        try:
            start = time.time()
            result = subprocess.run(
                ['nc', '-z', '-w', str(self.config.ssh_timeout), ip_address, '22'],
                capture_output=True,
                timeout=self.config.ssh_timeout + 1
            )
            response_times['ssh'] = (time.time() - start) * 1000
            checks['ssh'] = result.returncode == 0
            if result.returncode != 0:
                errors.append(f"SSH port unreachable")
        except Exception as e:
            checks['ssh'] = False
            errors.append(f"SSH check error: {str(e)}")

        # HTTP check (if web service is configured)
        if xnode_data.get('has_webserver'):
            try:
                import requests
                start = time.time()
                response = requests.get(
                    f"http://{ip_address}",
                    timeout=self.config.http_timeout
                )
                response_times['http'] = (time.time() - start) * 1000
                checks['http'] = response.status_code < 500
                if response.status_code >= 500:
                    errors.append(f"HTTP returned {response.status_code}")
            except Exception as e:
                checks['http'] = False
                errors.append(f"HTTP check error: {str(e)}")

        # Determine overall status
        if all(checks.values()):
            status = HealthStatus.HEALTHY
        elif any(checks.values()):
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY

        health_check = HealthCheck(
            xnode_id=xnode_id,
            timestamp=datetime.now().isoformat(),
            status=status,
            checks=checks,
            response_times=response_times,
            error_messages=errors
        )

        # Store in history
        if xnode_id not in self.health_history:
            self.health_history[xnode_id] = []
        self.health_history[xnode_id].append(health_check)

        # Check for alerts
        self._check_health_alerts(health_check)

        return health_check

    def collect_metrics(self, xnode_id: str, xnode_data: Dict) -> Optional[ResourceMetrics]:
        """
        Collect resource usage metrics from an xNode

        Requires SSH access to the xNode to run monitoring commands.
        """
        ip_address = xnode_data.get('ip_address')
        if not ip_address:
            return None

        try:
            import subprocess

            # Use SSH to collect metrics (requires SSH key setup)
            # This is a simplified example - production would use paramiko or fabric
            ssh_key = xnode_data.get('ssh_key_path', '~/.ssh/id_rsa')

            # Collect CPU, memory, disk usage via SSH
            cmd = (
                f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "
                f"-i {ssh_key} root@{ip_address} "
                f"'top -bn1 | grep \"Cpu(s)\" | awk \"{{print \\$2}}\" && "
                f"free | grep Mem | awk \"{{print (\\$3/\\$2) * 100}}\" && "
                f"df -h / | tail -1 | awk \"{{print \\$5}}\" && "
                f"uptime'"
            )

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.decode().strip().split('\n')
                cpu_percent = float(lines[0].replace('%', ''))
                memory_percent = float(lines[1])
                disk_percent = float(lines[2].replace('%', ''))

                # Parse load average from uptime
                load_avg = tuple(float(x) for x in lines[3].split('load average:')[1].split(','))

                metrics = ResourceMetrics(
                    xnode_id=xnode_id,
                    timestamp=datetime.now().isoformat(),
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    disk_percent=disk_percent,
                    network_in_mbps=0.0,  # Would need additional monitoring
                    network_out_mbps=0.0,
                    load_average=load_avg
                )

                # Store in history
                if xnode_id not in self.metrics_history:
                    self.metrics_history[xnode_id] = []
                self.metrics_history[xnode_id].append(metrics)

                # Check for alerts
                self._check_metrics_alerts(metrics)

                return metrics

        except Exception as e:
            logger.debug(f"Failed to collect metrics for {xnode_id}: {e}")

        return None

    def _check_health_alerts(self, health_check: HealthCheck):
        """Generate alerts based on health check results"""
        if health_check.status == HealthStatus.UNHEALTHY:
            if not health_check.checks.get('ssh', True):
                self._create_alert(
                    xnode_id=health_check.xnode_id,
                    alert_type=AlertType.SSH_UNREACHABLE,
                    severity=AlertSeverity.CRITICAL,
                    message=f"SSH unreachable on {health_check.xnode_id}",
                    metadata={'health_check': asdict(health_check)}
                )

            if not health_check.checks.get('ping', True):
                self._create_alert(
                    xnode_id=health_check.xnode_id,
                    alert_type=AlertType.SERVICE_DOWN,
                    severity=AlertSeverity.CRITICAL,
                    message=f"xNode {health_check.xnode_id} is unreachable",
                    metadata={'health_check': asdict(health_check)}
                )

    def _check_metrics_alerts(self, metrics: ResourceMetrics):
        """Generate alerts based on resource metrics"""
        # CPU alerts
        if metrics.cpu_percent >= self.config.cpu_critical_threshold:
            self._create_alert(
                xnode_id=metrics.xnode_id,
                alert_type=AlertType.HIGH_CPU,
                severity=AlertSeverity.CRITICAL,
                message=f"Critical CPU usage: {metrics.cpu_percent:.1f}%",
                metadata={'metrics': asdict(metrics)}
            )
        elif metrics.cpu_percent >= self.config.cpu_warning_threshold:
            self._create_alert(
                xnode_id=metrics.xnode_id,
                alert_type=AlertType.HIGH_CPU,
                severity=AlertSeverity.WARNING,
                message=f"High CPU usage: {metrics.cpu_percent:.1f}%",
                metadata={'metrics': asdict(metrics)}
            )

        # Memory alerts
        if metrics.memory_percent >= self.config.memory_critical_threshold:
            self._create_alert(
                xnode_id=metrics.xnode_id,
                alert_type=AlertType.HIGH_MEMORY,
                severity=AlertSeverity.CRITICAL,
                message=f"Critical memory usage: {metrics.memory_percent:.1f}%",
                metadata={'metrics': asdict(metrics)}
            )
        elif metrics.memory_percent >= self.config.memory_warning_threshold:
            self._create_alert(
                xnode_id=metrics.xnode_id,
                alert_type=AlertType.HIGH_MEMORY,
                severity=AlertSeverity.WARNING,
                message=f"High memory usage: {metrics.memory_percent:.1f}%",
                metadata={'metrics': asdict(metrics)}
            )

        # Disk alerts
        if metrics.disk_percent >= self.config.disk_critical_threshold:
            self._create_alert(
                xnode_id=metrics.xnode_id,
                alert_type=AlertType.LOW_DISK,
                severity=AlertSeverity.CRITICAL,
                message=f"Critical disk usage: {metrics.disk_percent:.1f}%",
                metadata={'metrics': asdict(metrics)}
            )
        elif metrics.disk_percent >= self.config.disk_warning_threshold:
            self._create_alert(
                xnode_id=metrics.xnode_id,
                alert_type=AlertType.LOW_DISK,
                severity=AlertSeverity.WARNING,
                message=f"High disk usage: {metrics.disk_percent:.1f}%",
                metadata={'metrics': asdict(metrics)}
            )

    def _create_alert(self, xnode_id: str, alert_type: AlertType,
                     severity: AlertSeverity, message: str, metadata: Optional[Dict] = None):
        """Create a new alert"""
        alert_id = f"{xnode_id}_{alert_type.value}_{int(time.time())}"

        # Check if similar alert already exists (prevent spam)
        existing = [
            a for a in self.active_alerts.values()
            if a.xnode_id == xnode_id and a.alert_type == alert_type and not a.resolved
        ]
        if existing:
            return  # Don't create duplicate

        alert = Alert(
            id=alert_id,
            xnode_id=xnode_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            timestamp=datetime.now().isoformat(),
            metadata=metadata
        )

        self.active_alerts[alert_id] = alert

        # Deliver alert
        self._deliver_alert(alert)

        # Auto-remediation
        if self.config.auto_restart_on_failure and alert_type == AlertType.SERVICE_DOWN:
            logger.info(f"Auto-remediation triggered for {xnode_id}")
            # Would trigger restart here

    def _deliver_alert(self, alert: Alert):
        """Deliver alert via configured channels"""
        if self.config.console_alerts:
            logger.warning(f"ALERT [{alert.severity.value.upper()}] {alert.message}")

        # Email delivery
        if self.config.email_alerts and self.config.email_recipients:
            self._send_email_alert(alert)

        # Webhook delivery
        if self.config.webhook_alerts and self.config.webhook_url:
            self._send_webhook_alert(alert)

        # Slack delivery
        if self.config.slack_alerts and self.config.slack_webhook_url:
            self._send_slack_alert(alert)

    def _send_email_alert(self, alert: Alert):
        """Send alert via email"""
        try:
            import smtplib
            from email.mime.text import MIMEText

            # This is a placeholder - would need SMTP configuration
            logger.info(f"Would send email alert: {alert.message}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook"""
        try:
            import requests
            payload = asdict(alert)
            requests.post(self.config.webhook_url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")

    def _send_slack_alert(self, alert: Alert):
        """Send alert to Slack"""
        try:
            import requests

            color = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9900",
                AlertSeverity.CRITICAL: "#ff0000"
            }[alert.severity]

            payload = {
                "attachments": [{
                    "color": color,
                    "title": f"xNode Alert: {alert.xnode_id}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Type", "value": alert.alert_type.value, "short": True},
                    ],
                    "footer": "Capsule Monitoring",
                    "ts": int(datetime.fromisoformat(alert.timestamp).timestamp())
                }]
            }

            requests.post(self.config.slack_webhook_url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            self._save_history()

    def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved = True
            self._save_history()

    def get_xnode_status(self, xnode_id: str) -> Dict:
        """Get comprehensive status for an xNode"""
        recent_health = self.health_history.get(xnode_id, [])[-10:] if xnode_id in self.health_history else []
        recent_metrics = self.metrics_history.get(xnode_id, [])[-10:] if xnode_id in self.metrics_history else []

        alerts = [a for a in self.active_alerts.values() if a.xnode_id == xnode_id and not a.resolved]

        return {
            'xnode_id': xnode_id,
            'current_health': recent_health[-1] if recent_health else None,
            'current_metrics': recent_metrics[-1] if recent_metrics else None,
            'active_alerts': alerts,
            'health_history': recent_health,
            'metrics_history': recent_metrics
        }

    def get_dashboard_data(self) -> Dict:
        """Get data for monitoring dashboard"""
        all_xnodes = list(set(list(self.health_history.keys()) + list(self.metrics_history.keys())))

        healthy_count = sum(
            1 for xid in all_xnodes
            if self.health_history.get(xid, [])
            and self.health_history[xid][-1].status == HealthStatus.HEALTHY
        )

        critical_alerts = [a for a in self.active_alerts.values()
                          if a.severity == AlertSeverity.CRITICAL and not a.resolved]
        warning_alerts = [a for a in self.active_alerts.values()
                         if a.severity == AlertSeverity.WARNING and not a.resolved]

        return {
            'total_xnodes': len(all_xnodes),
            'healthy_xnodes': healthy_count,
            'unhealthy_xnodes': len(all_xnodes) - healthy_count,
            'critical_alerts': len(critical_alerts),
            'warning_alerts': len(warning_alerts),
            'active_alerts': list(self.active_alerts.values()),
            'recent_checks': {
                xid: self.health_history[xid][-1]
                for xid in all_xnodes
                if xid in self.health_history and self.health_history[xid]
            }
        }


def get_default_monitoring() -> MonitoringSystem:
    """Get default monitoring system instance"""
    return MonitoringSystem()
