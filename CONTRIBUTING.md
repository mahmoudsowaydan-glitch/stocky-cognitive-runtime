# Contributing

Stocky Engineering OS is a self-observing cognitive operating kernel.

## Scope

This project is in early release (v0.1.0-rc1). The core architecture is
stable and validated through 1800+ tests. Contributions are welcome for:

- **Capability providers**: New stateless workers following the
  `(proposal, decision) → dict` contract
- **Tests**: Load tests, determinism tests, capability tests
- **Documentation**: Public docs, examples, architecture diagrams

## Constraints

- No modifications to P4 (policy authority) without prior discussion
- No modifications to RuntimeDaemon lifecycle state machine
- No networking, HTTP, or external I/O in the core runtime
- Capability providers must be stateless and return dict only
- All code must pass the existing 1800+ test suite

## Process

1. Open an issue describing the change
2. Fork and create a feature branch
3. Write tests first
4. Ensure `python -m pytest` passes
5. Submit a pull request

## Code Style

- Python 3.12+
- Type hints required for all public functions
- No external dependencies
- Follow existing patterns in `capabilities/` and `contracts/`
