# Compliance Report

**Scenario:** Cross-border data transfer without DPA
**Risk Level:** High
**Generated:** 2026-03-10

## Findings

1. **Missing Data Processing Agreement** — GDPR Art. 28 requires a signed DPA with all data processors.
2. **Unlawful Third-Country Transfer** — GDPR Art. 46 requires appropriate safeguards (SCCs, BCRs) for transfers outside the EEA.
3. **Incomplete Privacy Notice** — GDPR Art. 13/14 mandates disclosure of transfer destinations to data subjects.

## Risk Score

| Finding | Severity | Score |
|---------|----------|-------|
| Missing DPA | High | 8/10 |
| Unlawful transfer | Critical | 10/10 |
| Incomplete notice | Medium | 6/10 |

**Overall Score: 8.0 / 10**

## Remediation Steps

- [ ] Execute a DPA with the Indian cloud provider.
- [ ] Implement Standard Contractual Clauses (SCCs) for the EU→IN transfer.
- [ ] Update the privacy policy to disclose the transfer and its legal basis.
- [ ] Conduct a Transfer Impact Assessment (TIA).
