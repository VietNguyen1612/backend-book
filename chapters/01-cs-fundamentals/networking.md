[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 1.4 Networking

Every backend system is a distributed system, even if it is just one Django process talking to one Postgres instance — the moment a request crosses a socket, you inherit the network's failure modes. Latency that appears from nowhere, connections that hang only for large payloads, a service that runs out of ports while CPU sits idle, an API that works from the office but not from production: these are not application bugs, and no amount of reading your own code will explain them. They live in the handshakes, buffers, caches, and intermediaries between your code and its callers. The previous section on operating systems ended at the socket interface; this one follows the bytes after they leave it.

After working through this section you should be able to answer questions like: why does a new HTTPS connection cost two or three round trips, and what do connection pooling and TLS 1.3 each shave off? When a request stalls, how do you tell whether the time went to DNS, the TCP connect, the TLS handshake, or the application itself? Why must you never trust `X-Forwarded-For` from an arbitrary client, why do you lower a DNS TTL days before a migration, and why does blocking ICMP at the firewall cause large requests to hang while small ones succeed?

We build up in layers, the same way the network does. We start with the layered model and the lower layers — IP addressing, CIDR, NAT, routing — that everything else rides on. Then we go deep on TCP/IP: the handshake, congestion control, and the socket-level tuning knobs that matter in production. From there we climb to the HTTP protocol and its evolution from 1.1 through HTTP/3, then to the proxies, gateways, and load balancers that sit in front of every real deployment. Two supporting pillars follow — DNS, which turns names into addresses, and TLS/SSL, which secures the channel — before we close with network debugging: the tools that let you locate a fault at the right layer when something inevitably breaks.

## The Layered Model & Lower Layers

Before the TCP and HTTP details, it helps to see where each protocol sits. Networking is built in **layers**, each one adding its own header around the data from the layer above (**encapsulation**) and stripping it on the way back up.

### OSI vs TCP/IP and Encapsulation

The 7-layer OSI model is the academic reference; the 4-layer **TCP/IP model** is what the internet actually runs on. The mapping that matters in practice:

```
TCP/IP layer      Example protocols      Address / unit
--------------    -----------------      --------------------------
Application       HTTP, DNS, gRPC, TLS   data / message
Transport         TCP, UDP, QUIC         port (e.g. :443)  -> segment
Internet          IP, ICMP               IP address        -> packet
Link              Ethernet, Wi-Fi, ARP   MAC address       -> frame

Encapsulation — sending "GET /" wraps the data at each layer down:

  [ Ethernet hdr | IP hdr | TCP hdr | HTTP "GET /" | Ethernet trailer ]
   \___________/  \_____/  \______/  \___________/
     link layer    internet transport  application

Each layer reads ONLY its own header and hands the payload up/down.
A router rewrites the link header per hop but leaves the IP packet intact.
```

The discipline of layering is why you can debug at one level without the others: a `tcpdump` shows you IP/TCP headers; `curl -v` shows you the application layer; an MTU problem (link layer) manifests as application hangs precisely because the layers are normally independent.

### IP Addressing

- **IPv4:** 32-bit, written as a dotted quad (`93.184.216.34`) — ~4.3 billion addresses, long since exhausted (the reason NAT exists).
- **IPv6:** 128-bit, written in hex groups (`2606:2800:220:1::34`) — effectively unlimited; restores end-to-end addressability.
- **Private ranges** (RFC 1918, not routable on the public internet, reused inside every network): `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`. Your VPC subnets live here.
- **Loopback:** `127.0.0.1` (`::1` in IPv6) — the host talking to itself, never leaves the machine.
- **Link-local:** `169.254.0.0/16` (IPv6 `fe80::/10`) — auto-assigned, valid only on the local segment. The address `169.254.169.254` is the well-known **cloud metadata endpoint** (AWS/GCP/Azure), which is why SSRF protections specifically block it.

### CIDR and Subnetting

CIDR notation (`10.0.1.0/24`) says how many leading bits are the **network** portion; the rest identify hosts. The prefix length is the whole game:

```
/24  -> 256 addresses (254 usable: .0 = network, .255 = broadcast)
/16  -> 65,536 addresses
/8   -> 16,777,216 addresses
Smaller number after the slash = BIGGER network (more host bits).

10.0.1.0/24 contains 10.0.1.0 .. 10.0.1.255
10.0.0.0/16 contains all of 10.0.0.x .. 10.0.255.x
```

This is the math behind **VPC/subnet design** and every **security-group / firewall rule** ("allow `10.0.0.0/8` inbound") — sizing a subnet too small (`/28` = 14 hosts) and running out of IPs for pods/instances is a common cloud-networking mistake.

### ARP, ICMP, NAT

- **ARP (Address Resolution Protocol):** maps an IP address to a MAC address on the **local** segment. Before a host can send a frame to `10.0.1.5`, it broadcasts "who has 10.0.1.5?" and caches the MAC reply.
- **ICMP:** the network's control/diagnostic channel — `ping` (echo request/reply), `traceroute`, "destination unreachable", and the critical "**fragmentation needed**" message that drives Path MTU Discovery. Blocking ICMP wholesale (a common over-zealous firewall rule) breaks MTU discovery and causes the silent large-payload hangs covered later.
- **NAT (Network Address Translation):** rewrites private source addresses to a shared public one (with port translation, PAT) so many internal hosts share one public IP. NAT is **why most devices aren't directly reachable from the internet** — connections must be initiated *outbound*. This is the reason inbound webhooks need a public endpoint, and why peer-to-peer apps resort to **hole-punching** through NAT.

### Routing, BGP, and Anycast

The internet is a mesh of **autonomous systems** (ASes — ISPs, clouds, large networks) that exchange reachability information via **BGP (Border Gateway Protocol)**. BGP decides, hop by AS-hop, how a packet reaches a distant network. **Anycast** layers on top: the *same* IP address is announced from many locations worldwide, and BGP naturally routes each client to the **nearest** one. Anycast is the backbone of **CDNs**, public DNS resolvers (`8.8.8.8`, `1.1.1.1` answer from hundreds of sites under one IP), and **DDoS absorption** (attack traffic is spread across many points of presence instead of one).

> **Key Takeaway:** The layers are independent for a reason — knowing which layer a symptom lives at tells you which tool to reach for. Internalize private ranges and CIDR math (you will design subnets and write firewall rules constantly), remember that NAT makes inbound connections the hard direction, and recognize anycast as the trick that puts `8.8.8.8` or a CDN edge physically near every user.

---

## TCP/IP Deep Dive

The lower layers deliver individual packets on a best-effort basis; TCP is the transport layer's answer to building a reliable, ordered byte stream on top of that unreliability. Because nearly every protocol you operate — HTTP, your database wire protocol, gRPC — rides on TCP, its connection lifecycle and tuning knobs set the latency and throughput floor for everything above. We start with how a connection is born, then look at how TCP paces itself, and finally at the socket options worth changing in production.

### The Three-Way Handshake

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

### Flow Control and Congestion Control

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

### TCP Tuning Options

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

On a busy server the count command makes the problem visible:

```text
$ ss -ant state time-wait | wc -l
28734
```

**How to read this output:** Nearly 29,000 sockets stuck in TIME_WAIT. Each one pins the local (IP, port) tuple for ~60 seconds, and with only ~28,000 usable ephemeral ports per destination, you are on the edge of running out — at which point *new outbound* connections fail with "cannot assign requested address" even though CPU and memory are idle. This is the classic failure mode of a service that opens a fresh connection per request to an upstream (database, internal API) instead of pooling. The real fix is connection pooling and keep-alive; `tcp_tw_reuse` is a mitigation that lets the kernel safely reuse TIME_WAIT sockets for new *outgoing* connections, but it does not help inbound TIME_WAIT.

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

### Socket Buffer Tuning

The **Bandwidth-Delay Product (BDP)** determines the optimal socket buffer size: `BDP = bandwidth * RTT`. For a 1 Gbps link with 50ms RTT: BDP = 125 MB/s * 0.05s = 6.25 MB. If your socket buffer is smaller than BDP, you cannot fully utilize the link.

```bash
# View and tune socket buffer sizes
sysctl net.ipv4.tcp_rmem  # min, default, max receive buffer
sysctl net.ipv4.tcp_wmem  # min, default, max send buffer

# For high-bandwidth long-delay connections:
sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sysctl -w net.ipv4.tcp_wmem="4096 87380 16777216"
```

Reading the current values prints three numbers (min, default, max in bytes):

```console
$ sysctl net.ipv4.tcp_rmem
net.ipv4.tcp_rmem = 4096	131072	6291456
```

**How to read this output:** The kernel auto-tunes each connection's receive buffer between `min` and `max`, starting near `default`. The default `max` of ~6 MB here is fine for typical RTTs, but for the 1 Gbps / 50ms link above (BDP = 6.25 MB) it is right at the edge — bump `max` to 16 MB so the buffer can grow large enough to keep the pipe full. If `max` is below the BDP, throughput stalls no matter how fast the link is, because the sender runs out of in-flight window and waits for ACKs.

> **Common pitfall:** These `sysctl -w` changes are lost on reboot. Persist them in `/etc/sysctl.conf` (or a file in `/etc/sysctl.d/`) and apply with `sysctl -p`.

### TCP vs UDP

| Feature | TCP | UDP |
|---|---|---|
| Reliability | Guaranteed delivery, ordering | Best-effort, no guarantees |
| Connection | Connection-oriented (handshake) | Connectionless |
| Overhead | Higher (headers, state, retransmission) | Lower (8-byte header) |
| Use cases | HTTP, database, email, file transfer | DNS, video streaming, gaming, QUIC |

> **Key Takeaway:** TCP performance tuning matters in production. Enable TCP_NODELAY for latency-sensitive services, configure keep-alive for connection health monitoring, manage TIME_WAIT on high-traffic servers, and size socket buffers according to BDP for high-throughput links. Connection pooling (database, HTTP) amortizes the handshake cost across many requests.

---

## HTTP Protocol

With a reliable TCP stream in place, we can move up to the protocol your services actually speak. HTTP's evolution is largely a story of working around the transport beneath it — first reusing connections, then multiplexing over one, and finally replacing TCP altogether — and each version changes how you should think about connection management and performance. The caching headers at the end of this section are where a backend engineer gets the most leverage from the protocol.

### HTTP/1.1

HTTP/1.1 introduced **persistent connections** (Connection: keep-alive) — the TCP connection stays open for multiple request/response cycles instead of closing after each one. This avoids the per-request TCP handshake overhead.

**Pipelining** allows sending multiple requests without waiting for responses, but it was rarely used in practice because responses must arrive in order (**head-of-line blocking** at the HTTP level). If the first response is slow, all subsequent responses are delayed.

**Chunked transfer encoding** allows the server to start sending a response before knowing its total size (e.g., streaming API responses, server-sent events).

### HTTP/2

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

### HTTP/3

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

### Caching Headers

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

### Important HTTP Headers

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

## Proxies, Gateways & Load Balancers

A proxy is an intermediary that sits between client and server and relays requests. The single most important distinction — and a frequent interview question — is *which side* it fronts.

### Forward Proxy vs Reverse Proxy

```
Forward proxy (fronts the CLIENTS):

   [clients] -> [forward proxy] -> internet -> [any server]
   The server sees the PROXY's IP. Clients are hidden.
   Uses: corporate egress control, content filtering, caching, anonymity.

Reverse proxy (fronts the SERVERS):

   client -> [reverse proxy] -> [backend 1]
                              -> [backend 2]
                              -> [backend 3]
   The client sees the PROXY; backends are hidden behind it.
   Uses: TLS termination, caching, compression, LOAD BALANCING.
   Examples: nginx, HAProxy, Envoy, AWS ALB.
```

A **forward proxy** acts on behalf of the *clients* — it makes outbound requests for them (a corporate egress gateway, a caching proxy). The destination server sees the proxy's IP, not the client's.

A **reverse proxy** acts on behalf of the *servers* — it terminates the client's connection and forwards it to one of several backends. This is where most backend infrastructure lives: it does **TLS termination** (decrypt once at the edge so backends speak plain HTTP), **caching**, **compression**, and **load balancing** across a pool of identical app servers. A **load balancer** is a reverse proxy specialized for distributing traffic (round-robin, least-connections, consistent-hash) with health checks that pull dead backends out of rotation.

### API Gateway

An **API gateway** is a reverse proxy that is **application-aware**. Beyond routing, it centralizes cross-cutting concerns so individual services don't each reimplement them: **authentication/authorization**, **rate limiting**, request **routing and aggregation** (fan out to several services and combine responses), and **protocol translation** (e.g., REST in front, gRPC behind). It is the single front door to a fleet of microservices (Kong, AWS API Gateway, Envoy-based meshes).

### Tunneling, CONNECT, and the X-Forwarded-For Trap

Because a forward proxy can't read encrypted HTTPS, browsers use the HTTP **`CONNECT`** method to ask the proxy to open a raw TCP **tunnel** to the destination; the TLS handshake then passes through opaquely. This is how proxies pass HTTPS without decrypting it.

When traffic crosses one or more proxies, the original client IP is otherwise lost (the backend only sees the *last* proxy). To preserve it, proxies append headers — **`X-Forwarded-For`** (the de-facto standard, a comma-separated chain) and the standardized **`Forwarded`** header — or use the lower-level **PROXY protocol** at the TCP layer.

```
Client 1.2.3.4 -> Proxy A -> Proxy B (reverse proxy) -> app server

  X-Forwarded-For: 1.2.3.4, <Proxy A's IP>
  -> the app reads the LEFTMOST entry as the "real" client IP
```

> **Common pitfall:** Trusting `X-Forwarded-For` blindly. The header is just text a client can set — an attacker can send `X-Forwarded-For: 127.0.0.1` (or any IP) to forge their origin, bypassing IP allowlists, rate limits keyed on client IP, or audit logs. **Only honor forwarding headers when the request arrives from a proxy you control.** Configure your framework's trusted-proxy list (Django's `SECURE_PROXY_SSL_HEADER` / `USE_X_FORWARDED_HOST`, or a fixed number of trusted hops) so it strips client-supplied values and reads only the entry your own edge appended. Reading the *leftmost untrusted* value as the client IP is the secure default.

