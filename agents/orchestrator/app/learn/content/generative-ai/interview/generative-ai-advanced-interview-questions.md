---
title: Advanced generative AI interview questions
summary: Deeper questions on transformers, decoding, RAG quality, fine-tuning, evaluation and security.
takeaways:
- Explain the why, not only the what
- Mention trade-offs and how you would measure
- Use a concrete example from a project
kind: qa
---
### Q [Medium] Explain self-attention in simple terms.
Each token creates a query, key and value. Its query is compared with every token's key to get weights, and the output is a weighted mix of the values. This lets every word use context from all other words.

### Q [Medium] What does temperature do?
It scales the logits before softmax. Low temperature makes the top token dominate (repeatable, factual); high temperature flattens the distribution (varied, riskier).

### Q [Medium] What is top-p sampling?
Choose from the smallest set of tokens whose probabilities sum to p, ignoring the unlikely tail. The set size adapts to how confident the model is.

### Q [Medium] How do you get reliable JSON from an LLM?
Use the provider's structured output or schema mode, keep the schema small with field descriptions, set low temperature, validate with Pydantic or JSON schema, and retry with the error on failure.

### Q [Medium] What is a context window and what happens when it is exceeded?
The maximum tokens (prompt plus output) the model can handle. If exceeded the call fails or old text is dropped, so you must trim, summarise or retrieve only the relevant parts.

### Q [Medium] Why use a vector database instead of comparing with every embedding?
Brute force does not scale. Approximate indexes such as HNSW find near neighbours quickly with very high recall, and the database also stores metadata for filtering.

### Q [Hard] RAG gives wrong answers. How do you debug it?
Check retrieval first: print the retrieved chunks. If the right chunk is missing, improve chunking, use hybrid search, rerank, rewrite the query. If it is present but ignored, fix the prompt or reduce noise. Measure hit rate and faithfulness on a test set.

### Q [Hard] RAG, fine-tuning or prompting?
Prompting first (cheapest). RAG when the model needs your changing or private facts with citations. Fine-tuning for consistent style, format or a narrow task, or to make a smaller model sufficient. They are often combined.

### Q [Hard] What is LoRA and why is it useful?
Low-rank adaptation freezes the base model and trains small matrices added to the weights. It needs far less memory and storage, and adapters can be swapped per task.

### Q [Hard] What is quantization and its trade-off?
Storing weights in fewer bits (8 or 4) to cut memory and speed up inference. It slightly reduces quality, so test your task afterwards.

### Q [Hard] How do you evaluate an LLM application?
Build a test set of real cases, score with rules and exact checks where possible and an LLM judge for open-ended answers, measure retrieval and faithfulness separately for RAG, review samples by hand, and rerun on every change.

### Q [Hard] What is prompt injection and how do you defend against it?
Hidden instructions in user input or retrieved content that hijack the model. Defend in layers: least-privilege tools, treating content as untrusted data, output validation, human approval for risky actions, per-user data permissions, rate limits and red-team testing.

### Q [Hard] How would you reduce LLM cost in production?
Use a smaller model where it passes tests, shorter prompts and fewer retrieved chunks, prompt and response caching, output limits, batching for non-urgent work, and routing easy requests to cheap models.

### Q [Hard] What causes hallucinations and how can you reduce them?
The model predicts likely text, not verified facts. Reduce with grounding (RAG with citations), asking it to say "I do not know", lower temperature, verification steps, and tool use for exact facts such as calculations and lookups.
