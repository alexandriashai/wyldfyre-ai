# Infra Agent Mental Models

> Frameworks for reasoning about infrastructure, services, and deployments (stack-agnostic).

## Service Dependency Model

```
Startup Order (bottom to top):

┌─────────────────────────────────────────────────────┐
│  LAYER 5: FRONTEND                                  │
│  └── web clients, mobile apps                       │
│       ↓ depends on                                  │
├─────────────────────────────────────────────────────┤
│  LAYER 4: GATEWAY / LOAD BALANCER                   │
│  └── reverse proxy, API gateway                     │
│       ↓ depends on                                  │
├─────────────────────────────────────────────────────┤
│  LAYER 3: APPLICATION                               │
│  └── API servers, workers, schedulers               │
│       ↓ depends on                                  │
├─────────────────────────────────────────────────────┤
│  LAYER 2: DATA SERVICES                             │
│  └── databases, caches, message queues              │
│       ↓ depends on                                  │
├─────────────────────────────────────────────────────┤
│  LAYER 1: INFRASTRUCTURE                            │
│  └── networking, storage, secrets management        │
└─────────────────────────────────────────────────────┘

Shutdown Order: REVERSE (top to bottom)
```

**Health Check Priority**:
1. Infrastructure (network, storage)
2. Data services (databases, caches)
3. Application services
4. Gateway/Load balancer
5. External-facing services

**When to Use**: Service startup, health checks, debugging
**Key Insight**: Start dependencies first; stop dependents first.

---

## Resource Allocation Model

```
Service Resource Matrix:

┌──────────────────────────────────────────────────────────┐
│  SERVICE TYPE      │  CPU    │  MEMORY   │  NOTES       │
├──────────────────────────────────────────────────────────┤
│  Database          │  0.5-2  │  1-4 GB   │  Memory      │
│                    │         │           │  intensive   │
├──────────────────────────────────────────────────────────┤
│  Cache             │  0.25-1 │  512MB-2GB│  Memory      │
│                    │         │           │  bound       │
├──────────────────────────────────────────────────────────┤
│  API Server        │  0.5-2  │  256MB-1GB│  Scale       │
│                    │         │           │  horizontally│
├──────────────────────────────────────────────────────────┤
│  Worker            │  0.5-4  │  512MB-2GB│  CPU/Memory  │
│  (background jobs) │         │           │  depends     │
├──────────────────────────────────────────────────────────┤
│  Proxy/Gateway     │  0.1-0.5│  64-256MB │  Very light  │
└──────────────────────────────────────────────────────────┘

Scaling Decision:
- CPU bound? → Add more instances OR increase CPU limit
- Memory bound? → Increase memory limit (check for leaks)
- I/O bound? → Faster storage, connection pooling
```

**When to Use**: Service configuration, scaling decisions
**Key Insight**: Start conservative, scale based on metrics.

---

## SSL/Security Model

```
Certificate Lifecycle:

┌─────────────────────────────────────────────────────────┐
│                                                         │
│  ISSUE ──→ INSTALL ──→ MONITOR ──→ RENEW               │
│    │         │          │           │                  │
│    │         │          │           └─→ 30 days before │
│    │         │          │              expiry          │
│    │         │          │                              │
│    │         │          └─→ Check expiry weekly        │
│    │         │                                         │
│    │         └─→ Configure in proxy/app                │
│    │                                                   │
│    └─→ Auto-renewal (ACME) or manual (CA)             │
│                                                         │
└─────────────────────────────────────────────────────────┘

Security Layers:
┌─────────────────────────────────────────────────────────┐
│  1. NETWORK     │  Firewall, VPN, network policies     │
│  2. TRANSPORT   │  TLS/SSL, HTTPS only                 │
│  3. APPLICATION │  Auth, CORS, rate limiting           │
│  4. DATA        │  Encryption at rest, secrets mgmt    │
└─────────────────────────────────────────────────────────┘
```

**When to Use**: SSL setup, security audits
**Key Insight**: Defense in depth - no single layer is enough.

---

## Failure Recovery Model

```
Incident Response Flow:

DETECT ──→ ISOLATE ──→ RECOVER ──→ VERIFY ──→ POSTMORTEM
   │          │           │          │            │
   │          │           │          │            └─→ Document
   │          │           │          │               learnings
   │          │           │          │
   │          │           │          └─→ Health checks pass
   │          │           │              Logs clean
   │          │           │
   │          │           └─→ Restart service
   │          │              Rollback if needed
   │          │              Restore from backup
   │          │
   │          └─→ Stop bad service
   │             Redirect traffic
   │             Prevent cascade
   │
   └─→ Alerts fire
      Error rates spike
      Health checks fail

Rollback Triggers:
- Error rate > 5%
- P99 latency > 2x baseline
- Health checks failing
- User reports of errors
```

**When to Use**: Incident response, deployment monitoring
**Key Insight**: Fast rollback > perfect debugging under pressure.

---

## Deployment Risk Model

```
Risk Assessment:

┌─────────────────────────────────────────────────────────┐
│  CHANGE TYPE           │  RISK    │  STRATEGY          │
├─────────────────────────────────────────────────────────┤
│  Config change only    │  LOW     │  Rolling update    │
│  (env vars, flags)     │          │                    │
├─────────────────────────────────────────────────────────┤
│  Minor code change     │  MEDIUM  │  Canary deploy     │
│  (bug fix, small feat) │          │  10% → 50% → 100%  │
├─────────────────────────────────────────────────────────┤
│  Major feature         │  HIGH    │  Blue/Green        │
│  (new functionality)   │          │  Feature flags     │
├─────────────────────────────────────────────────────────┤
│  Database migration    │  HIGHEST │  Maintenance window│
│  (schema changes)      │          │  Full backup first │
└─────────────────────────────────────────────────────────┘

Deployment Timing:
- Best: Tuesday-Thursday morning
- Acceptable: Monday afternoon, Friday morning
- Avoid: Friday afternoon, weekends, holidays
```

**When to Use**: Planning deployments, change management
**Key Insight**: Match deployment strategy to change risk.

---

*Last updated: 2026-01-26*