> **Key Takeaway:** "Forward fronts clients, reverse fronts servers" is the mental model to keep. In production you live behind a reverse proxy / load balancer doing TLS termination and health-checked balancing, often with an API gateway adding auth and rate limiting. The recurring security gotcha is the client IP: never trust `X-Forwarded-For` except from proxies you operate, or you hand attackers a way to spoof their address.

---

## DNS

Everything so far assumed the client already knows the server's IP address. In practice that knowledge comes from DNS, the globally distributed, heavily cached database that maps names to addresses — and because every connection begins with a lookup, DNS misconfiguration has an outsized blast radius. Understanding how resolution and caching work is what makes zero-downtime migrations and DNS-based failover possible.

### Recursive Resolution

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

### Record Types

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

### TTL Strategies

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

### DNS-Based Load Balancing

- **Round-robin:** Return multiple A records; clients pick one (often the first). Simple but uneven — does not account for server load.
- **Weighted:** Return records with weights (e.g., 70% to server A, 30% to server B). Available in Route53, CloudFlare.
- **GeoDNS/Latency-based:** Return the IP of the geographically or latency-closest server. Used by CDNs and global services.
- **Health-checked failover:** DNS provider monitors server health and removes unhealthy servers from responses.

### Split-Horizon DNS

Split-horizon DNS returns different answers based on the client's network. Internal clients resolve `db.example.com` to the private IP `10.0.1.5`, while external clients resolve it to a public IP or get NXDOMAIN. This avoids hairpin NAT and keeps internal traffic on the private network.

