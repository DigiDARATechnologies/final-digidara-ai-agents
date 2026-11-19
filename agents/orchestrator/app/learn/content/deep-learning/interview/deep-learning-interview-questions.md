---
title: Deep learning interview questions
summary: Deep learning questions from basic to advanced, with clear answers you can say aloud, covering networks, training, CNNs, RNNs, transformers and deployment.
kind: qa
takeaways:
- Be able to explain the training loop, backpropagation and gradient descent in plain words
- Know the causes and cures of overfitting and vanishing gradients
- Understand CNNs, LSTMs, attention and transformers well enough to explain them with a small example
---
### Q [Easy] What is deep learning and how is it different from machine learning?
Deep learning is a subset of machine learning that uses neural networks with many layers to learn features directly from raw data such as images, text and audio. Traditional machine learning usually needs hand-made features and works best on tabular data; deep learning needs more data and compute but handles unstructured data very well.

### Q [Easy] What is a neuron, and what is a layer?
A neuron computes a weighted sum of its inputs plus a bias and passes it through an activation function. A layer is a group of neurons that process the same inputs in parallel, computed together as one matrix multiplication.

### Q [Easy] What is an activation function and why do we need non-linearity?
A function applied to a neuron's weighted sum, such as ReLU, sigmoid or tanh. Without a non-linear activation, a stack of linear layers collapses into a single linear transformation, so the network could only learn linear relationships. Non-linearity lets it learn complex patterns.

### Q [Easy] What is the difference between an epoch, a batch and an iteration?
An epoch is one full pass over the training data. A batch is the group of examples used for one weight update. An iteration is one update step, so the number of iterations per epoch is the dataset size divided by the batch size.

### Q [Medium] Explain gradient descent and the role of the learning rate.
Gradient descent repeatedly moves each weight a small step against the gradient of the loss, reducing the loss. The learning rate sets the step size: too small makes training slow, too large makes it overshoot, oscillate or diverge.

### Q [Medium] Explain backpropagation.
After a forward pass computes the loss, backpropagation applies the chain rule from the output backwards, multiplying local derivatives through the layers, to compute the gradient of the loss with respect to every weight efficiently in one backward pass. The optimiser then uses these gradients to update the weights.

### Q [Medium] What is the difference between SGD, mini-batch gradient descent and batch gradient descent?
Batch gradient descent uses the whole dataset for each update (exact but slow), stochastic gradient descent uses one example (fast but noisy), and mini-batch uses a small group (such as 32 or 256), which is the standard compromise between speed, stability and hardware efficiency.

### Q [Medium] How does Adam work and why is it popular?
Adam combines momentum (a running average of gradients) with adaptive per-parameter learning rates (a running average of squared gradients). It converges quickly with little tuning, which makes it a strong default; AdamW additionally applies weight decay correctly and is standard for transformers.

### Q [Medium] Which loss function would you use for regression, binary classification and multi-class classification?
Mean squared error (or MAE) for regression; binary cross-entropy for two classes (in PyTorch `BCEWithLogitsLoss` on logits); cross-entropy for multiple classes (`CrossEntropyLoss` on logits). Multi-label tasks use binary cross-entropy per label.

### Q [Medium] What is the vanishing gradient problem and how do you fix it?
In deep networks the gradient is a product of many per-layer factors; if they are less than 1, as with saturating sigmoid or tanh units, the gradient shrinks toward the early layers and they barely learn. Fixes include ReLU-type activations, Xavier or Kaiming initialisation, batch or layer normalisation, residual connections, and gated cells (LSTM or GRU) for recurrent networks. Exploding gradients are handled with gradient clipping.

### Q [Medium] What is overfitting and how do you prevent it in neural networks?
The model memorises training data and performs poorly on new data; training loss keeps falling while validation loss rises. Prevent it with more data and augmentation, dropout, weight decay, a smaller model, early stopping, batch normalisation and ensembling, and always evaluate on a separate validation set.

### Q [Medium] How does dropout work, and what happens at test time?
During training each neuron is zeroed with probability p, forcing the network not to depend on any single unit; remaining activations are scaled by 1/(1−p). At test time dropout is switched off (`model.eval()`), and all neurons are used.

### Q [Medium] What does batch normalisation do?
It normalises each layer's activations over the batch to zero mean and unit variance, then applies a learnable scale and shift. This stabilises and speeds up training, allows higher learning rates and acts as a mild regulariser. At inference it uses running statistics collected during training. Transformers use layer normalisation instead.

### Q [Medium] Why must we call `optimizer.zero_grad()` and `model.eval()`?
Gradients accumulate in PyTorch, so they must be cleared before each backward pass or old gradients contaminate the update. `model.eval()` switches layers such as dropout and batch normalisation to inference behaviour, otherwise test results are noisy and wrong; combine it with `torch.no_grad()` to save memory.

