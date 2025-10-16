pub mod health;
pub mod metrics;
pub mod alerts;
pub mod commands;

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use tokio::fs;

use health::{HealthCheck, HealthChecker, HealthStatus};
use metrics::{MetricsCollector, ResourceMetrics};
use alerts::{Alert, AlertManager, AlertSeverity, AlertStore, AlertType, AlertDeliveryConfig};

const MAX_HEALTH_HISTORY: usize = 288;  // 24 hours at 5 min intervals
const MAX_METRICS_HISTORY: usize = 1440; // 24 hours at 1 min intervals

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitoringConfig {
    pub enabled: bool,
    pub check_interval_seconds: u64,

    // Health check settings
    pub ping_timeout: u64,
    pub ssh_timeout: u64,
    pub http_timeout: u64,

    // Alert thresholds
    pub cpu_warning_threshold: f64,
    pub cpu_critical_threshold: f64,
    pub memory_warning_threshold: f64,
    pub memory_critical_threshold: f64,
    pub disk_warning_threshold: f64,
    pub disk_critical_threshold: f64,

    // Alert delivery
    #[serde(flatten)]
    pub alert_delivery: AlertDeliveryConfig,

    // Auto-remediation
    pub auto_restart_on_failure: bool,
    pub auto_scale_on_high_load: bool,
}

impl Default for MonitoringConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            check_interval_seconds: 60,
            ping_timeout: 5,
            ssh_timeout: 10,
            http_timeout: 10,
            cpu_warning_threshold: 75.0,
            cpu_critical_threshold: 90.0,
            memory_warning_threshold: 80.0,
            memory_critical_threshold: 95.0,
            disk_warning_threshold: 85.0,
            disk_critical_threshold: 95.0,
            alert_delivery: AlertDeliveryConfig::default(),
            auto_restart_on_failure: false,
            auto_scale_on_high_load: false,
        }
    }
}

pub struct MonitoringSystem {
    config_path: PathBuf,
    data_dir: PathBuf,
    config: MonitoringConfig,
    health_checker: HealthChecker,
    metrics_collector: MetricsCollector,
    alert_manager: AlertManager,
    health_history: HashMap<String, Vec<HealthCheck>>,
    metrics_history: HashMap<String, Vec<ResourceMetrics>>,
    alert_store: AlertStore,
}

impl MonitoringSystem {
    pub async fn new(config_path: Option<PathBuf>) -> Result<Self> {
        let config_path = config_path.unwrap_or_else(|| {
            dirs::home_dir()
                .unwrap()
                .join(".capsule")
                .join("monitoring.yml")
        });

        let data_dir = dirs::home_dir()
            .unwrap()
            .join(".capsule")
            .join("monitoring_data");

        fs::create_dir_all(&data_dir).await?;

        let config = Self::load_config(&config_path).await?;
        let health_checker = HealthChecker::new(
            config.ping_timeout,
            config.ssh_timeout,
            config.http_timeout,
        );
        let metrics_collector = MetricsCollector::new(config.ssh_timeout);
        let alert_manager = AlertManager::new(config.alert_delivery.clone());

        let mut system = Self {
            config_path,
            data_dir,
            config,
            health_checker,
            metrics_collector,
            alert_manager,
            health_history: HashMap::new(),
            metrics_history: HashMap::new(),
            alert_store: AlertStore::new(),
        };

        system.load_history().await?;

        Ok(system)
    }

    async fn load_config(path: &Path) -> Result<MonitoringConfig> {
        if path.exists() {
            let content = fs::read_to_string(path).await?;
            let config: MonitoringConfig = serde_yaml::from_str(&content)?;
            Ok(config)
        } else {
            Ok(MonitoringConfig::default())
        }
    }

    pub async fn save_config(&self) -> Result<()> {
        if let Some(parent) = self.config_path.parent() {
            fs::create_dir_all(parent).await?;
        }
        let content = serde_yaml::to_string(&self.config)?;
        fs::write(&self.config_path, content).await?;
        Ok(())
    }

