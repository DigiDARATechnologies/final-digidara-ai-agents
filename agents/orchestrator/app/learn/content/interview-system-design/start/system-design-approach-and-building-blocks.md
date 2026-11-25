---
title: System design: approach and building blocks
summary: A step-by-step way to answer a design question, and the building blocks you combine: load balancer, cache, database, queue, CDN.
takeaways:
- Clarify requirements and estimate scale before drawing boxes
- Know the standard building blocks and what each solves
- Explain trade-offs, not only the final picture
---
## What the interviewer wants

A system design round has no single right answer. They want to see how you **think**: ask questions, estimate scale, choose components, and explain **trade-offs**. Freshers are usually asked for simple designs (a URL shortener, a chat app), so focus on the basics.

## A five-step approach

1. **Clarify requirements.** Who uses it? What are the main features (functional)? How fast, how available, how consistent (non-functional)?
2. **Estimate scale.** Users, requests per second, data size. "10 million users, each makes 10 requests a day" is about 1,000 requests per second.
3. **Design the API and data model.** The main endpoints and the key tables.
4. **Draw the high-level design.** Clients, servers, database, cache, queue.
5. **Deep dive and trade-offs.** Scale the bottleneck, discuss failure, and consistency.

## Back-of-the-envelope numbers

- Seconds in a day: about **86,400** (round to 100,000).
- 1 million requests per day is about **12 per second**.
- Reading from memory is about 100 times faster than from an SSD, and an SSD is much faster than a network call to another region.

## The building blocks

| Block | What it does | Use it when |
| --- | --- | --- |
| **Load balancer** | spreads requests over many servers | one server is not enough, or you need availability |
| **Cache (Redis)** | keeps hot data in memory | the same data is read again and again |
| **CDN** | serves static files from servers near the user | images, videos, JavaScript |
| **Database (SQL)** | structured data with transactions | money, orders, relations |
| **Database (NoSQL)** | flexible or huge scale data | feeds, logs, sessions |
| **Message queue** | passes work between services asynchronously | slow or spiky work (emails, video processing) |
| **Object storage** | stores files cheaply (S3 style) | photos, documents, backups |
| **API gateway** | one entry point with auth and rate limits | many services behind one API |
| **Search index** | fast text search | search boxes |

## Scaling ideas

- **Vertical scaling**: a bigger machine (simple, but limited).
- **Horizontal scaling**: more machines behind a load balancer (needs stateless servers).
- **Database replication**: copies for reads (read replicas) and failover.
- **Sharding**: split the data across databases by a key (such as user id).
- **Caching** and **CDNs**: reduce load and delay.
- **Async processing**: move slow tasks to queues.

## Trade-offs you should mention

| Choice | Trade-off |
| --- | --- |
| SQL vs NoSQL | consistency and joins versus flexibility and scale |
| Cache | speed versus stale data |
| Replication | availability and read speed versus delay in copies |
| Strong vs eventual consistency | correctness now versus availability and speed |
| Sync vs async | simple and immediate versus resilient and scalable |

## CAP in one line

In a distributed system during a network partition you must choose between **consistency** and **availability**. A bank leans to consistency; a social feed leans to availability.

:::tip
Think aloud. Say "I will assume 10 million users, is that fine?" Interviewers love candidates who state assumptions and then check them.
:::
