# Infra Agent Strategies

> Proven multi-step patterns for infrastructure operations (stack-agnostic).

## Service Deployment Strategy

**Success Rate**: 95%
**When to Use**: Deploying or updating services

**Pattern**:
```
1. CHECK DEPS   → Verify dependencies are healthy
                 - Database responding?
                 - Cache available?
                 - Required services up?

2. PULL/BUILD  → Get the new service version
                 - Pull image/artifact
                 - Verify integrity (hash/signature)

3. BACKUP STATE → Preserve current state
                 - Note current version
                 - Export any stateful data
                 - Record current config

4. STOP OLD     → Gracefully stop current service
                 - Allow connections to drain
                 - Wait for graceful shutdown
                 - Timeout after reasonable period

5. START NEW    → Launch new service
                 - Apply resource limits
                 - Mount storage
                 - Inject environment/config

6. HEALTH CHECK → Verify service is healthy
                 - Health endpoint responds?
                 - Can connect to dependencies?
                 - Logs show no errors?

7. SMOKE TEST   → Basic functionality check
                 - Key endpoints responding?
                 - Sample requests succeed?
```

**Rollback Trigger**: Any health check failure → immediately restart previous version

---

## SSL Certificate Renewal

**Success Rate**: 99%
**When to Use**: Certificate nearing expiration

**Pattern**:
```
1. CHECK EXPIRY → Verify current cert status
                 - Check certificate end date
                 - Confirm renewal is needed

2. BACKUP CERTS → Preserve current certificates
                 - Copy current cert files
                 - Record current working config

3. RENEW CERT   → Obtain new certificate
                 - Auto-renewal (ACME/Let's Encrypt)
                 - Or manual request from CA

4. INSTALL CERT → Place new cert files
                 - Copy to correct location
                 - Verify permissions (restricted)
                 - Check file ownership

5. VERIFY CERT  → Validate new certificate
                 - Verify certificate chain
                 - Check full chain is present
                 - Confirm correct domain

6. RELOAD SVC   → Apply new certificate
                 - Reload proxy/server config
                 - No full restart needed typically

7. TEST SSL     → Verify SSL is working
                 - Test HTTPS connection
                 - Check certificate details
                 - Verify no mixed content
```

**Automation**: Set up auto-renewal + scheduled checks

---

## Service Troubleshooting

**Success Rate**: 91%
**When to Use**: Service not behaving as expected

**Pattern**:
```
1. LOGS        → Check service logs
                - Recent error messages
                - Startup logs
                - Warning patterns

2. STATUS      → Inspect service state
                - Is it running?
                - Health status
                - Restart count

3. SHELL       → Get inside service (if possible)
                - Check processes
                - Check connectivity
                - File system state

4. NETWORK     → Diagnose networking
                - DNS resolution working?
                - Can reach dependencies?
                - Ports accessible?

5. RESOURCES   → Check resource usage
                - Memory usage
                - CPU usage
                - Disk space

6. RESTART     → Attempt restart if needed
                - Graceful restart first
                - Watch logs during startup
                - Monitor for recurring issues

7. ESCALATE    → If still broken
                - Recreate service
                - Check host system
                - Review recent changes
```

**Common Issues & Fixes**:
- Out of memory → Increase memory limit or fix leak
- Restart loop → Check entrypoint, dependencies
- Network unreachable → Check DNS, firewall

---

## Resource Scaling Strategy

**Success Rate**: 88%
**When to Use**: Service performance degradation

**Pattern**:
```
1. MONITOR     → Identify the bottleneck
                - CPU usage > 80% sustained?
                - Memory usage > 85%?
                - Network/IO saturated?

2. ANALYZE     → Understand the cause
                - Traffic spike?
                - Memory leak?
                - Inefficient code?

3. PLAN        → Choose scaling approach
                - Vertical: More resources per instance
                - Horizontal: More instances
                - Optimization: Fix root cause

4. SCALE       → Apply the change
                - Update resource limits
                - Add replicas
                - Deploy optimized code

5. VERIFY      → Confirm improvement
                - Metrics improving?
                - Latency decreasing?
                - Error rate dropping?

6. DOCUMENT    → Record what was done
                - Update runbook
                - Set alerts for future
                - Plan permanent fix if temporary
```

**Scaling Decision Tree**:
```
Is it CPU bound?
├── Yes → Can code be optimized?
│         ├── Yes → Optimize first
│         └── No → Scale horizontally
└── No → Is it memory bound?
          ├── Yes → Memory leak?
          │         ├── Yes → Fix leak
          │         └── No → Increase limit
          └── No → Check I/O, network
```

---

## Disaster Recovery Strategy

**Success Rate**: 94%
**When to Use**: Major outage, data loss, security incident

**Pattern**:
```
1. ASSESS      → Determine scope of incident
                - What systems affected?
                - Data loss? How much?
                - Security breach?

2. STOP TRAFFIC→ Prevent further damage
                - Enable maintenance mode
                - Redirect to status page
                - Stop writes if data issue

3. COMMUNICATE → Notify stakeholders
                - Status page update
                - Team notification
                - User communication if needed

4. RESTORE     → Begin recovery
                - Identify last good backup
                - Restore to staging first
                - Verify data integrity

5. VERIFY      → Confirm recovery success
                - All services healthy?
                - Data complete and correct?
                - No security gaps remain?

6. RESUME      → Bring back online
                - Gradually restore traffic
                - Monitor closely
                - Ready to rollback

7. POSTMORTEM  → Learn from incident
                - Timeline of events
                - Root cause analysis
                - Prevention measures
```

**Recovery Time Objectives**:
- Critical services: < 1 hour
- Important services: < 4 hours
- Standard services: < 24 hours

---

*Last updated: 2026-01-26*