    async fn load_history(&mut self) -> Result<()> {
        // Load health history
        let health_file = self.data_dir.join("health_history.json");
        if health_file.exists() {
            let content = fs::read_to_string(&health_file).await?;
            let data: HashMap<String, Vec<HealthCheck>> = serde_json::from_str(&content)?;
            for (xnode_id, mut checks) in data {
                if checks.len() > MAX_HEALTH_HISTORY {
                    checks = checks.into_iter().rev().take(MAX_HEALTH_HISTORY).rev().collect();
                }
                self.health_history.insert(xnode_id, checks);
            }
        }

        // Load metrics history
        let metrics_file = self.data_dir.join("metrics_history.json");
        if metrics_file.exists() {
            let content = fs::read_to_string(&metrics_file).await?;
            let data: HashMap<String, Vec<ResourceMetrics>> = serde_json::from_str(&content)?;
            for (xnode_id, mut metrics) in data {
                if metrics.len() > MAX_METRICS_HISTORY {
                    metrics = metrics.into_iter().rev().take(MAX_METRICS_HISTORY).rev().collect();
                }
                self.metrics_history.insert(xnode_id, metrics);
            }
        }

        // Load active alerts
        let alerts_file = self.data_dir.join("active_alerts.json");
        if alerts_file.exists() {
            let content = fs::read_to_string(&alerts_file).await?;
            let data: HashMap<String, Alert> = serde_json::from_str(&content)?;
            self.alert_store.load_from_map(data);
        }

        Ok(())
    }

    pub async fn save_history(&self) -> Result<()> {
        // Save health history (last 24 hours)
        let health_data: HashMap<String, Vec<HealthCheck>> = self
            .health_history
            .iter()
            .map(|(k, v)| {
                let limited: Vec<HealthCheck> = v.iter().rev().take(MAX_HEALTH_HISTORY).rev().cloned().collect();
                (k.clone(), limited)
            })
            .collect();
        let content = serde_json::to_string_pretty(&health_data)?;
        fs::write(self.data_dir.join("health_history.json"), content).await?;

        // Save metrics history (last 24 hours)
        let metrics_data: HashMap<String, Vec<ResourceMetrics>> = self
            .metrics_history
            .iter()
            .map(|(k, v)| {
                let limited: Vec<ResourceMetrics> = v.iter().rev().take(MAX_METRICS_HISTORY).rev().cloned().collect();
                (k.clone(), limited)
            })
            .collect();
        let content = serde_json::to_string_pretty(&metrics_data)?;
        fs::write(self.data_dir.join("metrics_history.json"), content).await?;

        // Save active alerts
        let content = serde_json::to_string_pretty(self.alert_store.as_map())?;
        fs::write(self.data_dir.join("active_alerts.json"), content).await?;

        Ok(())
    }

    pub async fn check_health(
        &mut self,
        xnode_id: String,
        ip_address: Option<&str>,
        has_webserver: bool,
    ) -> HealthCheck {
        let health_check = self
            .health_checker
            .check_health(xnode_id.clone(), ip_address, has_webserver)
            .await;

        // Store in history
        self.health_history
            .entry(xnode_id.clone())
            .or_insert_with(Vec::new)
            .push(health_check.clone());

        // Check for alerts
        self.check_health_alerts(&health_check).await;

        health_check
    }

    pub async fn collect_metrics(
        &mut self,
        xnode_id: String,
        ip_address: Option<&str>,
        ssh_key_path: Option<&str>,
    ) -> Option<ResourceMetrics> {
        let metrics = self
            .metrics_collector
            .collect_metrics(xnode_id.clone(), ip_address, ssh_key_path)
            .await?;

        // Store in history
        self.metrics_history
            .entry(xnode_id.clone())
            .or_insert_with(Vec::new)
            .push(metrics.clone());

        // Check for alerts
        self.check_metrics_alerts(&metrics).await;

        Some(metrics)
    }

