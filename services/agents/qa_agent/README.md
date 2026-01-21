# QA Agent

The QA Agent is a specialized AI agent for testing, code review, security validation, and end-to-end browser automation within the Wyld Fyre AI Infrastructure.

## Capabilities

### Testing
- **run_tests** - Execute pytest with various options
- **list_tests** - List available test cases
- **run_coverage** - Generate coverage reports
- **run_lint** - Run linting tools

### Type Checking & Linting
- **run_mypy** - Static type analysis
- **check_type_coverage** - Check type annotation coverage
- **run_ruff** - Fast Python linting and auto-fix

### API Testing
- **test_api_endpoint** - Test individual endpoints
- **test_api_batch** - Run batch API tests
- **validate_json_schema** - Validate responses against schemas
- **measure_api_performance** - Measure response times
- **check_api_health** - Check multiple endpoint health

### Code Review
- **review_changes** - Review git changes for issues
- **analyze_code_quality** - Analyze code quality metrics
- **check_dependencies** - Verify dependency configurations

### Security Validation
- **check_secrets** - Scan for hardcoded secrets
- **scan_dependencies** - Check for vulnerable dependencies
- **validate_permissions** - Check file permissions

### Browser Automation (E2E Testing)

#### Lifecycle Management
- **browser_launch** - Launch browser (Chromium, Firefox, WebKit)
- **browser_close** - Close browser instance
- **browser_close_all** - Close all browsers (cleanup)
- **browser_list** - List active browsers
- **browser_context_create** - Create isolated context
- **browser_context_close** - Close context

#### Page Navigation
- **page_new** - Create new page
- **page_goto** - Navigate to URL
- **page_reload** - Reload page
- **page_go_back/forward** - Browser history
- **page_get_url/title/content** - Get page info
- **page_wait_for_selector/load_state/url** - Wait operations
- **page_evaluate** - Execute JavaScript

#### Element Interactions
- **element_click/dblclick/hover** - Mouse actions
- **element_fill/type/clear** - Input actions
- **element_press/focus** - Keyboard actions
- **element_select_option** - Dropdown selection
- **element_check/uncheck** - Checkbox control
- **element_drag_drop** - Drag and drop
- **element_upload_file** - File uploads
- **element_query/query_all/count** - Element queries
- **element_get_text/attribute** - Get element info
- **element_is_visible/enabled** - Check state

#### Assertions
- **expect_element_visible/hidden/enabled** - State assertions
- **expect_element_text/value/attribute** - Content assertions
- **expect_page_url/title** - Page assertions
- **expect_element_count/checked/focused** - Count/state assertions

#### Capture
- **screenshot_page/element** - Take screenshots
- **video_start/stop** - Record video
- **trace_start/stop** - Capture Playwright traces
- **pdf_export** - Export page as PDF

#### Network
- **network_intercept_enable** - Enable interception
- **network_mock_response/json** - Mock responses
- **network_block_urls** - Block URL patterns
- **network_get_requests** - Get captured requests
- **network_wait_for_response/request** - Wait for network
- **network_clear_interceptors** - Clear interceptors

#### Authentication
- **credential_store** - Store encrypted credentials
- **credential_get/rotate/list/delete** - Manage credentials
- **auth_login/logout** - Login/logout flows
- **auth_save/load_session** - Session state management
- **auth_list/delete_session** - Session management

## Configuration

### Environment Variables
```bash
REDIS_HOST=redis
POSTGRES_HOST=postgres
QDRANT_HOST=qdrant
CREDENTIAL_ENCRYPTION_KEY=<fernet-key>  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Permission Level
The QA Agent operates at **Permission Level 1** (READ_WRITE) for most tools, with **Level 2** (EXECUTE) for:
- File uploads
- Video recording
- Network interception
- Credential storage
- JavaScript evaluation

## Usage Examples

### Run Tests
```json
{
  "tool": "run_tests",
  "arguments": {
    "path": "tests/",
    "markers": "not slow",
    "verbose": true
  }
}
```

### Browser E2E Test
```json
// Launch browser
{"tool": "browser_launch", "arguments": {"browser_type": "chromium", "headless": true}}

// Create context and page
{"tool": "browser_context_create", "arguments": {"browser_id": "browser_123"}}
{"tool": "page_new", "arguments": {"context_id": "ctx_123"}}

// Navigate and interact
{"tool": "page_goto", "arguments": {"page_id": "page_123", "url": "https://app.wyldfyre.ai/login"}}
{"tool": "element_fill", "arguments": {"page_id": "page_123", "selector": "[data-testid='email']", "value": "test@example.com"}}
{"tool": "element_fill", "arguments": {"page_id": "page_123", "selector": "[data-testid='password']", "value": "secret"}}
{"tool": "element_click", "arguments": {"page_id": "page_123", "selector": "[data-testid='login-btn']"}}

// Assert
{"tool": "expect_page_url", "arguments": {"page_id": "page_123", "url": "/dashboard"}}
```

### Store and Use Credentials
```json
// Store credential
{
  "tool": "credential_store",
  "arguments": {
    "app_name": "wyld-web",
    "username": "test@wyldfyre.ai",
    "password": "secret123",
    "role": "admin"
  }
}

// Login with stored credential
{
  "tool": "auth_login",
  "arguments": {
    "page_id": "page_123",
    "app_name": "wyld-web",
    "role": "admin"
  }
}
```

## Architecture

```
services/agents/qa_agent/
├── src/
│   └── qa_agent/
│       ├── __init__.py
│       ├── agent.py              # Main agent class
│       ├── browser_config.py     # Browser configuration
│       ├── browser_manager.py    # Browser pool singleton
│       ├── credential_store.py   # Encrypted credential storage
│       ├── browser_fixtures.py   # Test fixtures
│       ├── browser_helpers.py    # Page Object Model
│       └── tools/
│           ├── __init__.py
│           ├── test_tools.py        # pytest integration
│           ├── type_checking_tools.py  # mypy, ruff
│           ├── api_test_tools.py    # API testing
│           ├── review_tools.py      # Code review
│           ├── security_tools.py    # Security scanning
│           ├── browser_tools.py     # Browser lifecycle
│           ├── browser_actions.py   # Element interactions
│           ├── browser_assertions.py # Playwright assertions
│           ├── browser_capture.py   # Screenshots/video/trace
│           ├── browser_network.py   # Network interception
│           └── browser_auth.py      # Authentication
├── pyproject.toml
└── README.md
```

## Browser Resource Management

- Maximum 3 concurrent browsers
- Maximum 5 contexts per browser
- Maximum 10 pages per context
- Automatic cleanup after idle timeout
- Resources cleaned up on task completion/error

## Security

- Credentials encrypted with AES-256-GCM (Fernet)
- Session states stored encrypted
- No plaintext passwords in logs
- Credentials scoped to user_id

## Dependencies
- ai-core, ai-messaging, ai-memory, base-agent
- playwright - Browser automation
- cryptography - Credential encryption
- Pillow - Image processing for visual diff
- aiofiles - Async file operations

## Running

### With Docker Compose
```bash
docker compose up -d qa-agent
```

### Standalone
```bash
# Install Playwright browsers first
playwright install chromium

python -m services.agents.qa_agent.src.qa_agent.agent
```

## Volumes
- `/app/screenshots` - Screenshot output
- `/app/traces` - Playwright traces

## Logs
Logs are written to `/home/wyld-data/logs/agents/qa-agent.log`