### Q [Medium] Why initialise weights carefully?
Poor initial scales make activations and gradients shrink or blow up through the layers. Xavier initialisation suits tanh and sigmoid, Kaiming (He) suits ReLU, keeping the variance of signals roughly constant across layers so training starts well.

### Q [Medium] How do convolutional neural networks work and why are they good for images?
Small learnable filters slide across the image computing local patterns, with the same weights used at every position (weight sharing). This needs far fewer parameters than dense layers, detects patterns wherever they appear, and stacked layers build a hierarchy from edges to textures to objects. Pooling reduces size and adds tolerance to small shifts.

### Q [Medium] What is the output size of a convolution layer?
`(n + 2p − k) / s + 1`, rounded down, where n is the input size, p the padding, k the kernel size and s the stride. For example an 8 by 8 input with a 3 by 3 kernel, no padding and stride 1 gives 6 by 6.

### Q [Medium] What is transfer learning and when would you use it?
Reusing a model pretrained on a large dataset as the starting point for a new task, by freezing the early layers and training a new final layer (feature extraction) or by fine-tuning all layers at a small learning rate. Use it when you have limited data or compute, which is the usual case.

### Q [Hard] Why do LSTMs work better than simple RNNs?
Simple RNNs suffer from vanishing gradients through time and forget long-range information. An LSTM has a cell state and forget, input and output gates that let information and gradients flow across many time steps with little change, so it can learn long-term dependencies. GRUs are a lighter variant.

### Q [Hard] Explain self-attention and the transformer.
Each token is projected into a query, key and value. Attention weights are softmax(QKᵀ/√d), and each token's output is the weighted sum of the values, letting every token gather information from all others in one step. A transformer stacks blocks of multi-head self-attention and feed-forward layers with residual connections and layer normalisation, plus positional information, and it trains in parallel, which lets it scale far better than RNNs.

### Q [Hard] Why divide by √d in scaled dot-product attention?
Dot products of high-dimensional vectors have a large variance that grows with d, which pushes the softmax into regions where one weight is nearly 1 and gradients almost vanish. Dividing by √d keeps the scores in a range where the softmax stays well behaved.

### Q [Hard] What is the complexity of self-attention, and how is it reduced?
Time and memory grow quadratically with the sequence length (n²) because every token is compared with every other. Techniques such as FlashAttention (memory-efficient exact attention), sparse or sliding-window attention, linear attention and key-value caching make long sequences practical.

### Q [Hard] What is the difference between encoder-only, decoder-only and encoder-decoder transformers?
Encoder-only models (BERT) read the whole input in both directions and suit understanding tasks such as classification. Decoder-only models (GPT, Llama) use a causal mask and generate text left to right. Encoder-decoder models (T5) encode an input and decode an output, suiting translation and summarisation.

### Q [Hard] How does an LLM generate text, and what does temperature do?
It predicts a probability distribution over the next token, selects one (greedily or by sampling with top-k or top-p), appends it and repeats. Temperature divides the logits before the softmax: low values make the output more deterministic, high values make it more diverse and more error-prone.

### Q [Hard] What is LoRA and why is it used?
Low-Rank Adaptation freezes the pretrained weights and trains small low-rank matrices whose product is added to selected weight matrices. It trains well under 1 to 2% of the parameters, drastically reducing memory and storage while giving results close to full fine-tuning, and one base model can serve many small adapters.

### Q [Hard] How do you reduce hallucinations in an LLM application?
Use retrieval-augmented generation to ground answers in trusted documents, give clear instructions and examples, lower the temperature, ask for citations and verify them, add validation and human review for important outputs, and fine-tune on domain data where necessary.

### Q [Medium] How would you debug a network that is not learning?
Check the data and labels, shapes and scaling; verify the first loss is near ln(classes); overfit a single small batch (if it cannot, there is a bug); try a learning rate ten times larger and smaller; check for silent bugs such as softmax before `CrossEntropyLoss`, a missing `zero_grad` or mismatched target shapes; then simplify the model and add complexity one step at a time.

### Q [Hard] How do you put a deep learning model into production?
Save the weights and preprocessing together, validate inputs, serve the model behind an API after loading it once, and reduce latency with batching, quantisation or export formats such as ONNX. Monitor inputs, predictions and accuracy for drift, version models with a rollback plan, test pipelines, and assess fairness, privacy and safety before and after launch.

:::practice mock-interview
Practise explaining backpropagation, overfitting, attention and how you would debug a network that will not learn aloud in a Mock Interview.
:::