    async fn check_health_alerts(&mut self, health_check: &HealthCheck) {
        if health_check.status == HealthStatus::Unhealthy {
            if !health_check.checks.get("ssh").copied().unwrap_or(true) {
                self.create_alert(
                    health_check.xnode_id.clone(),
                    AlertType::SshUnreachable,
                    AlertSeverity::Critical,
                    format!("SSH unreachable on {}", health_check.xnode_id),
                    Some(serde_json::to_value(health_check).unwrap()),
                ).await;
            }

            if !health_check.checks.get("ping").copied().unwrap_or(true) {
                self.create_alert(
                    health_check.xnode_id.clone(),
                    AlertType::ServiceDown,
                    AlertSeverity::Critical,
                    format!("xNode {} is unreachable", health_check.xnode_id),
                    Some(serde_json::to_value(health_check).unwrap()),
                ).await;
            }
        }
    }

    async fn check_metrics_alerts(&mut self, metrics: &ResourceMetrics) {
        // CPU alerts
        if metrics.cpu_percent >= self.config.cpu_critical_threshold {
            self.create_alert(
                metrics.xnode_id.clone(),
                AlertType::HighCpu,
                AlertSeverity::Critical,
                format!("Critical CPU usage: {:.1}%", metrics.cpu_percent),
                Some(serde_json::to_value(metrics).unwrap()),
            ).await;
        } else if metrics.cpu_percent >= self.config.cpu_warning_threshold {
            self.create_alert(
                metrics.xnode_id.clone(),
                AlertType::HighCpu,
                AlertSeverity::Warning,
                format!("High CPU usage: {:.1}%", metrics.cpu_percent),
                Some(serde_json::to_value(metrics).unwrap()),
            ).await;
        }

        // Memory alerts
        if metrics.memory_percent >= self.config.memory_critical_threshold {
            self.create_alert(
                metrics.xnode_id.clone(),
                AlertType::HighMemory,
                AlertSeverity::Critical,
                format!("Critical memory usage: {:.1}%", metrics.memory_percent),
                Some(serde_json::to_value(metrics).unwrap()),
            ).await;
        } else if metrics.memory_percent >= self.config.memory_warning_threshold {
            self.create_alert(
                metrics.xnode_id.clone(),
                AlertType::HighMemory,
                AlertSeverity::Warning,
                format!("High memory usage: {:.1}%", metrics.memory_percent),
                Some(serde_json::to_value(metrics).unwrap()),
            ).await;
        }

        // Disk alerts
        if metrics.disk_percent >= self.config.disk_critical_threshold {
            self.create_alert(
                metrics.xnode_id.clone(),
                AlertType::LowDisk,
                AlertSeverity::Critical,
                format!("Critical disk usage: {:.1}%", metrics.disk_percent),
                Some(serde_json::to_value(metrics).unwrap()),
            ).await;
        } else if metrics.disk_percent >= self.config.disk_warning_threshold {
            self.create_alert(
                metrics.xnode_id.clone(),
                AlertType::LowDisk,
                AlertSeverity::Warning,
                format!("High disk usage: {:.1}%", metrics.disk_percent),
                Some(serde_json::to_value(metrics).unwrap()),
            ).await;
        }
    }

    async fn create_alert(
        &mut self,
        xnode_id: String,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: String,
        metadata: Option<serde_json::Value>,
    ) {
        // Check if similar alert already exists (prevent spam)
        if self.alert_store.has_similar_alert(&xnode_id, alert_type) {
            return;
        }

        let mut alert = Alert::new(xnode_id.clone(), alert_type, severity, message);
        if let Some(metadata) = metadata {
            alert = alert.with_metadata(metadata);
        }

        // Deliver alert
        if let Err(e) = self.alert_manager.deliver_alert(&alert).await {
            eprintln!("Failed to deliver alert: {}", e);
        }

        // Store alert
        self.alert_store.add_alert(alert);

        // Auto-remediation
        if self.config.auto_restart_on_failure && alert_type == AlertType::ServiceDown {
            eprintln!("Auto-remediation triggered for {}", xnode_id);
            // Would trigger restart here
        }
    }

