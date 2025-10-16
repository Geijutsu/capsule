/// Base API Client
///
/// Provides base API client functionality for making HTTP requests to various
/// cloud and bare metal provider APIs with proper error handling, retries,
/// rate limiting, and logging.

use reqwest::{Client, Method, Response, StatusCode};
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::collections::HashMap;
use std::time::Duration;
use tokio::time::sleep;

use super::error::{ApiError, ApiResult};

/// Authentication method for API clients
#[derive(Debug, Clone)]
pub enum AuthMethod {
    /// Bearer token authentication
    Bearer(String),
    /// API key in custom header
    ApiKey { header: String, key: String },
    /// No authentication
    None,
}

/// Base API client with common functionality for provider APIs
///
/// Features:
/// - Automatic retries with exponential backoff
/// - Rate limit handling
/// - Request/response logging
/// - Standardized error handling
pub struct ApiClient {
    client: Client,
    base_url: String,
    auth: AuthMethod,
    timeout: Duration,
    max_retries: u32,
    rate_limit_delay: Duration,
    default_headers: HashMap<String, String>,
}

impl ApiClient {
    /// Create a new API client builder
    pub fn builder(base_url: impl Into<String>) -> ApiClientBuilder {
        ApiClientBuilder::new(base_url)
    }

    /// Build full URL from endpoint
    fn build_url(&self, endpoint: &str) -> String {
        let base = self.base_url.trim_end_matches('/');
        let endpoint = endpoint.trim_start_matches('/');
        format!("{}/{}", base, endpoint)
    }

    /// Add authentication headers to the request
    fn add_auth_headers(&self, headers: &mut HashMap<String, String>) {
        match &self.auth {
            AuthMethod::Bearer(token) => {
                headers.insert("Authorization".to_string(), format!("Bearer {}", token));
            }
            AuthMethod::ApiKey { header, key } => {
                headers.insert(header.clone(), key.clone());
            }
            AuthMethod::None => {}
        }
    }

    /// Handle API response and convert to appropriate error
    async fn handle_response<T: DeserializeOwned>(
        &self,
        response: Response,
    ) -> ApiResult<T> {
        let status = response.status();

        // Handle different status codes
        if status.is_success() {
            // Handle empty responses
            let text = response.text().await?;
            if text.is_empty() {
                // Return empty JSON object for empty responses
                return serde_json::from_str("{}").map_err(|e| {
                    ApiError::JsonParse(format!("Failed to parse empty response: {}", e))
                });
            }

            serde_json::from_str(&text).map_err(|e| {
                ApiError::JsonParse(format!("Failed to parse response: {}", e))
            })
        } else {
            // Try to get error details from response
            let error_text = response.text().await.unwrap_or_default();
            let error_data: Option<Value> = serde_json::from_str(&error_text).ok();
            let error_message = error_data
                .as_ref()
                .and_then(|v| v.get("error"))
                .and_then(|v| v.as_str())
                .or_else(|| error_data.as_ref().and_then(|v| v.get("message")).and_then(|v| v.as_str()))
                .unwrap_or(&error_text);

            match status {
                StatusCode::UNAUTHORIZED | StatusCode::FORBIDDEN => {
                    Err(ApiError::authentication(error_message, Some(status.as_u16())))
                }
                StatusCode::TOO_MANY_REQUESTS => {
                    Err(ApiError::rate_limit(error_message, Some(status.as_u16())))
                }
                StatusCode::NOT_FOUND => {
                    Err(ApiError::resource_not_found(error_message, Some(status.as_u16())))
                }
                _ => Err(ApiError::general(error_message, status.as_u16())),
            }
        }
    }

    /// Execute request with rate limit handling
    async fn execute_with_rate_limiting<F, T, Fut>(
        &self,
        mut func: F,
    ) -> ApiResult<T>
    where
        F: FnMut() -> Fut,
        Fut: std::future::Future<Output = ApiResult<T>>,
    {
        const MAX_RATE_LIMIT_RETRIES: u32 = 3;

        for attempt in 0..MAX_RATE_LIMIT_RETRIES {
            match func().await {
                Ok(result) => return Ok(result),
                Err(e) if e.is_rate_limit() => {
                    if attempt < MAX_RATE_LIMIT_RETRIES - 1 {
                        let wait_time = self.rate_limit_delay * 2_u32.pow(attempt);
                        log::warn!(
                            "Rate limited, waiting {:?} before retry {}/{}",
                            wait_time,
                            attempt + 1,
                            MAX_RATE_LIMIT_RETRIES
                        );
                        sleep(wait_time).await;
                    } else {
                        log::error!(
                            "Rate limit exceeded after {} retries",
                            MAX_RATE_LIMIT_RETRIES
                        );
                        return Err(e);
                    }
                }
                Err(e) => return Err(e),
            }
        }

        unreachable!()
    }