### DNSSEC

DNSSEC adds cryptographic signatures to DNS records, creating a **chain of trust** from the root zone down to individual records. It prevents DNS spoofing and cache poisoning attacks. Key record types: DNSKEY (public key), RRSIG (signature), DS (delegation signer).

> **Key Takeaway:** DNS is a critical part of your infrastructure that is easy to overlook until something breaks. Understand TTLs for migration planning, record types for service configuration, and DNS-based load balancing for global distribution. Always pre-lower TTLs before DNS migrations, and use health-checked DNS for automated failover.

---

## TLS/SSL

Name resolved and connection established, the remaining problem is that everything we have described so far travels in cleartext through networks you do not control. TLS supplies the encryption and authentication layer that every production service now requires — and, as we saw with proxies, where you terminate it is an architectural decision. This section covers the handshake cost, the certificate machinery you will inevitably debug, and mTLS for service-to-service identity.

### TLS 1.3 Handshake

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

### Certificate Chain

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

### mTLS (Mutual TLS)

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

### OCSP Stapling

Without stapling, the client must contact the CA's OCSP responder to check if the server's certificate has been revoked. This adds latency and reveals which sites the client is visiting. With **OCSP stapling**, the server periodically fetches its own revocation status from the CA and includes it (signed by the CA) in the TLS handshake. The client gets freshness proof without a separate round trip.

