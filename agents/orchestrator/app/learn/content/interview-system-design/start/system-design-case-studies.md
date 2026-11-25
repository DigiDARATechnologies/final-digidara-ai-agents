---
title: System design case studies
summary: Four common designs explained step by step: URL shortener, rate limiter, chat application and news feed.
takeaways:
- Follow the same five steps for every design
- A URL shortener is mostly a key-value lookup with caching
- A rate limiter needs a fast shared counter, such as Redis
---
## 1. URL shortener

**Requirements.** Create a short link for a long URL; redirect quickly; links may expire. Assume 100 million new links a month and a read-heavy workload (100 reads per write).

**API.**
- `POST /links` with the long URL returns a short code.
- `GET /<code>` redirects (HTTP 301 or 302).

**Data model.** `links(code PRIMARY KEY, long_url, created_at, expires_at, user_id)`.

**Generating the code.** Take an auto-increment id and convert it to **base62** (letters and digits). Seven characters give 62 to the power 7, which is about 3.5 trillion codes. Alternatively use random codes and check for collisions.

**Design.** Load balancer, stateless app servers, a database (key-value access by code), and a **Redis cache** in front for hot links. Reads are served from the cache most of the time.

**Trade-offs.** 301 (cached by browsers, less load, no click counts) versus 302 (every click reaches you, so you can count clicks). Shard by code when the table is huge.

## 2. Rate limiter

**Requirement.** Allow each user at most N requests per time window and reply `429 Too Many Requests` beyond that.

**Algorithms.**

| Algorithm | Idea |
| --- | --- |
| Fixed window | count requests in each minute; simple, but allows bursts at window edges |
| Sliding window | count requests in the last 60 seconds; smoother |
| **Token bucket** | a bucket refills with tokens at a steady rate; each request uses one; allows short bursts |

```python
import time

class TokenBucket:
    def __init__(self, capacity, refill_per_second):
        self.capacity = capacity
        self.tokens = capacity
        self.refill = refill_per_second
        self.updated = time.monotonic()

    def allow(self):
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.refill)
        self.updated = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

bucket = TokenBucket(capacity=3, refill_per_second=1)
print([bucket.allow() for _ in range(5)])
```

```output
[True, True, True, False, False]
```

The first 3 requests use the stored tokens; the next 2 are refused until tokens refill. With many servers, keep the counters in **Redis** (atomic increments) so all servers share one count.

## 3. Chat application (WhatsApp style)

**Requirements.** One-to-one and group messages, delivery in order, online status, message history.

**Design.**
- Clients keep a **WebSocket** connection to a chat server for real-time push.
- A **connection service** knows which server holds each user's connection.
- Sender to server, server **stores the message** (a wide-column or key-value store partitioned by chat id), then forwards to the recipient's connection; if the recipient is offline, queue it and send a **push notification**.
- Use per-chat **sequence numbers** to order messages and acknowledge delivery.
- Media goes to **object storage** with a CDN; the message holds only the link.

**Trade-offs.** Delivery guarantees (at-least-once with de-duplication), group size (fan-out cost), and end-to-end encryption.

## 4. News feed

**Requirement.** Show a user the latest posts from the people they follow.

**Two approaches.**
- **Fan-out on read (pull):** when you open the feed, fetch recent posts of everyone you follow and merge them. Cheap to write, slow to read.
- **Fan-out on write (push):** when someone posts, copy the post id into each follower's feed list (in a cache). Fast to read, expensive for users with millions of followers.

A real system uses a **hybrid**: push for normal users, pull for celebrities. Store feeds in Redis lists, posts in a database and media on a CDN; rank posts with a score and paginate with cursors.

## How to practise

Pick one design a week, draw it on paper in 20 minutes, and explain it aloud. Always finish with: bottlenecks, failures and what you would improve.

:::practice mock-interview
Practise explaining a design out loud with the Mock Interview agent.
:::
