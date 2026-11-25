---
title: Operating system questions
summary: Processes, threads, scheduling, deadlock, memory management and synchronization.
kind: qa
takeaways:
- Separate process from thread and know the process states
- Know the four deadlock conditions
- Explain paging, virtual memory and common scheduling algorithms
---
### Q [Easy] What is an operating system?
Software that manages hardware and provides services to programs: process management, memory management, file systems, device control and security.

### Q [Easy] Process vs thread?
A **process** is a running program with its own memory space. A **thread** is a unit of execution inside a process; threads of one process **share** memory, so they are lighter and communication is faster, but they need synchronization.

### Q [Easy] What are the states of a process?
New, Ready, Running, Waiting (blocked) and Terminated.

### Q [Medium] What is context switching?
Saving the state of the running process and loading the state of another so the CPU can switch between them. It is overhead: no useful work is done during the switch.

### Q [Medium] Name some CPU scheduling algorithms.
**FCFS** (first come first served), **SJF** (shortest job first, minimises average waiting time), **Round Robin** (each process gets a time slice), **Priority scheduling**, and **multilevel queue**.

### Q [Medium] What is starvation and how is it solved?
A process waits indefinitely because others always get priority. **Aging** (gradually raising the priority of waiting processes) solves it.

### Q [Medium] What is a deadlock? What are the necessary conditions?
Processes wait forever for resources held by each other. The four conditions (all must hold): **mutual exclusion**, **hold and wait**, **no preemption** and **circular wait**. Break any one to prevent deadlock.

### Q [Medium] How can deadlocks be handled?
Prevention (break a condition), avoidance (Banker's algorithm), detection and recovery, or ignoring it (the ostrich approach used by many general-purpose systems).

### Q [Medium] What is a semaphore and a mutex?
A **mutex** is a lock owned by one thread that allows exclusive access to a resource. A **semaphore** is a counter that allows up to N threads (a binary semaphore acts like a lock) and is used for signalling between threads.

### Q [Medium] What is the critical section problem?
Making sure only one process at a time executes the code that accesses a shared resource, giving **mutual exclusion**, **progress** and **bounded waiting**.

### Q [Medium] What is paging?
Memory is divided into fixed-size **frames** (physical) and **pages** (logical). A page table maps pages to frames, so a process need not be contiguous in memory and **external fragmentation** is avoided.

### Q [Medium] What is virtual memory?
A technique that lets programs use more memory than physically installed by keeping some pages on disk and loading them on demand.

### Q [Hard] What is thrashing?
The system spends more time swapping pages between memory and disk than running processes, because too many processes compete for too little memory. Reduce multiprogramming or add memory.

### Q [Hard] Name page replacement algorithms.
**FIFO** (replace the oldest), **LRU** (replace the least recently used), **Optimal** (replace the page not needed for the longest time; theoretical). FIFO can show **Belady's anomaly** (more frames can cause more faults).

### Q [Medium] Internal vs external fragmentation?
**Internal**: wasted space inside an allocated block. **External**: free memory split into small pieces that are not contiguous. Paging removes external fragmentation.