### Let's Encrypt and ACME

Let's Encrypt provides free TLS certificates using the **ACME protocol**. Two main validation methods:

- **HTTP-01:** Place a specific file at `http://yourdomain.com/.well-known/acme-challenge/<token>`. Proves you control the domain's web server.
- **DNS-01:** Create a specific TXT record at `_acme-challenge.yourdomain.com`. Proves you control the domain's DNS. Required for wildcard certificates.

```bash
# Certbot automatic certificate management
certbot certonly --nginx -d example.com -d www.example.com
# Auto-renewal (typically runs as a systemd timer or cron job)
certbot renew --deploy-hook "systemctl reload nginx"
```

A successful issuance prints the certificate paths and expiry:

```text
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/example.com/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/example.com/privkey.pem
This certificate expires on 2026-09-02.
```

**How to read this output:** Note `fullchain.pem` — point your server at this, not `cert.pem`, because it bundles the leaf *plus* the intermediate(s). Serving only the leaf is the single most common cause of "certificate verify failed" errors from clients that don't happen to cache the intermediate. The 90-day expiry is deliberate: Let's Encrypt certs are short-lived to force automation, so the `certbot renew` timer (which renews when ~30 days remain) is not optional — a forgotten renewal is a self-inflicted outage. The `--deploy-hook` only fires when a renewal actually happens, so reloading nginx there is safe to run on every timer tick.

