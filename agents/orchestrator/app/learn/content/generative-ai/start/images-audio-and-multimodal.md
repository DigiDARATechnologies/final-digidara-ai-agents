---
title: Images, audio and multimodal AI
summary: Understand how image generators (diffusion) work, how to prompt them, and how multimodal and speech models extend generative AI beyond text.
takeaways:
- Diffusion models learn to remove noise step by step, and generate images by starting from pure noise
- Image prompts work best with subject, style, lighting and composition
- Multimodal models accept images, audio and text together
---
## Beyond text

| Kind | What it does | Examples |
| --- | --- | --- |
| **Text to image** | creates a picture from a description | Stable Diffusion, DALL-E, Midjourney |
| **Image understanding** | describes or answers questions about an image | multimodal LLMs |
| **Speech to text** | transcribes audio | Whisper |
| **Text to speech** | speaks text aloud | many voice models |
| **Text to video** | short clips from a prompt | video generation models |

## How image generation works: diffusion

A **diffusion model** is trained by taking real images and **adding a little noise, step by step, until only random static is left**. It then learns to **reverse** each step: to remove a little noise. To generate a picture, it starts from pure noise and **removes noise step by step**, guided by your text prompt, until an image appears.

The "add noise" half is simple to see with numbers. Start with a clean signal and mix in more noise at each step:

```python
import numpy as np

rng = np.random.default_rng(0)
clean = np.sin(np.linspace(0, 6.28, 200))                # a clean "image" (a wave)
noise = rng.normal(size=200)

print("step   signal kept   similarity to the clean image")
for step, signal_kept in enumerate([1.0, 0.8, 0.5, 0.2, 0.0]):
    noisy = np.sqrt(signal_kept) * clean + np.sqrt(1 - signal_kept) * noise
    similarity = np.corrcoef(clean, noisy)[0, 1] if signal_kept > 0 else float("nan")
    print(f"{step:>4}   {signal_kept:>11.1f}   {similarity:>8.2f}" if signal_kept > 0 else f"{step:>4}   {signal_kept:>11.1f}   pure noise")
```

```output
step   signal kept   similarity to the clean image
   0           1.0       1.00
   1           0.8       0.84
   2           0.5       0.64
   3           0.2       0.42
   4           0.0   pure noise
```

With each step the signal fades into noise. A diffusion model is a neural network trained to run this film **backwards**, predicting the noise to take out at each step. After many tiny, guided steps, noise becomes a picture.

## Prompting image models

Be specific about **what, how and where**:

| Part | Example |
| --- | --- |
| **subject** | "a young woman studying in a library" |
| **style** | "watercolour illustration", "photograph", "flat vector icon" |
| **lighting and mood** | "soft morning light, calm" |
| **composition** | "close-up", "wide shot", "centered, plain background" |
| **details to avoid** | many tools accept a "negative prompt" such as "no text, no extra fingers" |

Text inside generated images is often wrong, and hands and small details can look odd, so check and edit the result.

## Using models in code

```py
# Stable Diffusion with the diffusers library (needs a GPU for good speed)
import torch
from diffusers import StableDiffusionPipeline

pipe = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5", torch_dtype=torch.float16).to("cuda")
image = pipe("a calm watercolour illustration of a student studying, soft morning light").images[0]
image.save("student.png")
```

Hosted APIs (from the image-model providers) let you do the same without owning a GPU. Model names and rules change quickly, so check the current documentation.

## Multimodal models

A **multimodal** model understands more than one kind of input, for example an image **and** a question about it:

| Use | Example |
| --- | --- |
| read a chart or a table from a photo | "What was the highest month in this chart?" |
| explain a diagram or a screenshot | "Why is this error showing?" |
| describe a scene for accessibility | alt text for images |
| extract data from a form or an ID card | OCR plus understanding (handle personal data carefully) |
| listen and talk | voice assistants combining speech recognition, an LLM and speech output |

## Speech

```py
# Whisper turns speech into text (pip install openai-whisper)
import whisper

model = whisper.load_model("base")
result = model.transcribe("lecture.mp3")          # works for many languages, including Tamil
print(result["text"])
```

Accuracy is lower for noisy audio, strong accents and mixed-language speech, so test with the voices your users really have.

## Responsible use

| Issue | Practice |
| --- | --- |
| **deepfakes and impersonation** | never create a real person's face or voice without consent; label generated media |
| **copyright** | check the licence of models and outputs, especially for commercial use |
| **bias** | image models can show stereotypes; review outputs |
| **misinformation** | do not present generated images as real photos |
| **cost and energy** | image and video generation use a lot of computing |

:::interview
**Interviewers often ask:** "How does a diffusion model generate an image?" It is trained to predict and remove the noise that was gradually added to real images. To generate, it starts from random noise and repeatedly removes noise, guided by the text prompt, until an image emerges.
:::
