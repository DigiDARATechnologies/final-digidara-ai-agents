---
title: Saving, deploying and responsible AI
summary: Save and load models safely, shrink them with quantisation, serve them in production, and build AI that is fair, safe and honest.
takeaways:
- Save the state_dict (the weights), not the whole pickled model, and keep the preprocessing with it
- Quantisation, batching and export formats make models smaller and faster in production
- Responsible AI means checking data, bias, privacy and failure modes before and after launch
---
## Saving and loading

Training is wasted unless you can reuse the result. In PyTorch, save the **state dictionary**: a dictionary of all the weights.

```python
import io
import torch
from torch import nn

torch.manual_seed(0)

def build():
    return nn.Sequential(nn.Linear(30, 64), nn.ReLU(), nn.Linear(64, 1))

model = build()
x = torch.randn(5, 30)
model.eval()
with torch.no_grad():
    before = model(x)

buffer = io.BytesIO()                                    # an in-memory file for this demo; use "model.pt" on disk
torch.save(model.state_dict(), buffer)
print("saved size:", round(buffer.tell() / 1024, 1), "KB")

buffer.seek(0)
restored = build()                                       # build the SAME architecture first...
restored.load_state_dict(torch.load(buffer))             # ...then load the weights into it
restored.eval()
with torch.no_grad():
    after = restored(x)

print("restored model gives identical predictions:", torch.equal(before, after))
```

```output
saved size: 10.2 KB
restored model gives identical predictions: True
```

On disk this is `torch.save(model.state_dict(), "model.pt")` and `model.load_state_dict(torch.load("model.pt"))`. Remember to call `model.eval()` after loading.

| Practice | Why |
| --- | --- |
| save `state_dict`, not the whole model object | works when your code changes; whole-object pickles break easily |
| keep the **model code** under version control | to rebuild the architecture |
| save the **preprocessing** too (scaler, tokenizer, label names) | predictions need the same transformations as training |
| record the version, data and metrics | so you can reproduce and compare |
| only load files you trust | loading a pickle can run arbitrary code; prefer `weights_only=True` or the **safetensors** format |

## Making a model smaller and faster

**Quantisation** stores weights as 8-bit integers instead of 32-bit decimals. The weights take up to four times less space, and the model is often faster on a CPU, usually with a tiny accuracy loss.

```python
quantised = torch.ao.quantization.quantize_dynamic(model, {nn.Linear}, dtype=torch.qint8)

def size_kb(m):
    buf = io.BytesIO()
    torch.save(m.state_dict(), buf)
    return buf.tell() / 1024

print(f"original  : {size_kb(model):.1f} KB")
print(f"quantised : {size_kb(quantised):.1f} KB")
with torch.no_grad():
    difference = (quantised(x) - model(x)).abs().max().item()
print("largest change in the outputs:", round(difference, 4))
```

```output
original  : 10.2 KB
quantised : 5.7 KB
largest change in the outputs: 0.0046
```

The quantised file is about 44% smaller, and its outputs differ from the original's by under 0.005. The saving is less than 4x here because this tiny model also stores biases and a little bookkeeping at full size; for big models the weights dominate and the saving approaches 4x. Always measure accuracy on your own test set after quantising.

| Technique | Effect |
| --- | --- |
| **quantisation** (8-bit, 4-bit) | smaller and faster, small accuracy cost |
| **pruning** | remove unimportant weights |
| **distillation** | train a small "student" model to imitate a big "teacher" |
| **batching requests** | handle many inputs at once for GPU efficiency |
| **mixed precision** | 16-bit numbers on GPUs |
| **compiling** (`torch.compile`) | faster execution of the same model |

## Exporting for other systems

| Format | Use |
| --- | --- |
| **TorchScript** (`torch.jit.script`) | run without Python (C++ or mobile) |
| **ONNX** (`torch.onnx.export`) | a standard format for many runtimes and hardware (ONNX Runtime, TensorRT) |
| **safetensors** | safe, fast weight files (standard for large models) |
| **TFLite / Core ML** | phones and edge devices |

```py
torch.onnx.export(model, torch.randn(1, 30), "model.onnx", input_names=["features"], output_names=["score"],
                  dynamic_axes={"features": {0: "batch"}})
```

## Serving predictions

A common pattern: load the model once when the server starts, and expose a small web API.

```py
from fastapi import FastAPI
from pydantic import BaseModel
import torch

app = FastAPI()
model = build(); model.load_state_dict(torch.load("model.pt")); model.eval()      # loaded once, at start-up

class Features(BaseModel):
    values: list[float]

@app.post("/predict")
def predict(features: Features):
    with torch.inference_mode():
        score = torch.sigmoid(model(torch.tensor([features.values]))).item()
    return {"probability": score}
```

| Production concern | What to do |
| --- | --- |
| **validate inputs** | wrong length, NaN, out-of-range values must not reach the model |
| **latency and throughput** | measure; use batching, quantisation, a GPU if needed |
| **monitoring** | log inputs and predictions; watch for drift and falling accuracy |
| **versioning and rollback** | keep the old model ready |
| **testing** | unit tests for preprocessing; a fixed set of examples that must keep working |
| **security** | rate limits, authentication, protect against prompt injection for LLMs |

## Responsible AI

A model that scores 95% in a notebook can still cause harm. Building well means asking harder questions.

| Risk | Example | What to do |
| --- | --- | --- |
| **Bias in the data** | a hiring model trained on past decisions copies past discrimination | audit data sources; check results **per group** (gender, region, age); fix or document gaps |
| **Unfair outcomes** | higher error rates for some skin tones or accents | measure accuracy for each group and fix before launch |
| **Privacy** | models can memorise personal data | collect only what you need, anonymise, follow the law (GDPR, India's DPDP Act) |
| **Lack of explanation** | a loan is refused and nobody can say why | use interpretable methods where decisions affect people (permutation importance, SHAP) |
| **Safety and misuse** | deepfakes, harmful instructions | content filters, usage policies, human review |
| **Hallucination** | confident but false answers | retrieval, verification, clear warnings, human in the loop for important decisions |
| **Overconfidence** | treating predictions as certainties | show uncertainty, allow appeals, never fully automate high-stakes calls |
| **Environmental cost** | large models use a lot of energy | choose smaller models, reuse pretrained ones, avoid wasteful retraining |

A habit worth building: write a short **model card** for every model: what it is for, what data trained it, how it performs overall **and for different groups**, its known limits, and what it must **not** be used for.

:::warning
If your model helps decide about people (jobs, loans, health, education, policing), you are responsible for testing it for fairness and for giving people a way to question the outcome. "The algorithm decided" is not an acceptable answer.
:::

## A final checklist for a project

1. Define the **problem and the metric** clearly, with the business or user need.
2. Collect and check the **data** (quality, balance, privacy, bias).
3. Build a **simple baseline** first (a linear model or small network) to beat.
4. Train, **validate**, and debug using the methods in this course.
5. Test on a **held-out test set** once, and per group.
6. **Explain** and review the results with the people affected.
7. **Deploy** carefully, with monitoring, validation and a rollback plan.
8. **Monitor** for drift and retrain when needed.

You now know how deep learning works from a single neuron up to transformers. The best next step is to **build something**: pick a dataset you care about, and take it through the checklist above.
