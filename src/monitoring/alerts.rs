use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use anyhow::Result;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AlertSeverity {
    Info,
    Warning,
    Critical,
}

impl std::fmt::Display for AlertSeverity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AlertSeverity::Info => write!(f, "info"),
            AlertSeverity::Warning => write!(f, "warning"),
            AlertSeverity::Critical => write!(f, "critical"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Hash)]
#[serde(rename_all = "snake_case")]
pub enum AlertType {
    HighCpu,
    HighMemory,
    LowDisk,
    ServiceDown,
    SshUnreachable,
    HttpError,
    CostThreshold,
}

impl std::fmt::Display for AlertType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AlertType::HighCpu => write!(f, "high_cpu"),
            AlertType::HighMemory => write!(f, "high_memory"),
            AlertType::LowDisk => write!(f, "low_disk"),
            AlertType::ServiceDown => write!(f, "service_down"),
            AlertType::SshUnreachable => write!(f, "ssh_unreachable"),
            AlertType::HttpError => write!(f, "http_error"),
            AlertType::CostThreshold => write!(f, "cost_threshold"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alert {
    pub id: String,
    pub xnode_id: String,
    pub alert_type: AlertType,
    pub severity: AlertSeverity,
    pub message: String,
    pub timestamp: String,
    #[serde(default)]
    pub acknowledged: bool,
    #[serde(default)]
    pub resolved: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
}

impl Alert {
    pub fn new(
        xnode_id: String,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: String,
    ) -> Self {
        let timestamp = chrono::Utc::now().to_rfc3339();
        let id = format!("{}_{}_{}",
            xnode_id,
            alert_type,
            chrono::Utc::now().timestamp()
        );

        Self {
            id,
            xnode_id,
            alert_type,
            severity,
            message,
            timestamp,
            acknowledged: false,
            resolved: false,
            metadata: None,
        }
    }

    pub fn with_metadata(mut self, metadata: serde_json::Value) -> Self {
        self.metadata = Some(metadata);
        self
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertDeliveryConfig {
    pub console_alerts: bool,
    pub email_alerts: bool,
    pub webhook_alerts: bool,
    pub slack_alerts: bool,
    pub email_recipients: Vec<String>,
    pub webhook_url: Option<String>,
    pub slack_webhook_url: Option<String>,
}

impl Default for AlertDeliveryConfig {
    fn default() -> Self {
        Self {
            console_alerts: true,
            email_alerts: false,
            webhook_alerts: false,
            slack_alerts: false,
            email_recipients: Vec::new(),
            webhook_url: None,
            slack_webhook_url: None,
        }
    }
}

pub struct AlertManager {
    config: AlertDeliveryConfig,
    client: reqwest::Client,
}

impl AlertManager {
    pub fn new(config: AlertDeliveryConfig) -> Self {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .unwrap();

        Self { config, client }
    }

    pub async fn deliver_alert(&self, alert: &Alert) -> Result<()> {
        if self.config.console_alerts {
            self.deliver_console(alert);
        }

        if self.config.email_alerts && !self.config.email_recipients.is_empty() {
            self.deliver_email(alert).await?;
        }

        if self.config.webhook_alerts {
            if let Some(ref url) = self.config.webhook_url {
                self.deliver_webhook(alert, url).await?;
            }
        }

        if self.config.slack_alerts {
            if let Some(ref url) = self.config.slack_webhook_url {
                self.deliver_slack(alert, url).await?;
            }
        }

        Ok(())
    }

    fn deliver_console(&self, alert: &Alert) {
        use colored::Colorize;

        let severity_str = match alert.severity {
            AlertSeverity::Info => "INFO".blue(),
            AlertSeverity::Warning => "WARNING".yellow(),
            AlertSeverity::Critical => "CRITICAL".red().bold(),
        };

        eprintln!("ALERT [{}] {}", severity_str, alert.message);
    }

    async fn deliver_email(&self, alert: &Alert) -> Result<()> {
        // Placeholder for email delivery
        // In production, this would use an SMTP library or email service API
        eprintln!("Would send email alert: {}", alert.message);
        Ok(())
    }

    async fn deliver_webhook(&self, alert: &Alert, url: &str) -> Result<()> {
        let payload = serde_json::to_value(alert)?;

        match self.client.post(url).json(&payload).send().await {
            Ok(response) => {
                if !response.status().is_success() {
                    eprintln!("Webhook delivery failed: {}", response.status());
                }
            }
            Err(e) => {
                eprintln!("Failed to send webhook alert: {}", e);
            }
        }

        Ok(())
    }

    async fn deliver_slack(&self, alert: &Alert, url: &str) -> Result<()> {
        let color = match alert.severity {
            AlertSeverity::Info => "#36a64f",
            AlertSeverity::Warning => "#ff9900",
            AlertSeverity::Critical => "#ff0000",
        };

        let timestamp = chrono::DateTime::parse_from_rfc3339(&alert.timestamp)
            .map(|dt| dt.timestamp())
            .unwrap_or(0);

        let payload = serde_json::json!({
            "attachments": [{
                "color": color,
                "title": format!("xNode Alert: {}", alert.xnode_id),
                "text": alert.message,
                "fields": [
                    {
                        "title": "Severity",
                        "value": alert.severity.to_string().to_uppercase(),
                        "short": true
                    },
                    {
                        "title": "Type",
                        "value": alert.alert_type.to_string(),
                        "short": true
                    },
                ],
                "footer": "Capsule Monitoring",
                "ts": timestamp
            }]
        });

        match self.client.post(url).json(&payload).send().await {
            Ok(response) => {
                if !response.status().is_success() {
                    eprintln!("Slack delivery failed: {}", response.status());
                }
            }
            Err(e) => {
                eprintln!("Failed to send Slack alert: {}", e);
            }
        }

        Ok(())
    }
}

pub struct AlertStore {
    active_alerts: HashMap<String, Alert>,
}

impl AlertStore {
    pub fn new() -> Self {
        Self {
            active_alerts: HashMap::new(),
        }
    }

    pub fn add_alert(&mut self, alert: Alert) {
        self.active_alerts.insert(alert.id.clone(), alert);
    }

    pub fn get_alert(&self, alert_id: &str) -> Option<&Alert> {
        self.active_alerts.get(alert_id)
    }

    pub fn get_alert_mut(&mut self, alert_id: &str) -> Option<&mut Alert> {
        self.active_alerts.get_mut(alert_id)
    }

    pub fn acknowledge_alert(&mut self, alert_id: &str) -> bool {
        if let Some(alert) = self.active_alerts.get_mut(alert_id) {
            alert.acknowledged = true;
            return true;
        }
        false
    }

    pub fn resolve_alert(&mut self, alert_id: &str) -> bool {
        if let Some(alert) = self.active_alerts.get_mut(alert_id) {
            alert.resolved = true;
            return true;
        }
        false
    }

    pub fn get_active_alerts(&self) -> Vec<&Alert> {
        self.active_alerts
            .values()
            .filter(|a| !a.resolved)
            .collect()
    }

    pub fn get_alerts_for_xnode(&self, xnode_id: &str) -> Vec<&Alert> {
        self.active_alerts
            .values()
            .filter(|a| a.xnode_id == xnode_id && !a.resolved)
            .collect()
    }

    pub fn has_similar_alert(&self, xnode_id: &str, alert_type: AlertType) -> bool {
        self.active_alerts
            .values()
            .any(|a| a.xnode_id == xnode_id && a.alert_type == alert_type && !a.resolved)
    }

    pub fn get_all_alerts(&self) -> Vec<&Alert> {
        self.active_alerts.values().collect()
    }

    pub fn load_from_map(&mut self, alerts: HashMap<String, Alert>) {
        self.active_alerts = alerts;
    }

    pub fn as_map(&self) -> &HashMap<String, Alert> {
        &self.active_alerts
    }
}

impl Default for AlertStore {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_alert_creation() {
        let alert = Alert::new(
            "test-node".to_string(),
            AlertType::HighCpu,
            AlertSeverity::Warning,
            "CPU usage high".to_string(),
        );

        assert_eq!(alert.xnode_id, "test-node");
        assert_eq!(alert.alert_type, AlertType::HighCpu);
        assert_eq!(alert.severity, AlertSeverity::Warning);
        assert!(!alert.acknowledged);
        assert!(!alert.resolved);
    }

    #[test]
    fn test_alert_store() {
        let mut store = AlertStore::new();

        let alert = Alert::new(
            "test-node".to_string(),
            AlertType::HighCpu,
            AlertSeverity::Warning,
            "CPU usage high".to_string(),
        );

        let alert_id = alert.id.clone();
        store.add_alert(alert);

        assert!(store.get_alert(&alert_id).is_some());
        assert_eq!(store.get_active_alerts().len(), 1);

        store.acknowledge_alert(&alert_id);
        assert!(store.get_alert(&alert_id).unwrap().acknowledged);

        store.resolve_alert(&alert_id);
        assert!(store.get_alert(&alert_id).unwrap().resolved);
        assert_eq!(store.get_active_alerts().len(), 0);
    }

    #[test]
    fn test_has_similar_alert() {
        let mut store = AlertStore::new();

        let alert = Alert::new(
            "test-node".to_string(),
            AlertType::HighCpu,
            AlertSeverity::Warning,
            "CPU usage high".to_string(),
        );

        store.add_alert(alert);

        assert!(store.has_similar_alert("test-node", AlertType::HighCpu));
        assert!(!store.has_similar_alert("test-node", AlertType::HighMemory));
        assert!(!store.has_similar_alert("other-node", AlertType::HighCpu));
    }
}
