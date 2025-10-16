/// Hivelocity API Client
///
/// Provides API client for Hivelocity's bare metal hosting platform.
/// Uses X-API-Key header authentication.

use super::client::ApiClient;
use super::error::ApiResult;

/// Hivelocity API client
pub struct HivelocityClient {
    client: ApiClient,
}

impl HivelocityClient {
    /// Create a new Hivelocity API client
    ///
    /// # Arguments
    ///
    /// * `api_key` - Hivelocity API key
    ///
    /// # Example
    ///
    /// ```no_run
    /// use capsule::api::hivelocity::HivelocityClient;
    ///
    /// let client = HivelocityClient::new("your-api-key").unwrap();
    /// ```
    pub fn new(api_key: impl Into<String>) -> ApiResult<Self> {
        let client = ApiClient::builder("https://core.hivelocity.net/api/v2")
            .api_key_auth("X-API-Key", api_key)
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
        let client = HivelocityClient::new("test-key");
        assert!(client.is_ok());
    }
}
