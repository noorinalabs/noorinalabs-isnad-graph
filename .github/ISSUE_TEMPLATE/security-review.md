---
name: Security Review Finding
about: Report a security vulnerability discovered during code review or audit
title: "security(SEVERITY): SHORT_DESCRIPTION"
labels: bug, security
assignees: ''
---

## Description

What is the vulnerability? Where in the code does it occur? Include file paths and line numbers.

## Risk

**Severity:** critical / high / medium / low

What can an attacker do if this is exploited? Be specific about the impact (e.g., "forge arbitrary JWTs", "enumerate all users", "bypass rate limiting").

## Affected Files

- `path/to/file.py:LINE` — brief description of the vulnerable code

## Reproduction

Step-by-step instructions to reproduce or exploit:

1. ...
2. ...
3. ...

## Recommended Fix

Provide a concrete fix with code snippets where possible. The engineer implementing the fix should be able to start from this recommendation without additional research.

```python
# Example fix
```
