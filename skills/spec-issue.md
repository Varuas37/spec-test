# spec-issue: Write a Detailed Issue

## Overview

This skill guides you through writing a detailed issue before creating specs. Issues document the **why** - intentions, context, trade-offs, and decisions.

## When to Use

- User asks to "add a feature" or "implement something new"
- User describes a problem that needs solving
- User wants to plan a change before coding
- Before writing any specs
- When you need to document a decision

## Why Issues First?

Issues provide context that specs alone cannot:

```
Issue (WHY)          Spec (WHAT)           Code (HOW)
    |                    |                     |
    v                    v                     v
"We need caching    "CACHE-001: API      def get_cached():
 because API calls   responses cached        ...
 are slow and        for 5 minutes"
 expensive. Redis
 vs in-memory?
 Chose in-memory
 for simplicity."
```

Without the issue, future developers won't know *why* caching was added or why in-memory was chosen over Redis.

## Issue Format

Issues live in `design/issues/` with naming: `NNN-short-name.md`

```markdown
# ISSUE-NNN: Short Title

## Summary
One paragraph describing what this issue is about.

## Motivation
Why are we doing this? What problem does it solve?
What happens if we don't do this?

## Detailed Description
Full details of the intended behavior:
- What should happen
- Edge cases to consider
- User-facing changes

## Options Considered

### Option A: [Name]
**Description**: How this approach works
**Pros**: Benefits
**Cons**: Drawbacks

### Option B: [Name]
**Description**: How this approach works
**Pros**: Benefits
**Cons**: Drawbacks

## Decision
Which option was chosen and why.

## Related Specs
Links to specs that implement this issue:
- [SPEC-001](../specs/feature.md)

## Status
- [x] Issue written
- [ ] Specs defined
- [ ] Implementation complete
- [ ] Tests passing
```

## Workflow

### Step 1: Understand the Request

Before writing, clarify:
1. **What** is being requested?
2. **Why** is it needed?
3. **Who** benefits from this?
4. **What** are the constraints?

Ask questions if unclear.

### Step 2: Research Options

Consider multiple approaches:
- What are the different ways to solve this?
- What are the trade-offs?
- What have others done?

### Step 3: Write the Issue

Create `design/issues/NNN-name.md` with:
- Clear motivation
- Detailed description
- Options considered with pros/cons
- Your recommended decision

### Step 4: Get Approval

Present the issue to the user for review before proceeding to specs.

### Step 5: Link to Specs

After approval, create specs and link them back to the issue.

## Example Issue

```markdown
# ISSUE-001: Add Response Caching

## Summary
Add caching layer for API responses to reduce latency and external API costs.

## Motivation
Our application makes repeated calls to the weather API for the same locations.
Each call costs $0.001 and takes 200-500ms. Users often check the same
locations multiple times per session.

Without caching:
- Poor user experience (slow responses)
- Unnecessary API costs (~$50/month wasted on duplicate calls)
- Risk of hitting rate limits

## Detailed Description
Cache API responses with a configurable TTL. Cache key should include:
- API endpoint
- Request parameters
- User context (if personalized)

Cache should be:
- Transparent to calling code
- Configurable per-endpoint
- Clearable on demand

## Options Considered

### Option A: Redis Cache
**Description**: Use Redis as external cache store
**Pros**:
- Shared across instances
- Persistent across restarts
- Battle-tested
**Cons**:
- Additional infrastructure
- Network latency for cache hits
- Operational complexity

### Option B: In-Memory Cache
**Description**: Use Python dict or lru_cache
**Pros**:
- Zero latency for hits
- No additional infrastructure
- Simple implementation
**Cons**:
- Not shared across instances
- Lost on restart
- Memory pressure on large caches

### Option C: HTTP Cache Headers
**Description**: Rely on HTTP caching via CDN
**Pros**:
- Standard approach
- Offloads to CDN
**Cons**:
- Less control over invalidation
- Requires CDN setup
- Not all APIs support it

## Decision
**Option B: In-Memory Cache** with TTL-based expiration.

Rationale:
- We run single-instance for now (no sharing needed)
- Simplicity is more valuable than persistence
- Can migrate to Redis later if needed

## Related Specs
- [CACHE-001](../specs/caching.md): Cache decorator implementation
- [CACHE-002](../specs/caching.md): TTL configuration

## Status
- [x] Issue written
- [ ] Specs defined
- [ ] Implementation complete
- [ ] Tests passing
```

## Commands

```bash
# After writing specs, verify they're linked
spec-test list-specs --specs design/specs

# Verify implementation
spec-test verify
```

## Checklist

Before moving to specs:

- [ ] Motivation is clear (why we need this)
- [ ] Multiple options were considered
- [ ] Pros/cons are documented
- [ ] Decision is justified
- [ ] Issue is saved in `design/issues/`
- [ ] User has approved the approach
