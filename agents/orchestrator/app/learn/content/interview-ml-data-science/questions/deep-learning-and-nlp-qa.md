---
title: Deep learning and NLP questions
summary: Neural networks, activation functions, backpropagation, CNNs, RNNs, transformers, embeddings and LLM basics.
kind: qa
takeaways:
- Explain a neural network, backpropagation and gradient descent simply
- Know when to use a CNN, RNN or transformer
- Describe embeddings, attention and fine-tuning
---
### Q [Easy] What is a neural network?
Layers of connected units (neurons). Each computes a weighted sum of its inputs plus a bias, applies an **activation function**, and passes the result on. Training adjusts the weights to reduce the error.

### Q [Medium] Why do we need activation functions?
Without non-linear activations, stacked layers collapse into a single linear function. Activations such as **ReLU**, **sigmoid** and **tanh** let the network learn complex patterns.

### Q [Medium] What is backpropagation?
An algorithm that computes how much each weight contributed to the error by applying the chain rule backwards from the output to the input, giving the gradients used to update the weights.

### Q [Medium] Explain gradient descent and the learning rate.
It repeatedly moves the weights a small step in the direction that reduces the loss. The **learning rate** is the step size: too large and training diverges; too small and it is very slow. **Adam** is a popular optimiser that adapts the step.

### Q [Medium] Batch, mini-batch and stochastic gradient descent?
**Batch** uses all data per update, **stochastic** uses one example, **mini-batch** uses a small group (the common choice, balancing speed and stability).

### Q [Medium] What is an epoch, batch size and iteration?
An **epoch** is one pass through the whole training set. **Batch size** is the number of examples per update. An **iteration** is one update (so iterations per epoch = data size / batch size).

### Q [Medium] What is the vanishing gradient problem?
In deep or recurrent networks, gradients become tiny as they move backwards, so early layers barely learn. ReLU, residual connections, good initialisation, LSTM/GRU and normalisation help.

### Q [Medium] What are dropout and batch normalisation?
**Dropout** randomly switches off neurons during training to reduce overfitting. **Batch normalisation** normalises layer inputs, which stabilises and speeds up training.

### Q [Medium] What is a CNN and what is it used for?
A convolutional neural network applies small learnable filters across an image to detect edges, then shapes, then objects, sharing weights and keeping spatial structure. Used for image classification, detection and more.

### Q [Medium] Why did transformers replace RNNs for language?
Attention lets every token look at all others directly, which captures long-range context and allows training in parallel on GPUs. RNNs process tokens one by one, are slow and forget long context.

### Q [Medium] What are word embeddings?
Dense vectors where words with similar meaning are close together (Word2Vec, GloVe). Modern models learn contextual embeddings, so the same word gets different vectors in different sentences.

### Q [Medium] What is transfer learning?
Reusing a model pre-trained on a large dataset and fine-tuning it on your smaller dataset. It needs far less data and compute than training from scratch.

### Q [Hard] What is attention?
A mechanism that gives each token a weighted mix of all tokens' information, with weights computed from query-key similarity. It lets the model focus on the relevant parts of the input.

### Q [Hard] BERT vs GPT?
**BERT** is an encoder reading text in both directions, suited to understanding tasks (classification, NER, search). **GPT** is a decoder predicting the next token left to right, suited to generating text.

### Q [Hard] What is RAG and why is it used?
Retrieval-augmented generation retrieves relevant documents and gives them to an LLM so answers are grounded in your data, reducing hallucination and avoiding retraining when information changes.

### Q [Hard] What is hallucination in an LLM and how do you reduce it?
The model produces fluent but false content. Reduce with retrieval and citations, low temperature, clear instructions to say "I do not know", verification steps and tool use for exact facts.
