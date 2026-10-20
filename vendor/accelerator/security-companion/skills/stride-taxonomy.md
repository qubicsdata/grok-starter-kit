---
name: stride-taxonomy
description: Invoke at the start of STRIDE threat analysis — provides category definitions, design-level threat examples, and per-category question checklists, and enforces the coverage gate requiring all six categories to be explicitly addressed.
---

# STRIDE Taxonomy

Import this skill at the start of any STRIDE analysis. Use the question checklists to drive systematic coverage. Do not move to output until all six categories have been addressed.

## Coverage Gate

**STOP before producing a threat register until all six STRIDE categories below have been analyzed. If zero threats are found for a category, include an explicit entry: "No threats identified for [category] — rationale: [reason]". Silent omission of any category is a violation.**

---

## S — Spoofing

**Full expansion:** Spoofing Identity

**Security property violated:** Authentication — the assurance that an entity is who it claims to be.

**Design-level threat examples:**
1. An attacker sends requests to a service endpoint while presenting a forged or stolen client certificate, impersonating a trusted peer service.
2. A mobile client receives a fake OAuth2 authorization code redirect from a malicious app that registered the same custom URL scheme, enabling authorization code theft.
3. An internal service accepts a `X-Internal-User-Id` header from any caller without verifying the caller is an authorized gateway, allowing identity injection.
4. A webhook receiver does not validate the signature on incoming payloads, allowing any party to send events claiming to be from the legitimate event source.

**Question checklist (ask for each entry point and service):**
- Can an actor impersonate another actor (user, service, or external partner) by forging a token, certificate, or header?
- Is there a mechanism to verify that the caller is who it claims to be at each trust boundary crossing?
- Can the authentication mechanism be bypassed by presenting a partial or modified credential?

---

## T — Tampering

**Full expansion:** Tampering with Data

**Security property violated:** Integrity — the assurance that data has not been modified without authorization.

**Design-level threat examples:**
1. An attacker intercepts a message on a semi-trusted internal network and modifies the order quantity before it reaches the payment service, because the message bus does not enforce message signing.
2. A client-supplied JSON payload includes an `isAdmin: true` field that the API server deserializes and trusts without re-validating against server-side authorization state.
3. A shared database is writable by multiple services; one compromised service can modify records that other services read and trust without re-checking integrity.
4. A signed JWT token's algorithm field is changed to `none` and the signature is stripped; the server accepts it if it does not enforce algorithm pinning.

**Question checklist:**
- Is there a mechanism (signing, HMAC, or access control) that prevents unauthorized modification of data in transit or at rest at each trust boundary?
- Can a client-supplied value flow into a server-side trust decision without server-side re-validation?
- Are shared data stores protected such that one compromised service cannot corrupt data relied upon by other services?

---

## R — Repudiation

**Full expansion:** Repudiation

**Security property violated:** Non-repudiation — the assurance that an entity cannot deny having performed an action.

**Design-level threat examples:**
1. A payment initiation API logs the user session ID but not the authenticated user identity, so a user can claim they did not initiate a transaction that was completed under their session.
2. An admin action endpoint has no audit log — after a data deletion event, there is no record of which admin account triggered it.
3. An event-sourced system does not sign or timestamp events at creation, allowing events to be reordered or back-dated without detection.
4. A file upload feature records that a file was uploaded but not who uploaded it or what the original file content hash was, making tampering with the stored file undetectable.

**Question checklist:**
- Is there a tamper-evident audit log for all sensitive operations (financial, administrative, data-modifying)?
- Does the audit log record the authenticated identity (not just a session ID) of the actor who performed each action?
- Are high-value events signed or timestamped such that their ordering and integrity can be verified after the fact?

---

## I — Information Disclosure

**Full expansion:** Information Disclosure

**Security property violated:** Confidentiality — the assurance that information is accessible only to authorized entities.

**Design-level threat examples:**
1. An API error response includes a full stack trace that reveals internal service names, database schema, and framework version to external callers.
2. A search endpoint returns all fields of matched records including fields the caller is not authorized to see, relying on the client to filter display — a mass assignment / over-fetch vulnerability at the design level.
3. A logging pipeline captures request bodies and ships them to a centralized log aggregator without scrubbing PII or authentication tokens, exposing sensitive data to log system operators.
4. A presigned URL for object storage is generated with a 7-day expiry and included in an email, where it could be forwarded or captured by mail scanning systems.

**Question checklist:**
- Can sensitive data (credentials, PII, internal system details) be inferred from error messages, log entries, or API responses by an unauthorized caller?
- Does the design apply a principle of data minimization — returning only the data the caller is authorized to receive?
- Are data flows that carry sensitive data encrypted in transit and with appropriate access controls at rest?

---

## D — Denial of Service

**Full expansion:** Denial of Service

**Security property violated:** Availability — the assurance that a system or service is accessible when needed.

**Design-level threat examples:**
1. A public-facing search API has no rate limiting; an attacker sends 10,000 concurrent search requests with complex queries, exhausting database connection pools and degrading service for all users.
2. A file upload endpoint imposes no size limit on uploaded files; an attacker uploads a 10 GB file, consuming all available storage on the processing service.
3. A microservice's circuit breaker is not configured; when a downstream dependency becomes slow, the calling service accumulates thread pool exhaustion as every request waits for the slow dependency, cascading into a full service outage.
4. A message queue consumer has no dead-letter queue; a malformed message that triggers a processing exception is retried indefinitely, blocking all subsequent messages in the queue.

**Question checklist:**
- Are rate limits and resource quotas (request rate, payload size, connection count) applied at each public-facing or semi-trusted entry point?
- Does the design include a circuit breaker or bulkhead pattern for calls to external or slow dependencies?
- Is there a dead-letter queue or poison-message handling strategy for all message queue consumers?

---

## E — Elevation of Privilege

**Full expansion:** Elevation of Privilege

**Security property violated:** Authorization — the assurance that an entity can only perform actions they are authorized to perform.

**Design-level threat examples:**
1. An API endpoint checks the user's role at request entry but does not re-check after an object is fetched, allowing a user to modify an object owned by another user by supplying a different object ID (Insecure Direct Object Reference at the design level).
2. An internal admin API is accessible on the same port and hostname as the public API, separated only by a URL prefix; a misconfigured nginx rule could expose admin endpoints to public traffic.
3. A service runs with a cloud IAM role that has `s3:*` permissions on all buckets; if the service is compromised, an attacker can read or delete all company data across all S3 buckets.
4. A JWT includes a `role: user` claim that the backend trusts; an attacker who can forge or modify the token (see Tampering) can escalate to `role: admin`.

**Question checklist:**
- Is authorization re-checked at the resource level (not just the endpoint level) — i.e., does the system verify the caller is authorized to access THIS specific resource, not just any resource of this type?
- Are privileged internal APIs isolated from public surfaces at the network layer (separate port, VPC, or explicit network policy), not only at the URL-path level?
- Does the design apply least privilege to all service accounts, IAM roles, and database credentials?

---

## Hard Gate

**NEVER return a STRIDE analysis without explicit coverage of all six categories.**
**NEVER silently omit a category with zero findings — include the explicit no-threat entry with rationale.**