### SNI (Server Name Indication)

**SNI** is a TLS extension where the client includes the requested hostname in the ClientHello message (before encryption). This allows a single IP address to serve multiple TLS-protected domains, each with its own certificate. Without SNI, you would need one IP address per domain. All modern clients support SNI.

> **Key Takeaway:** TLS is not optional — every production service should use TLS 1.3 with valid certificates. Use Let's Encrypt for free automated certificates, enable OCSP stapling for performance, and implement mTLS for service-to-service authentication in microservices. Understand the certificate chain so you can debug "certificate verify failed" errors (usually a missing intermediate certificate).

---

## Network Debugging

The preceding sections gave us the theory; this one is about what to type when production misbehaves. The layered model pays off here: each tool below observes a specific layer, so choosing the right one — packets, sockets, HTTP timing, DNS, or the path itself — is most of the diagnosis. We walk through the essential toolkit roughly bottom-up, ending with the MTU issues that tie back to the link layer where we began.

### tcpdump

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

### Wireshark

Wireshark provides a GUI for packet analysis. Open `.pcap` files from tcpdump, follow TCP streams to see full HTTP conversations, decode protocols automatically, and generate statistics (conversation lengths, retransmission rates, latency distribution).

### curl

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

The `-w` timing template is the highest-value trick here. It prints a cumulative breakdown that pinpoints which phase of a request is slow:

```text
  DNS:        0.004231s
  Connect:    0.038122s
  TLS:        0.119876s
  TTFB:       0.241509s
  Total:      0.245013s
```

**How to read this output:** Each value is the *cumulative* time from the start of the request, so you read the gaps between them, not the absolute numbers. DNS took 4ms; the TCP connect added ~34ms (`Connect - DNS`), the TLS handshake added ~82ms (`TLS - Connect`), and the server then took ~122ms to produce the first byte (`TTFB - TLS`). In a real incident this instantly tells you *where* the latency lives: a large `TLS - Connect` gap means a slow handshake (missing OCSP stapling, far-away server), while a large `TTFB - TLS` gap means the application itself is slow. The tiny gap between `TTFB` and `Total` here means the response body downloaded almost instantly. This is the first command to run when someone reports "the API feels slow."

### traceroute / mtr

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

### ss / netstat

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

### dig

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

A plain `dig api.example.com A` prints something like:

```text
;; ANSWER SECTION:
api.example.com.	276	IN	A	93.184.216.34

;; Query time: 12 msec
;; SERVER: 8.8.8.8#53(8.8.8.8)
```

**How to read this output:** The number `276` is the remaining TTL in seconds — it counts *down* on repeated queries as the resolver's cache ages, which is how you confirm a record is being served from cache versus fetched fresh. The `ANSWER SECTION` shows the resolved record type and value, and `SERVER` confirms which resolver answered. When planning a migration, watch that TTL drop toward your lowered value before you cut over; when debugging a stale record, compare the TTL across `dig @8.8.8.8` and `dig @1.1.1.1` to see if one resolver is still caching the old answer. `dig +trace` is the tool of choice when resolution fails entirely — it walks the delegation from the root down so you can see exactly which nameserver returns the wrong (or no) answer.

