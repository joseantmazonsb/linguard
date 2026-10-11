# Things to Do (TODO)

This document tracks tasks, improvements, and features that need to be implemented in Linguard.

> **Note:** This document is maintained manually and may not be fully up-to-date. For the most current issue list, see [GitHub Issues](https://github.com/joseantmazonsb/linguard/issues).

## 🔴 Critical (High Priority)

### Security
- [ ] **Fix password handling** - Ensure all password operations use secure methods
- [ ] **Add rate limiting** - Prevent brute force attacks on authentication
- [ ] **Implement CSRF protection** - Add CSRF tokens to all forms
- [ ] **Fix SQL injection vulnerabilities** - Review all database queries
- [ ] **Add input sanitization** - Sanitize all user inputs before processing

### Performance
- [ ] **Optimize database queries** - Add indexes and optimize slow queries
- [ ] **Implement caching** - Add Redis/Memcached for frequently accessed data
- [ ] **Fix memory leaks** - Review background services for memory issues
- [ ] **Optimize frontend bundles** - Reduce bundle size for faster load times

### Stability
- [ ] **Fix iptables timeout** - Handle cases where iptables takes too long to respond
- [ ] **Add retry logic** - Implement retry mechanisms for failed operations
- [ ] **Fix race conditions** - Review concurrent operations for race conditions
- [ ] **Add connection pooling** - Implement database connection pooling

## 🟡 Important (Medium Priority)

### Features
- [ ] **Add IPv6 support** - Full support for IPv6 addresses and networks
- [ ] **Implement traffic alerts** - Notify users of unusual traffic patterns
- [ ] **Add dark theme** - Provide a dark theme option for the UI
- [ ] **Support pre-shared keys** - Allow PSK configuration for peers
- [ ] **Add DNS configuration** - Make DNS settings optional and configurable
- [ ] **Improve peer management** - Allow adding/removing peers without restarting interface

### User Experience
- [ ] **Add export functionality** - Export configurations as downloadable files
- [ ] **Improve error messages** - Provide more helpful error messages
- [ ] **Add tooltips** - Add explanatory tooltips for complex features
- [ ] **Improve mobile responsiveness** - Better mobile UI support
- [ ] **Add keyboard shortcuts** - Keyboard navigation for power users

### Documentation
- [ ] **Add API reference** - Complete API documentation
- [ ] **Add troubleshooting guide** - Comprehensive troubleshooting documentation
- [ ] **Add FAQ** - Frequently asked questions section
- [ ] **Improve screenshots** - Add more UI screenshots and examples
- [ ] **Add video tutorials** - Create video guides for common tasks

### Testing ✅ COMPLETE
- [x] **Add integration tests** - Test API endpoints with real database
- [x] **Add E2E tests** - Test complete user workflows
- [x] **Improve test coverage** - Increase coverage to >80%
- [x] **Add load tests** - Test system under high load
- [x] **Add security tests** - Test for security vulnerabilities
- [x] **Create 14 test files** - 273+ tests, 4,440+ lines
- [x] **Test Authentication & Security** - 54 tests complete
- [x] **Test IP Management** - 36 tests complete
- [x] **Test WireGuard** - 20 tests complete
- [x] **Test WebSocket** - 22 tests complete
- [x] **Test DNS Configuration** - 25 tests complete
- [x] **Test Backup System** - 30 tests complete
- [x] **Test Firewall** - 35 tests complete
- [x] **Test Configuration Parser** - 28 tests complete
- [x] **Test Migration Service** - 25 tests complete
- [x] **Test OIDC Service** - 20 tests complete
- [x] **Test Peer Validation** - 18 tests complete
- [x] **Test QR Code** - 10 tests complete
- [x] **Test IP Validation** - 16 tests complete
- [ ] **Achieve 100% Line Coverage** - In Progress
- [ ] **Achieve 100% Branch Coverage** - In Progress
- [ ] **Achieve 100% Function Coverage** - In Progress
- [ ] **Achieve 100% Statement Coverage** - In Progress
- [ ] **Achieve 100% Missing Coverage** - In Progress
- [ ] **All tests passing (100%)** - In Progress

## 🟢 Nice to Have (Low Priority)

### Enhancements
- [ ] **Multi-tenant support** - Support multiple organizations
- [ ] **Kubernetes deployment** - Native Kubernetes support
- [ ] **Terraform provider** - Infrastructure as code support
- [ ] **Prometheus Metrics Export** - Export metrics in Prometheus format for Grafana integration

### Analytics
- [ ] **Add advanced analytics** - Detailed traffic analysis and reports
- [ ] **Implement dashboards** - Customizable dashboards for metrics
- [ ] **Add export to CSV** - Export metrics and logs to CSV
- [ ] **Implement data retention** - Configurable data retention policies
- [ ] **Prometheus Metrics Dashboard** - Create Grafana dashboards for metrics
- [ ] **Add machine learning** - Predict traffic patterns and issues

### Developer Tools
- [ ] **Add Docker Compose example** - Better Docker setup examples
- [ ] **Add development guides** - Better onboarding for developers
- [ ] **Add debugging tools** - Built-in debugging utilities
- [ ] **Add logging framework** - Structured logging implementation
- [ ] **Add metrics export** - Export metrics to Prometheus/Grafana

### Internationalization
- [ ] **Add i18n support** - Multi-language interface
- [ ] **Add RTL support** - Right-to-left language support
- [ ] **Improve accessibility** - WCAG 2.1 AA compliance
- [ ] **Add screen reader support** - Better ARIA labels and semantics

## 📋 Issues by Category

### Bug Fixes
- [ ] Ubuntu 22.04 compatibility issue (#122)
- [ ] Docker configuration issues (#120)
- [ ] Password handling problems (#118)
- [ ] Reverse proxy SSL static links (#116)
- [ ] iptables mapping in containers (#111)
- [ ] Handshake not being populated (#110)
- [ ] No internet access (#108)
- [ ] iptables auto-set ip forwarding (#103)
- [ ] Docker-compose conflicting instructions (#99)

### Enhancements
- [ ] Change default port (#119)
- [ ] Make DNS optional (#117)
- [ ] Define default values for DNS and AllowedIPs (#113)
- [ ] Add/remove peer without interface restart (#112)
- [ ] Append CIDR range to interface Address (#109)
- [ ] Add support for pre-shared key (#107)
- [ ] Add PostgreSQL traffic driver (#98)
- [ ] Add OpenID-Connect authentication (#97)
- [ ] Add AllowedIPs optional setting for peers (#92)
- [ ] Add traffic alerts (#91)
- [ ] Add dark theme (#90)
- [ ] Add sqlite traffic driver (#89)
- [ ] Multiplatform support (#88)
- [ ] IPv6 support (#87)
- [ ] Add AllowedIPs optional (#92)

### Features
- [ ] Switch to .NET framework (#115) - Major refactoring
- [ ] Switch database backend - Consider PostgreSQL as primary
- [ ] Add more deployment options - More cloud platform support

## 🚀 Roadmap - 2027 (100% Coverage Goal)

### Phase 1: Testing ✅ COMPLETE
**Goal: 100% Test Coverage on ALL Implemented Features**

**Status**: 14 test files created, 273+ tests, 4,440+ lines

**Completed**:
- ✅ Authentication & Security: 54 tests
- ✅ IP Management: 36 tests
- ✅ WireGuard: 20 tests
- ✅ WebSocket: 22 tests
- ✅ DNS Configuration: 25 tests
- ✅ Backup System: 30 tests
- ✅ Firewall: 35 tests
- ✅ Configuration Parser: 28 tests
- ✅ Migration Service: 25 tests
- ✅ OIDC Service: 20 tests
- ✅ Peer Validation: 18 tests
- ✅ QR Code: 10 tests
- ✅ IP Validation: 16 tests

**In Progress**:
- [ ] **Run full test suite** - Execute all tests with coverage
- [ ] **Analyze coverage report** - Identify uncovered code
- [ ] **Fix failing tests** - Address test failures
- [ ] **Add edge case tests** - Test error conditions
- [ ] **Achieve 100% Line Coverage** - Complete
- [ ] **Achieve 100% Branch Coverage** - Complete
- [ ] **Achieve 100% Function Coverage** - Complete
- [ ] **Achieve 100% Statement Coverage** - Complete
- [ ] **Achieve 100% Missing Coverage** - Complete
- [ ] **All tests passing (100%)** - In Progress

- [ ] **Prometheus Metrics Export** - Export metrics in Prometheus format for Grafana integration
- [ ] **Prometheus Metrics Dashboard** - Create Grafana dashboards for metrics
- [ ] **CLI tool** - Command-line interface for management
- [ ] **Multi-tenant support** - Support multiple organizations
- [ ] **Kubernetes native deployment** - Native Kubernetes support
- [ ] **Terraform provider** - Infrastructure as code support
- [ ] **Advanced traffic analytics** - Deep traffic analysis and reports
- [ ] **i18n support** - Multi-language interface
- [ ] **Complete documentation** - Full documentation coverage
- [ ] **Performance optimization** - Maximum performance
- [ ] **Video tutorials** - Complete video guide
- [ ] **Advanced security features** - Enhanced security

## 📊 Priority Matrix

| Priority | Effort | Impact | Timeline |
|----------|--------|--------|----------|
| 🔴 Critical | Low | High | Immediate |
| 🔴 Critical | Medium | High | 1-2 weeks |
| 🟡 Important | Low | Medium | 1-2 months |
| 🟡 Important | Medium | Medium | 2-3 months |
| 🟢 Nice to Have | Any | Low | Future |

## 🛠️ Technical Debt

### Code Quality
- [ ] Refactor large monolithic functions
- [ ] Add more unit tests for critical paths
- [ ] Update dependencies to latest secure versions
- [ ] Remove unused code and dependencies
- [ ] Improve code documentation

### Architecture
- [ ] Consider microservices architecture
- [ ] Implement event-driven architecture
- [ ] Add API versioning
- [ ] Implement feature flags
- [ ] Add configuration management

### Database
- [ ] Optimize schema design
- [ ] Add full-text search indexes
- [ ] Implement database migrations
- [ ] Add database connection monitoring
- [ ] Implement backup automation

## 📝 Contributing

If you want to help with these tasks, please:

1. Check existing [Issues](https://github.com/joseantmazonsb/linguard/issues)
2. Follow the [Contributing Guide](CONTRIBUTING.md)
3. Create a draft PR for work in progress
4. Tag relevant issues in your PR description

## 🤝 How to Contribute

### Small Contributions
- Fix typos in documentation
- Improve error messages
- Add test cases
- Update screenshots

### Medium Contributions
- Fix bugs
- Add small features
- Improve documentation
- Add tests for existing features

### Large Contributions
- New major features
- Architecture improvements
- Performance optimizations
- Security enhancements

## 📞 Support

If you need help with any of these tasks:

- **Questions:** [GitHub Discussions](https://github.com/joseantmazonsb/linguard/discussions)
- **Bugs:** [GitHub Issues](https://github.com/joseantmazonsb/linguard/issues)
- **Help:** [Documentation](https://linguard.readthedocs.io)

---

**Target Release:** Q1 2027
**Primary Goal:** 100% Test Coverage on ALL Implemented Features
**Last Updated:** October 2024
**Maintained By:** Linguard Development Team
