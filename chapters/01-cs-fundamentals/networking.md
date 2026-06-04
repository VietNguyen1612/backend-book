[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 1.4 Networking

### TCP/IP Deep Dive

#### The Three-Way Handshake

TCP establishes a connection with a three-way handshake that takes **one round-trip time (RTT)**. This latency is unavoidable for every new TCP connection, which is why connection pooling and keep-alive are so important.

```
TCP Three-Way Handshake:

  Client                                    Server
    |                                          |
    |------- SYN (seq=x) -------------------->|  Step 1: Client initiates
    |                                          |
    |<------ SYN-ACK (seq=y, ack=x+1) -------|  Step 2: Server acknowledges
    |                                          |
    |------- ACK (ack=y+1) ------------------>|  Step 3: Client confirms
    |                                          |
    |========= Connection Established =========|
    |                                          |
    |------- Data --------------------------->|  Now data can flow
    |                                          |

    Total latency: 1 RTT (Round-Trip Time) before data can be sent.
    On a 100ms RTT connection, that's 100ms just for the handshake.
    With TLS, add another 1-2 RTTs for the TLS handshake.

Connection Teardown (Four-Way):

  Client                                    Server
    |------- FIN --------------------------->|
    |<------ ACK ----------------------------|
    |<------ FIN ----------------------------|
    |------- ACK --------------------------->|
    |                                          |
    |--- TIME_WAIT (2*MSL, ~60s) ------------|
```

**SYN flood attack:** An attacker sends many SYN packets with spoofed source IPs. The server allocates resources for each half-open connection, eventually exhausting memory. **SYN cookies** defend against this: the server encodes connection state in the initial sequence number and does not allocate resources until the third handshake packet (ACK) arrives with the correct cookie.

#### Flow Control and Congestion Control

**Flow control** prevents the sender from overwhelming the receiver. The receiver advertises a **window size (rwnd)** indicating how much data it can buffer. The sender cannot send more than `min(cwnd, rwnd)` bytes of unacknowledged data.

**Congestion control** prevents the sender from overwhelming the network. The sender maintains a **congestion window (cwnd)** that grows and shrinks based on network feedback:

```
TCP Congestion Control Phases:

  cwnd
  (KB)
   |                                            *
   |                                         *
   |                                      *     <- Congestion Avoidance
   |                                   *           (linear growth, AIMD)
   |                                *
   |                             *
   |                    ssthresh = cwnd/2
   |            *  *  * ------+---------
   |         *                |
   |      *   <- Slow Start   | Packet loss detected!
   |    *      (exponential    | cwnd halved, switch to
   |  *        growth)         | congestion avoidance
   | *
   +---------------------------------------------> Time

  Modern algorithms:
    CUBIC (Linux default): uses a cubic function for window growth,
           faster recovery after loss
    BBR (Google): measures actual bandwidth and RTT, maintains a model
         of the network, better for high-bandwidth long-delay networks
```

#### TCP Tuning Options

**TCP_NODELAY** disables Nagle's algorithm. Nagle's algorithm buffers small outgoing packets and waits for either: (a) enough data to fill a full-size packet, or (b) an ACK for previously sent data. This reduces small-packet overhead on the network but adds latency. For interactive or real-time applications, disable it:

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle
# Important for: database connections, real-time APIs, WebSockets, gaming
```

**TIME_WAIT** is a state that lasts 2*MSL (Maximum Segment Lifetime, typically 60 seconds) after a connection closes. It ensures that delayed packets from the old connection are not confused with a new connection using the same port pair. On high-traffic servers, thousands of connections in TIME_WAIT can exhaust ephemeral ports.

```bash
# Check TIME_WAIT connections
ss -s  # Summary of all socket states
ss -ant state time-wait | wc -l  # Count TIME_WAIT sockets

# Mitigation:
# /etc/sysctl.conf
net.ipv4.tcp_tw_reuse = 1          # Reuse TIME_WAIT sockets for new outgoing connections
net.core.somaxconn = 65535         # Increase listen backlog
net.ipv4.ip_local_port_range = 1024 65535  # More ephemeral ports
```

**Keep-alive** sends periodic probes to detect dead connections:

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
# Linux-specific options:
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)    # Seconds before first probe
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)   # Seconds between probes
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)      # Probes before declaring dead

# Application-level heartbeats (WebSocket ping/pong, gRPC keepalive)
# are more reliable because they detect application-level issues,
# not just network-level connectivity.
```

#### Socket Buffer Tuning

The **Bandwidth-Delay Product (BDP)** determines the optimal socket buffer size: `BDP = bandwidth * RTT`. For a 1 Gbps link with 50ms RTT: BDP = 125 MB/s * 0.05s = 6.25 MB. If your socket buffer is smaller than BDP, you cannot fully utilize the link.

```bash
# View and tune socket buffer sizes
sysctl net.ipv4.tcp_rmem  # min, default, max receive buffer
sysctl net.ipv4.tcp_wmem  # min, default, max send buffer

# For high-bandwidth long-delay connections:
sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sysctl -w net.ipv4.tcp_wmem="4096 87380 16777216"
```

#### TCP vs UDP

| Feature | TCP | UDP |
|---|---|---|
| Reliability | Guaranteed delivery, ordering | Best-effort, no guarantees |
| Connection | Connection-oriented (handshake) | Connectionless |
| Overhead | Higher (headers, state, retransmission) | Lower (8-byte header) |
| Use cases | HTTP, database, email, file transfer | DNS, video streaming, gaming, QUIC |

> **Key Takeaway:** TCP performance tuning matters in production. Enable TCP_NODELAY for latency-sensitive services, configure keep-alive for connection health monitoring, manage TIME_WAIT on high-traffic servers, and size socket buffers according to BDP for high-throughput links. Connection pooling (database, HTTP) amortizes the handshake cost across many requests.

---

### HTTP Protocol

#### HTTP/1.1

HTTP/1.1 introduced **persistent connections** (Connection: keep-alive) — the TCP connection stays open for multiple request/response cycles instead of closing after each one. This avoids the per-request TCP handshake overhead.

**Pipelining** allows sending multiple requests without waiting for responses, but it was rarely used in practice because responses must arrive in order (**head-of-line blocking** at the HTTP level). If the first response is slow, all subsequent responses are delayed.

**Chunked transfer encoding** allows the server to start sending a response before knowing its total size (e.g., streaming API responses, server-sent events).

#### HTTP/2

HTTP/2 addresses HTTP/1.1's major limitations:

```
HTTP/1.1 vs HTTP/2:

  HTTP/1.1 (6 parallel connections):    HTTP/2 (single multiplexed connection):

  Conn 1: [--- req1 ---][--- req4 ---]   Stream 1: [--- req1 ---]
  Conn 2: [--- req2 ---][--- req5 ---]   Stream 2: [--- req2 ---]
  Conn 3: [--- req3 ---][--- req6 ---]   Stream 3: [--- req3 ---]
  Conn 4: [--- req7 ---]                 Stream 4: [--- req4 ---]
  Conn 5: [--- req8 ---]                 Stream 5: [--- req5 ---]
  Conn 6: [--- req9 ---]                 Stream 6: [--- req6 ---]
                                          Stream 7: [--- req7 ---]
  Problem: limited parallel connections,  Stream 8: [--- req8 ---]
  TCP handshake for each, wasteful        All interleaved on ONE connection!
```

Key features:
- **Binary framing layer**: HTTP messages are split into frames, transmitted interleaved, and reassembled. More efficient to parse than text-based HTTP/1.1.
- **Multiplexing**: multiple streams over a single TCP connection. No head-of-line blocking at the HTTP level (but TCP HOL blocking still exists — if a TCP packet is lost, all streams wait for retransmission).
- **HPACK header compression**: compresses headers using a dynamic table. HTTP/1.1 headers can be 500-800 bytes per request; HPACK reduces this dramatically.
- **Server push**: server can send resources before the client requests them (e.g., push CSS and JS along with the HTML response).

#### HTTP/3

HTTP/3 replaces TCP with **QUIC** (built on UDP), solving TCP's fundamental limitations:

```
HTTP/3 (QUIC) Advantages:

  TCP (HTTP/2):                          QUIC (HTTP/3):

  Single TCP stream                      Independent QUIC streams
  +==========================+           Stream 1: [===========]
  | Stream1 | Stream2 | ...  |           Stream 2: [====X=======]  <- loss here
  +==========================+           Stream 3: [===========]   <- NOT blocked!
  If ANY packet is lost,
  ALL streams are blocked                Connection migration:
  until retransmission.                  - Client changes IP (WiFi -> cellular)?
                                         - Connection continues! (identified by
  Connection migration:                    connection ID, not IP+port tuple)
  - Client changes IP?
  - Connection must be re-established    0-RTT resumption:
    (new TCP + TLS handshake)            - For returning clients, first request
                                           can be sent immediately (no handshake)
```

#### Caching Headers

Understanding HTTP caching is critical for performance:

```python
# Django view with caching headers
from django.views.decorators.cache import cache_control
from django.utils.cache import patch_cache_control
from django.http import JsonResponse
import hashlib

@cache_control(max_age=300, public=True)  # Cache for 5 minutes
def product_list(request):
    products = list(Product.objects.values('id', 'name', 'price'))
    return JsonResponse({'products': products})

def product_detail(request, pk):
    product = Product.objects.get(pk=pk)
    response = JsonResponse({'name': product.name, 'price': str(product.price)})

    # ETag for conditional requests
    content = response.content
    etag = hashlib.md5(content).hexdigest()
    response['ETag'] = f'"{etag}"'

    # Check if client has current version
    if request.META.get('HTTP_IF_NONE_MATCH') == f'"{etag}"':
        return HttpResponse(status=304)  # Not Modified — no body sent

    # Cache control directives
    patch_cache_control(response,
        max_age=60,           # Browser cache for 60 seconds
        s_maxage=300,         # CDN/proxy cache for 5 minutes
        public=True,          # Can be cached by shared caches
        must_revalidate=True  # Must check with server after max-age expires
    )
    return response
```

Key caching headers:
- **`Cache-Control: max-age=300`**: cache for 300 seconds without revalidation
- **`Cache-Control: no-cache`**: always revalidate with server (can still be stored)
- **`Cache-Control: no-store`**: never cache (sensitive data)
- **`Cache-Control: s-maxage=600`**: override max-age for shared caches (CDNs)
- **`ETag`**: content fingerprint for conditional requests
- **`Vary: Accept-Encoding`**: cache separate versions based on this header

#### Important HTTP Headers

```
Request/Response Headers for Backend Engineers:

  X-Request-Id: abc-123-def-456      # Unique ID for tracing across services
  X-Forwarded-For: 1.2.3.4, 5.6.7.8 # Real client IP chain (behind proxies)
  X-Forwarded-Proto: https            # Original protocol (when behind TLS-terminating proxy)
  Strict-Transport-Security: max-age=31536000; includeSubDomains  # Force HTTPS
  Content-Security-Policy: default-src 'self'  # XSS protection
  X-Content-Type-Options: nosniff     # Prevent MIME-type sniffing
```

> **Key Takeaway:** HTTP/2 should be your default for web APIs (multiplexing, header compression). HTTP/3 is increasingly adopted for mobile and lossy-network scenarios. Proper caching headers can eliminate 50-90% of backend traffic — they are one of the highest-leverage performance optimizations available.

---

### DNS

#### Recursive Resolution

When your browser needs to resolve `api.example.com`, this is what happens:

```
DNS Resolution: api.example.com

  Browser      Recursive Resolver       Root NS        .com TLD NS      example.com NS
     |         (e.g., 8.8.8.8)            |                |                  |
     |                |                    |                |                  |
     |-- query ------>|                    |                |                  |
     |                |-- "root?" -------->|                |                  |
     |                |<- "ask .com NS" ---|                |                  |
     |                |                                     |                  |
     |                |-- "example.com?" ------------------>|                  |
     |                |<- "ask ns1.example.com" ------------|                  |
     |                |                                                        |
     |                |-- "api.example.com?" -------------------------------->|
     |                |<- "93.184.216.34" ------------------------------------|
     |                |                                                        |
     |<- 93.184.216.34|
     |                |
     |  (cached at every level with TTL)

  After first resolution, the recursive resolver caches the answer.
  Subsequent queries for api.example.com return immediately from cache.
```

#### Record Types

| Type | Purpose | Example |
|---|---|---|
| A | IPv4 address | `api.example.com -> 93.184.216.34` |
| AAAA | IPv6 address | `api.example.com -> 2606:2800:220:1:...` |
| CNAME | Alias (canonical name) | `www.example.com -> example.com` |
| MX | Mail server (with priority) | `example.com -> 10 mail.example.com` |
| TXT | Arbitrary text (SPF, DKIM, verification) | `example.com -> "v=spf1 include:_spf.google.com"` |
| SRV | Service discovery (host + port + priority) | `_http._tcp.example.com -> 10 0 8080 web1.example.com` |
| NS | Nameserver delegation | `example.com -> ns1.example.com` |
| PTR | Reverse DNS (IP to name) | `34.216.184.93.in-addr.arpa -> api.example.com` |
| CAA | Certificate Authority Authorization | `example.com -> 0 issue "letsencrypt.org"` |

#### TTL Strategies

**Low TTL (30-300 seconds):** Use for services that need fast failover. If a server goes down, DNS can redirect traffic within seconds. Cost: more DNS queries, higher load on authoritative nameservers.

**High TTL (3600-86400 seconds):** Use for stable records (MX, NS, rarely-changing A records). Reduces DNS query volume and improves resolution latency.

**Migration strategy:** Before changing a DNS record, lower the TTL well in advance (at least 2x the old TTL before the change), make the change, verify, then raise the TTL back.

```
DNS TTL Strategy for Zero-Downtime Migration:

  Timeline:
  Day -2:  Lower TTL from 3600s to 60s
           (wait for old TTL to expire across all caches)
  Day 0:   Change the A record to new IP
           (within 60s, all clients resolve to new IP)
  Day +1:  Verify everything works
  Day +2:  Raise TTL back to 3600s
```

#### DNS-Based Load Balancing

- **Round-robin:** Return multiple A records; clients pick one (often the first). Simple but uneven — does not account for server load.
- **Weighted:** Return records with weights (e.g., 70% to server A, 30% to server B). Available in Route53, CloudFlare.
- **GeoDNS/Latency-based:** Return the IP of the geographically or latency-closest server. Used by CDNs and global services.
- **Health-checked failover:** DNS provider monitors server health and removes unhealthy servers from responses.

#### Split-Horizon DNS

Split-horizon DNS returns different answers based on the client's network. Internal clients resolve `db.example.com` to the private IP `10.0.1.5`, while external clients resolve it to a public IP or get NXDOMAIN. This avoids hairpin NAT and keeps internal traffic on the private network.

#### DNSSEC

DNSSEC adds cryptographic signatures to DNS records, creating a **chain of trust** from the root zone down to individual records. It prevents DNS spoofing and cache poisoning attacks. Key record types: DNSKEY (public key), RRSIG (signature), DS (delegation signer).

> **Key Takeaway:** DNS is a critical part of your infrastructure that is easy to overlook until something breaks. Understand TTLs for migration planning, record types for service configuration, and DNS-based load balancing for global distribution. Always pre-lower TTLs before DNS migrations, and use health-checked DNS for automated failover.

---

### TLS/SSL

#### TLS 1.3 Handshake

TLS 1.3 drastically simplified the handshake, reducing it from 2 RTTs (TLS 1.2) to **1 RTT**. It removed all insecure cipher suites and only supports AEAD ciphers (AES-128-GCM, AES-256-GCM, ChaCha20-Poly1305).

```
TLS 1.3 Handshake (1-RTT):

  Client                                         Server
    |                                               |
    |-- ClientHello + KeyShare ----------------->  |
    |   (supported ciphers, key exchange params)    |
    |                                               |
    |<-- ServerHello + KeyShare + {Certificate} ---|
    |    + {CertificateVerify} + {Finished}        |
    |   (server sends everything in one flight!)    |
    |                                               |
    |-- {Finished} ------------------------------>  |
    |                                               |
    |============= Encrypted Data ================|

  TLS 1.2: 2 RTTs (ClientHello -> ServerHello -> Certificate -> KeyExchange -> Finished)
  TLS 1.3: 1 RTT (merged steps)
  TLS 1.3 0-RTT: Returning clients can send data in the FIRST message
                  (using previously established keys — replay risk!)
```

#### Certificate Chain

```
Certificate Chain of Trust:

  Root CA (self-signed, pre-installed in OS/browser trust store)
     |
     |-- signs -->  Intermediate CA Certificate
                       |
                       |-- signs -->  Leaf Certificate (your domain)
                                        CN=api.example.com
                                        SAN=*.example.com

  The server must send: Leaf + Intermediate(s)
  The client already has: Root CA (in trust store)
  The client verifies: Leaf was signed by Intermediate,
                       Intermediate was signed by Root.
```

**Certificate pinning** for mobile apps: the app embeds the expected certificate (or public key hash) and rejects connections with any other certificate, even if it is technically valid. This prevents man-in-the-middle attacks using fraudulently issued certificates.

#### mTLS (Mutual TLS)

In standard TLS, only the server presents a certificate. In **mTLS**, both sides authenticate each other with certificates. This is the primary mechanism for service-to-service authentication in microservice architectures.

```
Standard TLS:                       Mutual TLS (mTLS):

  Client        Server               Client        Server
    |               |                   |               |
    |-- hello ----->|                   |-- hello ----->|
    |<-- cert ------|                   |<-- cert ------|
    |-- verify -----|                   |-- verify -----|
    |               |                   |<-- cert req --|
    |               |                   |-- client cert>|
    |               |                   |-- verify -----|
    |== encrypted ==|                   |== encrypted ==|

  Server identity only               Both identities verified
```

**SPIFFE/SPIRE** provides automatic workload identity management — each service gets a short-lived X.509 certificate that identifies it. This is how service meshes like Istio and Linkerd implement zero-trust networking.

#### OCSP Stapling

Without stapling, the client must contact the CA's OCSP responder to check if the server's certificate has been revoked. This adds latency and reveals which sites the client is visiting. With **OCSP stapling**, the server periodically fetches its own revocation status from the CA and includes it (signed by the CA) in the TLS handshake. The client gets freshness proof without a separate round trip.

#### Let's Encrypt and ACME

Let's Encrypt provides free TLS certificates using the **ACME protocol**. Two main validation methods:

- **HTTP-01:** Place a specific file at `http://yourdomain.com/.well-known/acme-challenge/<token>`. Proves you control the domain's web server.
- **DNS-01:** Create a specific TXT record at `_acme-challenge.yourdomain.com`. Proves you control the domain's DNS. Required for wildcard certificates.

```bash
# Certbot automatic certificate management
certbot certonly --nginx -d example.com -d www.example.com
# Auto-renewal (typically runs as a systemd timer or cron job)
certbot renew --deploy-hook "systemctl reload nginx"
```

#### SNI (Server Name Indication)

**SNI** is a TLS extension where the client includes the requested hostname in the ClientHello message (before encryption). This allows a single IP address to serve multiple TLS-protected domains, each with its own certificate. Without SNI, you would need one IP address per domain. All modern clients support SNI.

> **Key Takeaway:** TLS is not optional — every production service should use TLS 1.3 with valid certificates. Use Let's Encrypt for free automated certificates, enable OCSP stapling for performance, and implement mTLS for service-to-service authentication in microservices. Understand the certificate chain so you can debug "certificate verify failed" errors (usually a missing intermediate certificate).

---

### Network Debugging

#### tcpdump

`tcpdump` captures raw packets on a network interface. It is the most fundamental network debugging tool, available on virtually every Linux system.

```bash
# Capture all traffic on port 443 (HTTPS)
tcpdump -i any port 443 -w capture.pcap

# Capture traffic to/from a specific host
tcpdump -i eth0 host 10.0.1.5

# Capture only TCP SYN packets (new connections)
tcpdump -i any 'tcp[tcpflags] & tcp-syn != 0'

# Capture DNS queries
tcpdump -i any port 53 -nn

# Read and analyze a capture file
tcpdump -r capture.pcap -A  # ASCII output
```

#### Wireshark

Wireshark provides a GUI for packet analysis. Open `.pcap` files from tcpdump, follow TCP streams to see full HTTP conversations, decode protocols automatically, and generate statistics (conversation lengths, retransmission rates, latency distribution).

#### curl

`curl` is essential for testing HTTP endpoints with precise control:

```bash
# Verbose output showing TLS handshake, headers, timing
curl -v https://api.example.com/health

# Timing breakdown of a request
curl -w "\n  DNS:        %{time_namelookup}s\n  Connect:    %{time_connect}s\n  TLS:        %{time_appconnect}s\n  TTFB:       %{time_starttransfer}s\n  Total:      %{time_total}s\n" \
     -o /dev/null -s https://api.example.com/

# Override DNS resolution (test before DNS change)
curl --resolve api.example.com:443:93.184.216.34 https://api.example.com/

# Force HTTP/2
curl --http2 -v https://api.example.com/

# POST with JSON body
curl -X POST https://api.example.com/users \
     -H "Content-Type: application/json" \
     -d '{"name": "Alice", "email": "alice@example.com"}'
```

#### traceroute / mtr

`traceroute` shows the network path (hops) between your machine and a destination. `mtr` combines traceroute with continuous ping for ongoing monitoring.

```bash
# Basic traceroute
traceroute api.example.com

# MTR: continuous monitoring, shows packet loss per hop
mtr api.example.com

# Example output:
#                              Loss%  Snt   Last   Avg  Best  Wrst StDev
# 1. gateway.local              0.0%   10    0.5   0.4   0.3   0.8   0.1
# 2. isp-router.net             0.0%   10    5.2   5.1   4.8   5.5   0.2
# 3. core-router.isp.net        0.0%   10   12.3  12.1  11.8  12.8   0.3
# 4. peer-exchange.net          5.0%   10   25.1  30.2  24.5  45.3   7.2  <-- packet loss!
# 5. api.example.com            0.0%   10   28.4  28.1  27.5  29.0   0.5
```

#### ss / netstat

`ss` (Socket Statistics) is the modern replacement for `netstat`:

```bash
# List all listening TCP sockets with process names
ss -tlnp
# State   Recv-Q  Send-Q  Local Address:Port   Peer Address:Port   Process
# LISTEN  0       128     0.0.0.0:8000          0.0.0.0:*           users:("gunicorn",pid=1234)
# LISTEN  0       128     0.0.0.0:5432          0.0.0.0:*           users:("postgres",pid=5678)

# Summary of all connection states
ss -s
# TCP:   485 (estab 320, closed 42, orphaned 3, timewait 98)

# Find connections in TIME_WAIT state
ss -ant state time-wait | wc -l

# Find all connections to a specific port
ss -ant dst :5432   # All connections to PostgreSQL
```

#### dig

`dig` queries DNS records with detailed output:

```bash
# Basic query
dig api.example.com A

# Full resolution trace
dig +trace api.example.com

# Query a specific DNS server
dig @8.8.8.8 api.example.com

# Check TXT records (SPF, DKIM, domain verification)
dig example.com TXT

# Reverse DNS lookup
dig -x 93.184.216.34
```

#### MTU and Fragmentation

The **Maximum Transmission Unit (MTU)** is the largest packet size a network link can carry (typically 1500 bytes for Ethernet). When a packet exceeds the MTU, it must be fragmented (split into smaller pieces) or dropped (if the "Don't Fragment" flag is set).

**Path MTU Discovery** finds the smallest MTU along the entire path. If ICMP "Fragmentation Needed" messages are blocked by a firewall (common), this fails silently, causing mysterious connection issues where small requests work but large ones hang.

```bash
# Test path MTU (1472 = 1500 MTU - 20 IP header - 8 ICMP header)
ping -s 1472 -M do api.example.com
# If this fails, try smaller sizes to find the actual path MTU
ping -s 1400 -M do api.example.com
```

> **Key Takeaway:** Network debugging is an essential skill for backend engineers. Use `curl -w` for HTTP timing analysis, `ss` for connection state inspection, `tcpdump` for packet-level debugging, and `mtr` for path analysis. Most production networking issues come down to: DNS misconfiguration, certificate problems, firewall blocking, connection exhaustion (TIME_WAIT), or MTU issues. Having these tools in your toolkit lets you quickly identify which layer the problem is at.
