---
title: Generative AI interview questions
summary: Common generative AI questions with short answers you can say aloud, from what an LLM is to RAG, prompting, safety and evaluation.
kind: qa
takeaways:
- Be able to explain tokens, context, temperature and hallucination simply
- Know RAG end to end, and when to use prompting, RAG or fine-tuning
- Have an answer ready for safety, prompt injection and evaluation
---
### Q [Easy] What is generative AI?
AI that creates new content, such as text, images, code, audio or video, by learning the patterns of its training data. Unlike a classifier that labels data, it generates new examples that resemble what it learned.

### Q [Easy] What is a large language model?
A very large neural network (a transformer) trained on huge amounts of text to predict the next token. By repeating that prediction it can write, summarise, translate and answer questions.

### Q [Easy] What is a token?
The unit of text a model reads and writes: a whole common word, part of a rarer word, or punctuation. Usage, limits and prices are counted in tokens. For English, roughly 4 characters or three-quarters of a word make one token.

### Q [Medium] What is a context window?
The maximum number of tokens the model can handle in a single request, covering the instructions, the history, any documents and its own answer. Content beyond it is not seen.

### Q [Medium] What do temperature and top-p do?
They control randomness when picking the next token. Low temperature makes the output more deterministic, which suits facts and code; higher temperature gives more varied, creative output. Top-p samples only from the most likely tokens whose probabilities add up to p.

### Q [Easy] What is hallucination, and how do you reduce it?
When a model states false things confidently, because it generates likely text rather than verified facts. Reduce it with retrieval (RAG) and citations, instructions to say "I do not know", lower temperature, tools for facts and calculations, and human review.

### Q [Medium] What is prompt engineering?
Designing the instructions you give a model so it produces reliable output: a clear role, task, context, format and limits, plus examples (few-shot), structured output, and testing the prompt on varied inputs.

### Q [Medium] What is few-shot prompting?
Including a few examples of input and desired output in the prompt so the model copies the pattern, without any training. Zero-shot means giving only the instruction.

### Q [Medium] What are embeddings and what are they used for?
Vectors that represent the meaning of text so similar meanings are close together. They power semantic search, recommendations, duplicate detection, clustering and the retrieval step in RAG.

### Q [Medium] Explain RAG.
Retrieval-augmented generation: split documents into chunks, embed and store them, retrieve the chunks most relevant to the question, put them in the prompt, and ask the model to answer only from them and cite the sources. It gives answers based on your current data without retraining.

### Q [Hard] How do you improve a RAG system that gives poor answers?
First check retrieval: clean documents, tune chunk size and overlap, use a better embedding model, hybrid keyword and vector search, a reranker and metadata filters. Then check generation: a stricter grounded prompt, citations and an "I do not know" rule. Measure everything on a test set of real questions with expected sources.

### Q [Medium] Prompting, RAG or fine-tuning: how do you choose?
Prompting first for tone, format and behaviour. RAG when the model needs your or current knowledge, or must cite sources. Fine-tuning when you need a consistent style or narrow task behaviour that prompts cannot achieve and you have good examples. Fine-tuning is not a reliable way to add facts.

### Q [Medium] What is LoRA?
A parameter-efficient fine-tuning method that freezes the base model and trains small low-rank matrices added to its weights, so only a tiny fraction of parameters is trained, which saves memory and cost.

### Q [Hard] What is prompt injection and how do you defend against it?
An attack where text from an untrusted source (a web page, email or document) contains instructions that the model follows. Defend with least-privilege tools, no secrets in prompts, delimiting and labelling untrusted data, output validation, human approval for risky actions and monitoring. No prompt wording alone is a full defence.

### Q [Medium] How do you evaluate an LLM application?
Build a test set of real questions with expected facts, sources or refusals, run the app on it after every change, and score with automatic checks, source checks, LLM-as-judge (spot-checked by hand) and human review. Track accuracy, groundedness, refusal quality, latency, cost and safety.

### Q [Medium] How would you control the cost of an LLM app?
Shorten prompts, retrieve only relevant chunks, set max tokens, use smaller models for easy tasks, cache repeated prompt parts, and track tokens per user with budgets and alerts.

### Q [Hard] How does a diffusion model generate images?
It learns to remove noise that was gradually added to training images. To generate, it starts from random noise and removes it step by step, guided by the text prompt, until an image forms.

### Q [Medium] What privacy rules apply when using LLM APIs?
Do not send secrets or personal data unless allowed; redact what is not needed; use approved providers and settings, understand how the provider stores and uses data, comply with laws such as India's DPDP Act and GDPR, and log carefully.

:::practice mock-interview
Explain RAG and prompt injection aloud in a Mock Interview, using one example from a project you could build.
:::
