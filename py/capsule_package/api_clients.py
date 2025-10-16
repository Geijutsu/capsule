#!/usr/bin/env python3
"""API Client Module for Provider Integrations

Provides base API client functionality for making HTTP requests to various
cloud and bare metal provider APIs with proper error handling, retries,
rate limiting, and logging.
"""

import logging
import time
from typing import Dict, Any, Optional, Callable
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[dict] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class AuthenticationError(APIError):
    """Raised when API authentication fails"""
    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded"""
    pass


class ResourceNotFoundError(APIError):
    """Raised when requested resource is not found"""
    pass


class APIClient:
    """Base API client with common functionality for provider APIs

    Features:
    - Automatic retries with exponential backoff
    - Rate limit handling
    - Request/response logging
    - Session management with connection pooling
    - Standardized error handling
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_delay: float = 1.0,
        headers: Optional[Dict[str, str]] = None
    ):
        """Initialize API client

        Args:
            base_url: Base URL for API endpoint
            api_key: API authentication key/token
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            rate_limit_delay: Delay in seconds when rate limited
            headers: Additional HTTP headers to include
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay

        # Initialize session with retry strategy
        self.session = self._create_session()

        # Setup default headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if headers:
            self.headers.update(headers)

        # Add authentication header if API key provided
        if self.api_key:
            self._add_auth_header()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry configuration"""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _add_auth_header(self):
        """Add authentication header (override in subclasses for provider-specific auth)"""
        self.headers['Authorization'] = f'Bearer {self.api_key}'

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint"""
        return urljoin(self.base_url + '/', endpoint.lstrip('/'))

    def _handle_response(self, response: requests.Response) -> dict:
        """Handle API response and raise appropriate exceptions

        Args:
            response: Response object from requests

        Returns:
            Parsed JSON response data

        Raises:
            AuthenticationError: On authentication failure (401, 403)
            RateLimitError: On rate limit exceeded (429)
            ResourceNotFoundError: On resource not found (404)
            APIError: On other API errors
        """
        try:
            response.raise_for_status()

            # Handle empty responses
            if not response.content:
                return {}

            return response.json()

        except requests.exceptions.HTTPError as e:
            status_code = response.status_code

            try:
                error_data = response.json()
            except:
                error_data = {'error': response.text}

            # Handle specific error codes
            if status_code in (401, 403):
                raise AuthenticationError(
                    f"Authentication failed: {error_data}",
                    status_code=status_code,
                    response=error_data
                )
            elif status_code == 429:
                raise RateLimitError(
                    f"Rate limit exceeded: {error_data}",
                    status_code=status_code,
                    response=error_data
                )
            elif status_code == 404:
                raise ResourceNotFoundError(
                    f"Resource not found: {error_data}",
                    status_code=status_code,
                    response=error_data
                )
            else:
                raise APIError(
                    f"API error ({status_code}): {error_data}",
                    status_code=status_code,
                    response=error_data
                )

    def _handle_rate_limiting(self, func: Callable, *args, **kwargs) -> Any:
        """Wrapper to handle rate limiting with retries

        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result
        """
        max_rate_limit_retries = 3

        for attempt in range(max_rate_limit_retries):
            try:
                return func(*args, **kwargs)
            except RateLimitError as e:
                if attempt < max_rate_limit_retries - 1:
                    wait_time = self.rate_limit_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_rate_limit_retries}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Rate limit exceeded after {max_rate_limit_retries} retries")
                    raise

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        **kwargs
    ) -> dict:
        """Make HTTP request to API

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path
            data: Request body data (will be JSON encoded)
            params: URL query parameters
            headers: Additional headers for this request
            **kwargs: Additional arguments for requests

        Returns:
            Parsed JSON response

        Raises:
            APIError: On request failure
        """
        url = self._build_url(endpoint)

        # Merge headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        # Log request
        logger.debug(f"{method} {url}")
        if data:
            logger.debug(f"Request data: {data}")

        def _make_request():
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=request_headers,
                    timeout=self.timeout,
                    **kwargs
                )

                result = self._handle_response(response)
                logger.debug(f"Response: {result}")
                return result

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error: {e}")
                raise APIError(f"Failed to connect to {url}: {e}")
            except requests.exceptions.Timeout as e:
                logger.error(f"Request timeout: {e}")
                raise APIError(f"Request timed out: {e}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                raise APIError(f"Request failed: {e}")

        return self._handle_rate_limiting(_make_request)

    def get(self, endpoint: str, params: Optional[dict] = None, **kwargs) -> dict:
        """Make GET request"""
        return self.request('GET', endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: Optional[dict] = None, **kwargs) -> dict:
        """Make POST request"""
        return self.request('POST', endpoint, data=data, **kwargs)

    def put(self, endpoint: str, data: Optional[dict] = None, **kwargs) -> dict:
        """Make PUT request"""
        return self.request('PUT', endpoint, data=data, **kwargs)

    def patch(self, endpoint: str, data: Optional[dict] = None, **kwargs) -> dict:
        """Make PATCH request"""
        return self.request('PATCH', endpoint, data=data, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> dict:
        """Make DELETE request"""
        return self.request('DELETE', endpoint, **kwargs)

    def close(self):
        """Close the session"""
        self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class HivelocityAPIClient(APIClient):
    """Hivelocity API client"""

    def __init__(self, api_key: str):
        super().__init__(
            base_url='https://core.hivelocity.net/api/v2',
            api_key=api_key
        )

    def _add_auth_header(self):
        """Hivelocity uses X-API-Key header"""
        self.headers['X-API-Key'] = self.api_key


class DigitalOceanAPIClient(APIClient):
    """DigitalOcean API client"""

    def __init__(self, api_key: str):
        super().__init__(
            base_url='https://api.digitalocean.com/v2',
            api_key=api_key
        )

    def _add_auth_header(self):
        """DigitalOcean uses Bearer token"""
        self.headers['Authorization'] = f'Bearer {self.api_key}'


class VultrAPIClient(APIClient):
    """Vultr API client"""

    def __init__(self, api_key: str):
        super().__init__(
            base_url='https://api.vultr.com/v2',
            api_key=api_key
        )

    def _add_auth_header(self):
        """Vultr uses Bearer token"""
        self.headers['Authorization'] = f'Bearer {self.api_key}'


class EquinixMetalAPIClient(APIClient):
    """Equinix Metal API client"""

    def __init__(self, api_key: str):
        super().__init__(
            base_url='https://api.equinix.com/metal/v1',
            api_key=api_key
        )

    def _add_auth_header(self):
        """Equinix Metal uses X-Auth-Token header"""
        self.headers['X-Auth-Token'] = self.api_key
