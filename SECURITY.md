# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | Yes                |
| < 1.0   | No                 |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

**Option 1: GitHub Security Advisories (Preferred)**

1. Go to the [Security tab](https://github.com/wyldfyre-ai/wyld-core/security) of this repository
2. Click "Report a vulnerability"
3. Fill out the security advisory form

**Option 2: Email**

Send details to: **security@wyldfyre.ai**

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution Timeline**: Depends on severity, typically 30-90 days

### Disclosure Policy

- Please do not publicly disclose the vulnerability until we have addressed it
- We will credit you in the security advisory (unless you prefer anonymity)
- We will notify you when the fix is released

## Security Best Practices

When deploying Wyld Fyre AI:

1. **Environment Variables**: Never commit `.env` files or API keys
2. **Network Security**: Use firewalls and restrict port access
3. **Updates**: Keep all dependencies updated
4. **Access Control**: Use strong passwords and limit admin access
5. **Monitoring**: Review logs regularly for suspicious activity

## Scope

The following are in scope for security reports:

- Wyld Fyre AI core application
- Official Docker images
- API endpoints
- Agent communication protocols
- Memory system security

Out of scope:

- Third-party services (Claude API, OpenAI, etc.)
- User misconfiguration
- Social engineering

Thank you for helping keep Wyld Fyre AI secure!
