/// Equinix Metal API Client
///
/// Provides API client for Equinix Metal's bare metal infrastructure platform.
/// Uses X-Auth-Token header authentication.

use super::client::ApiClient;
use super::error::ApiResult;

/// Equinix Metal API client
pub struct EquinixMetalClient {
    client: ApiClient,
}

impl EquinixMetalClient {
    /// Create a new Equinix Metal API client
    ///
    /// # Arguments
    ///
    /// * `api_key` - Equinix Metal API token
    ///
    /// # Example
    ///
    /// ```no_run
    /// use capsule::api::equinix::EquinixMetalClient;
    ///
    /// let client = EquinixMetalClient::new("your-api-token").unwrap();
    /// ```
    pub fn new(api_key: impl Into<String>) -> ApiResult<Self> {
        let client = ApiClient::builder("https://api.equinix.com/metal/v1")
            .api_key_auth("X-Auth-Token", api_key)
            .build()?;

        Ok(Self { client })
    }

    /// Get reference to underlying API client
    pub fn client(&self) -> &ApiClient {
        &self.client
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let client = EquinixMetalClient::new("test-token");
        assert!(client.is_ok());
    }
}
