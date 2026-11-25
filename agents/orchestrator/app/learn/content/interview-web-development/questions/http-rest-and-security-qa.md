---
title: HTTP, REST APIs and web security questions
summary: REST principles, status codes, authentication, CORS, cookies versus tokens and common attacks.
kind: qa
takeaways:
- Design and explain a REST API
- Know authentication methods and where tokens are stored
- Name common attacks (XSS, CSRF, SQL injection) and fixes
---
### Q [Easy] What is a REST API?
An API that uses HTTP methods on **resources** identified by URLs (`GET /students/5`), is **stateless** (each request carries what the server needs) and usually exchanges JSON.

### Q [Medium] PUT vs PATCH vs POST?
`POST` creates a resource. `PUT` **replaces** a resource completely. `PATCH` changes **part** of a resource. `PUT` and `DELETE` are **idempotent** (repeating them has the same effect as doing it once).

### Q [Medium] What does stateless mean?
The server does not remember the client between requests; every request has all the information (such as an auth token). This makes servers easy to scale.

### Q [Medium] Which status codes should an API use?
200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorised (not logged in), 403 Forbidden (not allowed), 404 Not Found, 409 Conflict, 422 Unprocessable Entity (validation), 429 Too Many Requests, 500 Internal Server Error.

### Q [Medium] Authentication vs authorisation?
**Authentication** proves who you are (login). **Authorisation** decides what you may do (permissions).

### Q [Medium] Sessions with cookies vs JWT tokens?
A **session** stores state on the server and gives the browser a session id cookie. A **JWT** is a signed token carrying claims, which the client sends with each request; the server verifies it without storing a session. JWTs scale easily but are hard to revoke, so keep them short-lived with refresh tokens.

### Q [Medium] What is CORS?
A browser rule that blocks a web page from calling another **origin** (different domain, port or scheme) unless that server allows it with headers such as `Access-Control-Allow-Origin`. It is enforced by the browser, not the server.

### Q [Medium] How do you store passwords?
Never in plain text. Store a **salted, slow hash** (bcrypt, scrypt or Argon2). Hashing is one-way; the salt makes identical passwords hash differently.

### Q [Medium] What is SQL injection and how do you prevent it?
An attacker puts SQL into an input that is concatenated into a query. Prevent with **parameterised queries** or an ORM, input validation and a least-privilege database user.

### Q [Medium] What is XSS and how do you prevent it?
Cross-site scripting: an attacker gets a script to run in other users' browsers (for example through an unescaped comment). Prevent by **escaping output**, using frameworks that escape by default, a Content Security Policy and avoiding `innerHTML` with untrusted data.

### Q [Medium] What is CSRF and how is it prevented?
Cross-site request forgery: a malicious site makes the user's browser send an authenticated request. Prevent with **CSRF tokens**, `SameSite` cookies and checking the origin.

### Q [Hard] How would you design pagination for an API?
Offset pagination (`?page=2&limit=20`) is simple but slows and shifts on large changing data. **Cursor-based** pagination (`?after=<id>`) is stable and faster for large datasets. Return total or next-page information.

### Q [Hard] How do you make an API secure and reliable?
HTTPS everywhere, authentication and authorisation checks, input validation, rate limiting, parameterised queries, proper error handling without leaking details, logging, versioning and tests.

### Q [Medium] What is rate limiting?
Restricting how many requests a client can make in a period, to prevent abuse and overload; it returns `429` when exceeded.