    /// Make HTTP request to API
    ///
    /// # Arguments
    ///
    /// * `method` - HTTP method
    /// * `endpoint` - API endpoint path
    /// * `data` - Optional request body (will be JSON encoded)
    /// * `params` - Optional URL query parameters
    /// * `headers` - Optional additional headers
    pub async fn request<T: DeserializeOwned>(
        &self,
        method: Method,
        endpoint: &str,
        data: Option<&Value>,
        params: Option<&HashMap<String, String>>,
        headers: Option<HashMap<String, String>>,
    ) -> ApiResult<T> {
        let url = self.build_url(endpoint);

        // Merge headers
        let mut request_headers = self.default_headers.clone();
        self.add_auth_headers(&mut request_headers);
        if let Some(h) = headers {
            request_headers.extend(h);
        }

        log::debug!("{} {}", method, url);
        if let Some(d) = data {
            log::debug!("Request data: {}", d);
        }

        let make_request = || async {
            let mut request_builder = self.client.request(method.clone(), &url).timeout(self.timeout);

            // Add headers
            for (key, value) in &request_headers {
                request_builder = request_builder.header(key, value);
            }

            // Add query parameters
            if let Some(p) = params {
                request_builder = request_builder.query(p);
            }

            // Add body data
            if let Some(d) = data {
                request_builder = request_builder.json(d);
            }

            let response = request_builder.send().await?;
            let result: T = self.handle_response(response).await?;
            log::debug!("Response received successfully");
            Ok(result)
        };

        self.execute_with_rate_limiting(make_request).await
    }

    /// Make GET request
    pub async fn get<T: DeserializeOwned>(
        &self,
        endpoint: &str,
        params: Option<&HashMap<String, String>>,
    ) -> ApiResult<T> {
        self.request(Method::GET, endpoint, None, params, None).await
    }

    /// Make POST request
    pub async fn post<T: DeserializeOwned>(
        &self,
        endpoint: &str,
        data: Option<&Value>,
    ) -> ApiResult<T> {
        self.request(Method::POST, endpoint, data, None, None).await
    }

    /// Make PUT request
    pub async fn put<T: DeserializeOwned>(
        &self,
        endpoint: &str,
        data: Option<&Value>,
    ) -> ApiResult<T> {
        self.request(Method::PUT, endpoint, data, None, None).await
    }

    /// Make PATCH request
    pub async fn patch<T: DeserializeOwned>(
        &self,
        endpoint: &str,
        data: Option<&Value>,
    ) -> ApiResult<T> {
        self.request(Method::PATCH, endpoint, data, None, None).await
    }

    /// Make DELETE request
    pub async fn delete<T: DeserializeOwned>(&self, endpoint: &str) -> ApiResult<T> {
        self.request(Method::DELETE, endpoint, None, None, None).await
    }
}

/// Builder for API client
pub struct ApiClientBuilder {
    base_url: String,
    auth: AuthMethod,
    timeout: Duration,
    max_retries: u32,
    rate_limit_delay: Duration,
    headers: HashMap<String, String>,
}

impl ApiClientBuilder {
    /// Create a new builder
    pub fn new(base_url: impl Into<String>) -> Self {
        let mut headers = HashMap::new();
        headers.insert("Content-Type".to_string(), "application/json".to_string());
        headers.insert("Accept".to_string(), "application/json".to_string());

        Self {
            base_url: base_url.into(),
            auth: AuthMethod::None,
            timeout: Duration::from_secs(30),
            max_retries: 3,
            rate_limit_delay: Duration::from_secs(1),
            headers,
        }
    }

    /// Set authentication method
    pub fn auth(mut self, auth: AuthMethod) -> Self {
        self.auth = auth;
        self
    }

    /// Set bearer token authentication
    pub fn bearer_auth(mut self, token: impl Into<String>) -> Self {
        self.auth = AuthMethod::Bearer(token.into());
        self
    }

    /// Set API key authentication
    pub fn api_key_auth(mut self, header: impl Into<String>, key: impl Into<String>) -> Self {
        self.auth = AuthMethod::ApiKey {
            header: header.into(),
            key: key.into(),
        };
        self
    }

    /// Set request timeout
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    /// Set maximum number of retries
    pub fn max_retries(mut self, max_retries: u32) -> Self {
        self.max_retries = max_retries;
        self
    }

    /// Set rate limit delay
    pub fn rate_limit_delay(mut self, delay: Duration) -> Self {
        self.rate_limit_delay = delay;
        self
    }

    /// Add a custom header
    pub fn header(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.headers.insert(key.into(), value.into());
        self
    }

    /// Build the API client
    pub fn build(self) -> ApiResult<ApiClient> {
        let client = Client::builder()
            .timeout(self.timeout)
            .build()
            .map_err(|e| ApiError::RequestBuild(e.to_string()))?;

        Ok(ApiClient {
            client,
            base_url: self.base_url,
            auth: self.auth,
            timeout: self.timeout,
            max_retries: self.max_retries,
            rate_limit_delay: self.rate_limit_delay,
            default_headers: self.headers,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_build_url() {
        let client = ApiClient::builder("https://api.example.com")
            .build()
            .unwrap();

        assert_eq!(
            client.build_url("/v1/resources"),
            "https://api.example.com/v1/resources"
        );
        assert_eq!(
            client.build_url("v1/resources"),
            "https://api.example.com/v1/resources"
        );
    }

    #[test]
    fn test_builder_pattern() {
        let client = ApiClient::builder("https://api.example.com")
            .bearer_auth("test-token")
            .timeout(Duration::from_secs(60))
            .max_retries(5)
            .build()
            .unwrap();

        assert_eq!(client.base_url, "https://api.example.com");
        assert_eq!(client.max_retries, 5);
    }
}
