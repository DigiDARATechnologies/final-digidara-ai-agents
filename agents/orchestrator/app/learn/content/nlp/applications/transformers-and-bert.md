---
title: Transformers and BERT for NLP tasks
summary: Use pre-trained BERT-style models for classification, NER and question answering with the Hugging Face library.
takeaways:
- Pre-trained models already understand language, so you need far less data
- The pipeline() helper runs a model in two lines
- Fine-tuning adapts a pre-trained model to your own labelled data
---
## Pre-training and transfer learning

Training a language model from scratch needs huge text and cost. Instead, organisations release **pre-trained** models (BERT, RoBERTa, DistilBERT, and many more) that already understand grammar and meaning. You **reuse** them: this is **transfer learning**, the same idea as ImageNet models in computer vision.

**BERT** reads text in **both directions** at once, so it is excellent at **understanding** tasks: classification, NER, question answering, search. (GPT-style models read left to right and are built for **generation**.)

## Hugging Face pipelines

The `transformers` library gives ready-made models.

```python
from transformers import pipeline

classifier = pipeline("sentiment-analysis")
print(classifier("The delivery was late but the support team was wonderful."))
# [{'label': 'POSITIVE', 'score': 0.99}]

ner = pipeline("ner", aggregation_strategy="simple")
print(ner("Asha joined Infosys in Chennai in 2024."))
# entities: Asha (person), Infosys (organisation), Chennai (location)

qa = pipeline("question-answering")
print(qa(question="When does the library close?",
         context="The library is open from 8 am to 8 pm on weekdays."))
# {'answer': '8 pm', ...}
```

(Display only. The first run downloads the model. Output shapes shown in comments.)

## Fine-tuning for your task

When the general model is not accurate enough on your data (for example support tickets in your own words), **fine-tune** it on a few hundred or thousand labelled examples.

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments

name = "distilbert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(name)
model = AutoModelForSequenceClassification.from_pretrained(name, num_labels=4)

def encode(batch):
    return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=128)

# train_data and test_data are Hugging Face datasets with "text" and "label" columns
train_data = train_data.map(encode, batched=True)
test_data = test_data.map(encode, batched=True)

trainer = Trainer(
    model=model,
    args=TrainingArguments(output_dir="out", num_train_epochs=3, per_device_train_batch_size=16),
    train_dataset=train_data,
    eval_dataset=test_data,
)
trainer.train()
```

The steps: load a pre-trained model, tokenise your text with **its** tokenizer, train for a few epochs with a small learning rate, evaluate on held-out data.

## Choosing a model

| Need | Choice |
| --- | --- |
| fast, small, runs on CPU | DistilBERT, MiniLM |
| best accuracy | RoBERTa, DeBERTa |
| Indian languages | multilingual models (mBERT, XLM-R, IndicBERT) |
| open-ended text generation | an LLM (Generative AI course) |

## Practical tips

- Use a GPU for fine-tuning (Google Colab is free to start).
- Start with a **small** model; upgrade only if needed.
- Keep a **test set** the model never trains on.
- Compare against your TF-IDF baseline. If the gain is small, the baseline may win on cost.

:::remember
BERT-style models understand text, GPT-style models generate it. For classification, NER and search, use pre-trained BERT-like models and fine-tune them.
:::
