---
title: Computer network questions
summary: OSI and TCP/IP models, TCP vs UDP, HTTP and HTTPS, DNS, IP addressing and what happens when you type a URL.
kind: qa
takeaways:
- Know the OSI layers and what each does
- Explain TCP versus UDP and the TCP handshake
- Be able to describe what happens when you open a website
---
### Q [Easy] What is the OSI model? Name the layers.
A 7-layer reference model for network communication, from top to bottom: **Application, Presentation, Session, Transport, Network, Data Link, Physical**. (Mnemonic: "All People Seem To Need Data Processing".)

### Q [Medium] What is the TCP/IP model?
The practical 4-layer model: **Application** (HTTP, DNS), **Transport** (TCP, UDP), **Internet** (IP) and **Network access** (Ethernet, Wi-Fi).

### Q [Easy] TCP vs UDP?
**TCP**: connection oriented, reliable, ordered, with error recovery and flow control (web, email, file transfer). **UDP**: connectionless, no guarantee, faster and lighter (video calls, gaming, DNS).

### Q [Medium] Explain the TCP three-way handshake.
**SYN** (client asks to connect), **SYN-ACK** (server agrees), **ACK** (client confirms). Then data flows.

### Q [Easy] What is an IP address? IPv4 vs IPv6?
A unique address of a device on a network. IPv4 is 32 bits (about 4.3 billion addresses, such as 192.168.1.1). IPv6 is 128 bits, giving a vastly larger space.

### Q [Medium] What is DNS?
The Domain Name System translates names (`example.com`) into IP addresses, like a phone book of the internet.

### Q [Medium] HTTP vs HTTPS?
HTTP sends data in plain text. HTTPS is HTTP over **TLS**, which encrypts data, verifies the server with a certificate and prevents tampering.

### Q [Medium] Common HTTP methods and status codes?
GET (read), POST (create), PUT (replace), PATCH (partial update), DELETE (remove). Codes: **200** OK, **201** Created, **301** moved, **400** bad request, **401** unauthorised, **403** forbidden, **404** not found, **500** server error.

### Q [Medium] Router vs switch vs hub?
A **hub** repeats data to all ports. A **switch** sends data only to the right device in a local network. A **router** connects different networks and forwards packets between them.

### Q [Medium] What is a subnet mask?
It tells which part of an IP address is the network and which is the host. For example `255.255.255.0` (/24) means the first 24 bits are the network.

### Q [Medium] What are ports? Name common ones.
A port number identifies a service on a machine. HTTP 80, HTTPS 443, SSH 22, FTP 21, SMTP 25, DNS 53.

### Q [Hard] What happens when you type a URL in the browser and press Enter?
1. The browser checks its cache and **DNS** resolves the domain to an IP address.
2. A **TCP** connection is made (handshake), then **TLS** if HTTPS.
3. The browser sends an **HTTP request**.
4. The server processes it and returns an HTTP **response** (HTML).
5. The browser parses the HTML, fetches CSS, JavaScript and images, and **renders** the page.

### Q [Medium] What is a firewall?
A security system that allows or blocks network traffic based on rules, protecting a network from unauthorised access.

### Q [Hard] What is NAT?
Network Address Translation lets many devices on a private network share one public IP address by mapping private addresses and ports to the public one.
