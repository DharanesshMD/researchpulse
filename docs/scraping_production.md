# Production Scraping: Session Consistency & IP Quality Under Load

When transitioning a scraper from a local prototype to a production environment running continuously under load, websites and API servers will frequently flag, rate-limit, or completely block requests. 

This document details the common issues encountered when scraping at scale and how the ResearchPulse reliability suite solves them.

---

## 1. The Core Challenges of Scraping at Scale

### Session Consistency vs. Session Isolation

A session represents a series of requests originating from the same client. Websites track sessions using two primary vectors:
1. **HTTP State (Cookies/Tokens):** Re-using the same cookie jar simulates a logged-in or persistent visitor.
2. **Network State (IP Address/User-Agent):** Requests from a single IP address with a consistent User-Agent.

*   **The Session Consistency Problem:** If your scraper makes a request, receives cookies, and then switches its IP address but sends the *same cookies*, target websites will instantly identify the requests as coming from the same logical scraper. This is a common footprint.
*   **The Session Isolation Solution:** If an IP is flagged (e.g., you receive an HTTP `429 Too Many Requests` or `403 Forbidden` block), ResearchPulse executes a **Session Reset**. It increments the proxy pool index, clears the cookie jar, and generates a fresh, randomized, realistic browser User-Agent string. This ensures the target site sees a completely new client session.

### IP Quality: Residential vs. Datacenter

Target servers inspect the Autonomous System Number (ASN) of your IP address to classify the traffic source:
*   **Datacenter IPs (Low Quality):** Owned by Amazon AWS, DigitalOcean, Hetzner, etc. These are cheap and fast, but target websites (like Reddit, GitHub, and major news publishers) routinely block datacenter ranges entirely or serve them high volumes of CAPTCHAs.
*   **Residential IPs (High Quality):** Assigned by internet service providers (ISPs) to home internet connections. These are highly trusted and rarely blocked outright, but they are more expensive and have higher latency.

ResearchPulse's proxy layer lets you plug in datacenter or residential proxy lists and rotate them dynamically.

---

## 2. ResearchPulse Reliability Architecture

```
                       [ Scraping Run ]
                              │
                    ( GET or POST Request )
                              │
                    [ httpx.AsyncClient ] 
                 (Current Proxy & User-Agent)
                              │
            ┌─────────────────┴─────────────────┐
     [ HTTP 200/201 ]                    [ 403 / 429 / Timeout / 5xx ]
            │                                   │
      (Scrape Item)                    ( Trigger Backoff )
            │                                   │
       [ Success ]                 [ Retry Limit Reached? ]
                                      ┌─────────┴─────────┐
                                    [ No ]              [ Yes ]
                                      │                    │
                              ( Rotate Session )      [ Log Failure ]
                           * New Proxy IP             * Return empty
                           * New Browser User-Agent   * Continue run
                           * Clear Cookies/State
                                      │
                               ( Retry Request )
```

### Automatic Exponential Backoff & Jitter

When a request fails, hammering the server immediately makes rate-limits tighter. ResearchPulse uses the `tenacity` library to retry requests using:
1. **Exponential Backoff:** The delay increases exponentially after each failure (e.g., 2s, 4s, 8s, 16s).
2. **Random Jitter:** Random noise is added to the delay (e.g., 4.2s instead of 4.0s). This prevents multiple scraper threads from hitting the target server in synchronized waves.

### Supported Retryable Errors

ResearchPulse automatically retries and triggers proxy rotation on:
*   **Network Errors:** Connection timeouts, DNS failures, read/write timeouts.
*   **Rate Limits:** `429 Too Many Requests` response code.
*   **Access Blocks:** `403 Forbidden` response code (often returned by Cloudflare/Akamai when blocking bot IPs).
*   **Server Failures:** `500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`.

---

## 3. Configuration Guide

To enable proxy rotation, update the `scraping` section of your `config.yaml`:

```yaml
scraping:
  request_timeout: 30
  max_retries: 3                  # Retry up to 3 times (4 attempts total)
  user_agent_rotation: true       # Rotate browser UAs on session rotation
  custom_user_agents: []          # Leave empty to use defaults
  
  proxies:
    enabled: true
    ips:
      - "http://username:password@proxy1.residential-network.com:1234"
      - "http://username:password@proxy2.residential-network.com:1234"
      - "http://198.51.100.42:8080" # Unauthenticated proxy
    rotation_strategy: "round_robin"  # Choose "round_robin" or "random"
    health_check_url: "https://httpbin.org/ip"
```

### Environment Variable Override

In containerized or CI/CD environments, you can define your proxies as a comma-separated list in the `RESEARCHPULSE_PROXIES` environment variable:

```bash
export RESEARCHPULSE_PROXIES="http://proxy1.com:8080,http://proxy2.com:8080"
researchpulse run github
```

*(Note: Setting this environment variable automatically enables proxy rotation.)*

---

## 4. Verification & Health Monitoring

Before starting a heavy scraping run, use the built-in health checker tool to test your IPs:

```bash
researchpulse check-ips
```

This command will output a rich table testing:
1. **Proxy Status:** Latency and connectivity to the health check endpoint.
2. **Returned Public IP:** Verifies that your outgoing IP is successfully masked.
3. **Target Reachability:** Executes lightweight head requests to target academic and social endpoints (ArXiv, GitHub, Reddit) to confirm whether your proxy IP is flagged or blocked by that specific service.

### Reading the Health Check Table

*   `[green]OK[/green]`: Connection successful, endpoint reached.
*   `[red]Blocked (403)[/red] / [red]Blocked (429)[/red]`: The proxy IP is blacklisted by that target and will fail when running scrapers.
*   `[red]Timeout/Err[/red]`: The proxy took too long to connect or rejected the request.