    pub fn acknowledge_alert(&mut self, alert_id: &str) -> bool {
        self.alert_store.acknowledge_alert(alert_id)
    }

    pub fn resolve_alert(&mut self, alert_id: &str) -> bool {
        self.alert_store.resolve_alert(alert_id)
    }

    pub fn get_xnode_status(&self, xnode_id: &str) -> XNodeStatus {
        let recent_health: Vec<_> = self
            .health_history
            .get(xnode_id)
            .map(|h| h.iter().rev().take(10).rev().cloned().collect())
            .unwrap_or_default();

        let recent_metrics: Vec<_> = self
            .metrics_history
            .get(xnode_id)
            .map(|m| m.iter().rev().take(10).rev().cloned().collect())
            .unwrap_or_default();

        let active_alerts = self.alert_store.get_alerts_for_xnode(xnode_id);

        XNodeStatus {
            xnode_id: xnode_id.to_string(),
            current_health: recent_health.last().cloned(),
            current_metrics: recent_metrics.last().cloned(),
            active_alerts: active_alerts.into_iter().cloned().collect(),
            health_history: recent_health,
            metrics_history: recent_metrics,
        }
    }

    pub fn get_dashboard_data(&self) -> DashboardData {
        let all_xnodes: Vec<String> = self
            .health_history
            .keys()
            .chain(self.metrics_history.keys())
            .cloned()
            .collect::<std::collections::HashSet<_>>()
            .into_iter()
            .collect();

        let healthy_count = all_xnodes
            .iter()
            .filter(|xid| {
                self.health_history
                    .get(*xid)
                    .and_then(|h| h.last())
                    .map(|h| h.status == HealthStatus::Healthy)
                    .unwrap_or(false)
            })
            .count();

        let active_alerts = self.alert_store.get_active_alerts();
        let critical_alerts = active_alerts
            .iter()
            .filter(|a| a.severity == AlertSeverity::Critical)
            .count();
        let warning_alerts = active_alerts
            .iter()
            .filter(|a| a.severity == AlertSeverity::Warning)
            .count();

        let recent_checks: HashMap<String, HealthCheck> = all_xnodes
            .iter()
            .filter_map(|xid| {
                self.health_history
                    .get(xid)
                    .and_then(|h| h.last())
                    .map(|h| (xid.clone(), h.clone()))
            })
            .collect();

        DashboardData {
            total_xnodes: all_xnodes.len(),
            healthy_xnodes: healthy_count,
            unhealthy_xnodes: all_xnodes.len() - healthy_count,
            critical_alerts,
            warning_alerts,
            active_alerts: self.alert_store.get_all_alerts().into_iter().cloned().collect(),
            recent_checks,
        }
    }

    pub fn get_config(&self) -> &MonitoringConfig {
        &self.config
    }

    pub fn get_config_mut(&mut self) -> &mut MonitoringConfig {
        &mut self.config
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct XNodeStatus {
    pub xnode_id: String,
    pub current_health: Option<HealthCheck>,
    pub current_metrics: Option<ResourceMetrics>,
    pub active_alerts: Vec<Alert>,
    pub health_history: Vec<HealthCheck>,
    pub metrics_history: Vec<ResourceMetrics>,
}

#[derive(Debug, Clone, Serialize)]
pub struct DashboardData {
    pub total_xnodes: usize,
    pub healthy_xnodes: usize,
    pub unhealthy_xnodes: usize,
    pub critical_alerts: usize,
    pub warning_alerts: usize,
    pub active_alerts: Vec<Alert>,
    pub recent_checks: HashMap<String, HealthCheck>,
}
