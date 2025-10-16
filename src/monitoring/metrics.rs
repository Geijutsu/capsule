use serde::{Deserialize, Serialize};
use tokio::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceMetrics {
    pub xnode_id: String,
    pub timestamp: String,
    pub cpu_percent: f64,
    pub memory_percent: f64,
    pub disk_percent: f64,
    pub network_in_mbps: f64,
    pub network_out_mbps: f64,
    pub load_average: (f64, f64, f64),
}

impl ResourceMetrics {
    pub fn new(xnode_id: String) -> Self {
        Self {
            xnode_id,
            timestamp: chrono::Utc::now().to_rfc3339(),
            cpu_percent: 0.0,
            memory_percent: 0.0,
            disk_percent: 0.0,
            network_in_mbps: 0.0,
            network_out_mbps: 0.0,
            load_average: (0.0, 0.0, 0.0),
        }
    }
}

pub struct MetricsCollector {
    pub ssh_timeout: std::time::Duration,
}

impl Default for MetricsCollector {
    fn default() -> Self {
        Self {
            ssh_timeout: std::time::Duration::from_secs(10),
        }
    }
}

impl MetricsCollector {
    pub fn new(ssh_timeout: u64) -> Self {
        Self {
            ssh_timeout: std::time::Duration::from_secs(ssh_timeout),
        }
    }

    pub async fn collect_metrics(
        &self,
        xnode_id: String,
        ip_address: Option<&str>,
        ssh_key_path: Option<&str>,
    ) -> Option<ResourceMetrics> {
        let ip = ip_address?;
        let ssh_key = ssh_key_path.unwrap_or("~/.ssh/id_rsa");

        // Build SSH command to collect all metrics in one call
        let cmd = format!(
            "top -bn1 | grep 'Cpu(s)' | awk '{{print $2}}' && \
             free | grep Mem | awk '{{print ($3/$2) * 100}}' && \
             df -h / | tail -1 | awk '{{print $5}}' && \
             uptime"
        );

        let ssh_cmd = format!(
            "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i {} root@{} '{}'",
            ssh_key, ip, cmd
        );

        let result = tokio::time::timeout(
            self.ssh_timeout,
            Command::new("sh")
                .arg("-c")
                .arg(&ssh_cmd)
                .output()
        ).await;

        match result {
            Ok(Ok(output)) if output.status.success() => {
                self.parse_metrics_output(xnode_id, &output.stdout)
            }
            _ => None,
        }
    }

    fn parse_metrics_output(&self, xnode_id: String, stdout: &[u8]) -> Option<ResourceMetrics> {
        let output = String::from_utf8_lossy(stdout);
        let lines: Vec<&str> = output.trim().split('\n').collect();

        if lines.len() < 4 {
            return None;
        }

        // Parse CPU percentage
        let cpu_percent = lines[0]
            .trim()
            .replace('%', "")
            .parse::<f64>()
            .ok()?;

        // Parse memory percentage
        let memory_percent = lines[1]
            .trim()
            .parse::<f64>()
            .ok()?;

        // Parse disk percentage
        let disk_percent = lines[2]
            .trim()
            .replace('%', "")
            .parse::<f64>()
            .ok()?;

        // Parse load average from uptime output
        let load_average = self.parse_load_average(lines[3])?;

        Some(ResourceMetrics {
            xnode_id,
            timestamp: chrono::Utc::now().to_rfc3339(),
            cpu_percent,
            memory_percent,
            disk_percent,
            network_in_mbps: 0.0,  // Would need additional monitoring
            network_out_mbps: 0.0,
            load_average,
        })
    }

    fn parse_load_average(&self, uptime_line: &str) -> Option<(f64, f64, f64)> {
        // Extract load average from uptime output
        // Example: " 12:34:56 up 1 day,  2:34,  1 user,  load average: 0.52, 0.58, 0.59"
        let parts: Vec<&str> = uptime_line.split("load average:").collect();
        if parts.len() != 2 {
            return None;
        }

        let load_parts: Vec<&str> = parts[1].trim().split(',').collect();
        if load_parts.len() < 3 {
            return None;
        }

        let load1 = load_parts[0].trim().parse::<f64>().ok()?;
        let load5 = load_parts[1].trim().parse::<f64>().ok()?;
        let load15 = load_parts[2].trim().parse::<f64>().ok()?;

        Some((load1, load5, load15))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_load_average() {
        let collector = MetricsCollector::default();

        let uptime_line = " 12:34:56 up 1 day,  2:34,  1 user,  load average: 0.52, 0.58, 0.59";
        let result = collector.parse_load_average(uptime_line);
        assert_eq!(result, Some((0.52, 0.58, 0.59)));

        let invalid_line = "no load average here";
        let result = collector.parse_load_average(invalid_line);
        assert_eq!(result, None);
    }

    #[test]
    fn test_parse_metrics_output() {
        let collector = MetricsCollector::default();

        let output = b"75.5\n80.2\n85%\n 12:34:56 up 1 day,  2:34,  1 user,  load average: 0.52, 0.58, 0.59";
        let result = collector.parse_metrics_output("test-node".to_string(), output);

        assert!(result.is_some());
        let metrics = result.unwrap();
        assert_eq!(metrics.xnode_id, "test-node");
        assert_eq!(metrics.cpu_percent, 75.5);
        assert_eq!(metrics.memory_percent, 80.2);
        assert_eq!(metrics.disk_percent, 85.0);
        assert_eq!(metrics.load_average, (0.52, 0.58, 0.59));
    }
}
