---
title: Diffusion models and image generation
summary: Learn how text-to-image models like Stable Diffusion create pictures from noise, and how to prompt and control them.
takeaways:
- Diffusion models learn to remove noise step by step
- Text guides the denoising through a text encoder
- Prompts, guidance scale, steps and seeds control the result
---
## The idea in plain words

Take a clear photo and add a little random noise, again and again, until only static remains. A **diffusion model** is trained to do the **reverse**: given a noisy image, predict the noise and remove a bit of it. Run that many times starting from pure noise, and a brand new image appears.

```text
training:   photo -> a bit noisy -> noisier -> ... -> pure noise
generating: pure noise -> less noisy -> ... -> new image
```

## Adding the text prompt

A **text encoder** (like CLIP) turns "a red bicycle in the rain, watercolour" into numbers that **guide** each denoising step, so the image drifts toward that description. The strength of this pull is the **guidance scale**.

## Latent diffusion (Stable Diffusion)

Working on full-size pixels is slow, so Stable Diffusion works in a small compressed space called the **latent space** and uses a decoder at the end to turn the result back into pixels. That is why it runs on a normal GPU.

## Generating an image

```python
from diffusers import StableDiffusionPipeline
import torch

pipe = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5", torch_dtype=torch.float16).to("cuda")

image = pipe(
    "a cozy classroom with students learning on laptops, soft light, illustration",
    negative_prompt="blurry, distorted, text",
    num_inference_steps=30,
    guidance_scale=7.5,
).images[0]
image.save("classroom.png")
```

(Display only; needs a GPU. Model names change over time.)

## Controls

| Setting | Effect |
| --- | --- |
| **Prompt** | what to draw: subject, style, lighting, camera |
| **Negative prompt** | what to avoid ("blurry, extra fingers") |
| **Steps** | more steps = more detail, slower (20 to 50 typical) |
| **Guidance scale** | higher follows the prompt more strictly, but can look harsh (5 to 9 typical) |
| **Seed** | the starting noise; the same seed and settings give the same image |

## Writing good image prompts

Structure: **subject + setting + style + lighting + details**.
"A friendly robot teacher in a bright Indian classroom, flat vector illustration, soft pastel colours, wide shot."

## Beyond text-to-image

| Technique | What it does |
| --- | --- |
| **Image-to-image** | start from your picture and restyle it |
| **Inpainting** | repaint only a masked area |
| **ControlNet** | follow a pose, edges or depth map |
| **LoRA** | small add-on that teaches a style or a subject |
| **Video diffusion** | the same idea over frames |

## GANs and VAEs

Earlier generators: **GANs** (a generator and a critic compete; sharp but unstable to train) and **VAEs** (compress and rebuild; the latent space idea used in Stable Diffusion). Diffusion became dominant because it trains stably and gives high quality and variety.

## Responsible use

Respect copyright and licences, do not create misleading fake images of real people (deepfakes), label AI-generated images, and add safety filters if users can type prompts.

:::note
For a portfolio project, a simple web page that turns a prompt into an image using a hosted image API is quick to build and easy to demonstrate.
:::