### MTU and Fragmentation

The **Maximum Transmission Unit (MTU)** is the largest packet size a network link can carry (typically 1500 bytes for Ethernet). When a packet exceeds the MTU, it must be fragmented (split into smaller pieces) or dropped (if the "Don't Fragment" flag is set).

**Path MTU Discovery** finds the smallest MTU along the entire path. If ICMP "Fragmentation Needed" messages are blocked by a firewall (common), this fails silently, causing mysterious connection issues where small requests work but large ones hang.

```bash
# Test path MTU (1472 = 1500 MTU - 20 IP header - 8 ICMP header)
ping -s 1472 -M do api.example.com
# If this fails, try smaller sizes to find the actual path MTU
ping -s 1400 -M do api.example.com
```

When a packet is too big for some link on the path and the "Don't Fragment" bit is set, the failure looks like this:

```text
$ ping -s 1472 -M do api.example.com
PING api.example.com (93.184.216.34) 1472(1500) bytes of data.
ping: local error: message too long, mtu=1492
--- api.example.com ping statistics ---
3 packets transmitted, 0 received, 100% packet loss
```

**How to read this output:** The clue is `mtu=1492` — a classic PPPoE/tunnel link that steals 8 bytes from the usual 1500. A 1472-byte payload (+28 bytes of headers = 1500) cannot pass, so the packet is dropped rather than fragmented. The reason this matters: when ICMP "Fragmentation Needed" messages are firewalled (extremely common), this happens *silently* in real traffic — a TLS ClientHello or a large POST body hangs forever while small requests and pings succeed. That asymmetry ("curl to /health works but real requests stall") is the signature of an MTU black hole. The fix is to lower the path MTU or enable MSS clamping on the gateway.

> **Common pitfall:** The exact byte arithmetic differs by OS. The `-s` size is the ICMP *payload*; macOS/BSD `ping` also needs `-D` instead of `-M do`, and on Windows the flag is `ping -f -l 1472`.

> **Key Takeaway:** Network debugging is an essential skill for backend engineers. Use `curl -w` for HTTP timing analysis, `ss` for connection state inspection, `tcpdump` for packet-level debugging, and `mtr` for path analysis. Most production networking issues come down to: DNS misconfiguration, certificate problems, firewall blocking, connection exhaustion (TIME_WAIT), or MTU issues. Having these tools in your toolkit lets you quickly identify which layer the problem is at.

## Summary

This section followed a request from the wire up. The layered model is the organizing idea: each layer reads only its own header, which is precisely why you can debug one level at a time — and why knowing your private ranges, CIDR math, and NAT's outbound-only nature is daily work, not trivia. On top of IP sits TCP, whose handshake costs one round trip on every new connection; that single fact motivates connection pooling, keep-alive, and the TIME_WAIT and buffer-sizing discipline (size to the bandwidth-delay product) that high-traffic servers demand. HTTP's evolution is a series of escapes from transport limitations — persistent connections in 1.1, multiplexing in HTTP/2, QUIC replacing TCP in HTTP/3 — while caching headers remain the highest-leverage performance tool the protocol offers.

In real deployments you live behind intermediaries: a reverse proxy fronts your servers (TLS termination, load balancing), an API gateway adds application-aware concerns like auth and rate limiting, and the standing rule is to trust `X-Forwarded-For` only from proxies you operate. Two pillars support all of it. DNS turns names into addresses through a cached hierarchy governed by TTLs — lower them well before any migration, and use health-checked records for failover. TLS secures the channel: TLS 1.3 in one round trip, certificates verified through a chain of trust (a missing intermediate is the classic "verify failed"), and mTLS for service-to-service identity. When something breaks anyway, the debugging toolkit maps to the layers: `curl -w` for HTTP timing, `ss` for socket state, `dig` for DNS, `tcpdump` and `mtr` below that — and MTU black holes for the cases where small requests work and large ones silently hang.

This closes Chapter 1. With the fundamentals of how machines compute, store, schedule, and communicate in place, we turn from the platform to the language: Chapter 2 begins with **2.1 Language Internals**, opening up what actually happens inside the Python interpreter when your code runs.

*Last reviewed: 2026-06-08*

**Next:** [2.1 Language Internals](../02-python-deep-knowledge/language-internals.md)
