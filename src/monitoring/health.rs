use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{Duration, Instant};
use tokio::process::Command;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Unhealthy,
    Unknown,
}

impl std::fmt::Display for HealthStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HealthStatus::Healthy => write!(f, "healthy"),
            HealthStatus::Degraded => write!(f, "degraded"),
            HealthStatus::Unhealthy => write!(f, "unhealthy"),
            HealthStatus::Unknown => write!(f, "unknown"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheck {
    pub xnode_id: String,
    pub timestamp: String,
    pub status: HealthStatus,
    pub checks: HashMap<String, bool>,
    pub response_times: HashMap<String, f64>,
    pub error_messages: Vec<String>,
}

impl HealthCheck {
    pub fn new(xnode_id: String) -> Self {
        Self {
            xnode_id,
            timestamp: chrono::Utc::now().to_rfc3339(),
            status: HealthStatus::Unknown,
            checks: HashMap::new(),
            response_times: HashMap::new(),
            error_messages: Vec::new(),
        }
    }
}

pub struct HealthChecker {
    pub ping_timeout: Duration,
    pub ssh_timeout: Duration,
    pub http_timeout: Duration,
}

impl Default for HealthChecker {
    fn default() -> Self {
        Self {
            ping_timeout: Duration::from_secs(5),
            ssh_timeout: Duration::from_secs(10),
            http_timeout: Duration::from_secs(10),
        }
    }
}

impl HealthChecker {
    pub fn new(ping_timeout: u64, ssh_timeout: u64, http_timeout: u64) -> Self {
        Self {
            ping_timeout: Duration::from_secs(ping_timeout),
            ssh_timeout: Duration::from_secs(ssh_timeout),
            http_timeout: Duration::from_secs(http_timeout),
        }
    }

    pub async fn check_health(
        &self,
        xnode_id: String,
        ip_address: Option<&str>,
        has_webserver: bool,
    ) -> HealthCheck {
        let mut health_check = HealthCheck::new(xnode_id);

        let Some(ip) = ip_address else {
            health_check.error_messages.push("No IP address available".to_string());
            health_check.status = HealthStatus::Unknown;
            return health_check;
        };

        // Perform ping check
        self.check_ping(&mut health_check, ip).await;

        // Perform SSH check
        self.check_ssh(&mut health_check, ip).await;

        // Perform HTTP check if webserver is configured
        if has_webserver {
            self.check_http(&mut health_check, ip).await;
        }

        // Determine overall status
        health_check.status = self.determine_status(&health_check.checks);

        health_check
    }

    async fn check_ping(&self, health_check: &mut HealthCheck, ip: &str) {
        let start = Instant::now();

        let result = tokio::time::timeout(
            self.ping_timeout + Duration::from_secs(1),
            Command::new("ping")
                .args(["-c", "1", "-W", &self.ping_timeout.as_secs().to_string(), ip])
                .output()
        ).await;

        let elapsed = start.elapsed().as_millis() as f64;
        health_check.response_times.insert("ping".to_string(), elapsed);

        match result {
            Ok(Ok(output)) => {
                let success = output.status.success();
                health_check.checks.insert("ping".to_string(), success);
                if !success {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    health_check.error_messages.push(format!("Ping failed: {}", stderr.chars().take(100).collect::<String>()));
                }
            }
            Ok(Err(e)) => {
                health_check.checks.insert("ping".to_string(), false);
                health_check.error_messages.push(format!("Ping error: {}", e));
            }
            Err(_) => {
                health_check.checks.insert("ping".to_string(), false);
                health_check.error_messages.push("Ping timeout".to_string());
            }
        }
    }

    async fn check_ssh(&self, health_check: &mut HealthCheck, ip: &str) {
        let start = Instant::now();

        let result = tokio::time::timeout(
            self.ssh_timeout + Duration::from_secs(1),
            Command::new("nc")
                .args(["-z", "-w", &self.ssh_timeout.as_secs().to_string(), ip, "22"])
                .output()
        ).await;

        let elapsed = start.elapsed().as_millis() as f64;
        health_check.response_times.insert("ssh".to_string(), elapsed);

        match result {
            Ok(Ok(output)) => {
                let success = output.status.success();
                health_check.checks.insert("ssh".to_string(), success);
                if !success {
                    health_check.error_messages.push("SSH port unreachable".to_string());
                }
            }
            Ok(Err(e)) => {
                health_check.checks.insert("ssh".to_string(), false);
                health_check.error_messages.push(format!("SSH check error: {}", e));
            }
            Err(_) => {
                health_check.checks.insert("ssh".to_string(), false);
                health_check.error_messages.push("SSH check timeout".to_string());
            }
        }
    }

    async fn check_http(&self, health_check: &mut HealthCheck, ip: &str) {
        let start = Instant::now();
        let url = format!("http://{}", ip);

        let client = reqwest::Client::builder()
            .timeout(self.http_timeout)
            .build()
            .unwrap();

        match client.get(&url).send().await {
            Ok(response) => {
                let elapsed = start.elapsed().as_millis() as f64;
                health_check.response_times.insert("http".to_string(), elapsed);

                let status_code = response.status().as_u16();
                let success = status_code < 500;
                health_check.checks.insert("http".to_string(), success);

                if !success {
                    health_check.error_messages.push(format!("HTTP returned {}", status_code));
                }
            }
            Err(e) => {
                let elapsed = start.elapsed().as_millis() as f64;
                health_check.response_times.insert("http".to_string(), elapsed);
                health_check.checks.insert("http".to_string(), false);
                health_check.error_messages.push(format!("HTTP check error: {}", e));
            }
        }
    }

    fn determine_status(&self, checks: &HashMap<String, bool>) -> HealthStatus {
        if checks.is_empty() {
            return HealthStatus::Unknown;
        }

        let all_passed = checks.values().all(|&v| v);
        let any_passed = checks.values().any(|&v| v);

        if all_passed {
            HealthStatus::Healthy
        } else if any_passed {
            HealthStatus::Degraded
        } else {
            HealthStatus::Unhealthy
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_health_status_display() {
        assert_eq!(HealthStatus::Healthy.to_string(), "healthy");
        assert_eq!(HealthStatus::Degraded.to_string(), "degraded");
        assert_eq!(HealthStatus::Unhealthy.to_string(), "unhealthy");
        assert_eq!(HealthStatus::Unknown.to_string(), "unknown");
    }

    #[test]
    fn test_determine_status() {
        let checker = HealthChecker::default();
        let mut checks = HashMap::new();

        // All pass
        checks.insert("ping".to_string(), true);
        checks.insert("ssh".to_string(), true);
        assert_eq!(checker.determine_status(&checks), HealthStatus::Healthy);

        // Some pass
        checks.insert("http".to_string(), false);
        assert_eq!(checker.determine_status(&checks), HealthStatus::Degraded);

        // None pass
        checks.clear();
        checks.insert("ping".to_string(), false);
        checks.insert("ssh".to_string(), false);
        assert_eq!(checker.determine_status(&checks), HealthStatus::Unhealthy);

        // Empty
        checks.clear();
        assert_eq!(checker.determine_status(&checks), HealthStatus::Unknown);
    }
}
