# Model verification: `rasbt/ai-text-detector-modernbert`

Checked on 2026-10-18 before any classifier code was written. Everything below was read from the Hugging Face Hub or observed in a local run.

## Source

| Item | Value |
|---|---|
| Repository | https://huggingface.co/rasbt/ai-text-detector-modernbert |
| Pinned revision | `a6efd4bf6ecd852f332b2569ae0f98cae13b7985` (last modified 2026-08-11) |
| Licence | **Apache-2.0** (model card metadata and `LICENSE` file). Permits commercial and non-commercial use and redistribution with attribution, so deploying it inside this app is allowed. |
| Files used | `config.json`, `detector-config.json`, `model.safetensors` (299 MB), `tokenizer.json`, `tokenizer_config.json`, `LICENSE`, `README.md` |

## Architecture

| Item | Value |
|---|---|
| Architecture class | `ModernBertForSequenceClassification` (`model_type: modernbert`) |
| Base model | `answerdotai/ModernBERT-base`, fully fine-tuned, ~149.6M trainable parameters |
| Tokenizer | `tokenizer.json` (fast tokenizer), `model_max_length` 8192 |
| Maximum sequence length | 8192 tokens (`max_position_embeddings`, `detector-config.json: max_length`) |
| Problem type | `single_label_classification` |
| Trained with | transformers 5.14.1, torch 2.13.0 |

## Label mapping (copied verbatim)

`config.json`:
```json
"id2label": {"0": "HUMAN", "1": "AI"}
"label2id": {"AI": 1, "HUMAN": 0}
```
`detector-config.json`:
```json
"label_mapping": {"human": 0, "ai": 1}
```
Both files name the AI class explicitly and agree: **index 1 = AI**. The classifier still re-reads and cross-checks both at load time; if they're missing, disagree, or don't name an AI class, it reports `model_unavailable` with reason `label_mapping_unverified`.

## Training data, languages, calibration and limitations (from the model card and `detector-config.json`)

- Training data: `rasbt/human-vs-ai-50k`. Language: **English** (`language: en`).
- `calibration: "temperature scaling"`, `temperature: 1.566228609277514`, `decision_threshold: 0.5`, best validation accuracy 0.997 **on the author's own validation split**.
- The card's own limitation: performance may change for generators, domains, languages and editing workflows not in the training set; short or partly AI-assisted text is harder; *"The score should not be treated as definitive evidence that a person did or did not write a text."*
- Not stated: performance on customer-support tickets, non-native English, Hinglish, or translated text. We therefore treat it as **out of domain** for our tickets.

## Compatibility

| Package | Installed | Needed |
|---|---|---|
| transformers | 5.20.1 | ModernBERT support (present since 4.48; model was trained with 5.14.1) ✅ |
| torch | 2.14.1+cpu | CPU inference ✅ |
| Python | 3.14.8 | ✅ |

## Local load test (this laptop, CPU only)

| Measurement | Result |
|---|---|
| Download (7 files, pinned revision) | 151.7 s |
| Load tokenizer + model | 2.02 s |
| Memory | Not measured reliably: the weights are memory-mapped, so the working set barely changed at load (reported delta 0 MB). Expect roughly the weight size (~300 MB) once pages are touched. |
| `model.config.id2label` after load | `{0: 'HUMAN', 1: 'AI'}` ✅ |
| Inference, 1 short informal sentence (~20 tokens) | 424 ms → [HUMAN 0.5393, AI 0.4607] |
| Inference, 1 formal paragraph (~60 tokens) | 802 ms → [HUMAN 0.0085, **AI 0.9915**] |

The second text is a formal, plausibly human-written complaint, and it scored 0.99. This is the expected weakness of such detectors on formal or non-native writing, and the reason the feature only ever **suggests a manual review** and never decides anything.

## Chosen backend

**Real backend**, loaded from a local directory (`AI_INTEGRITY_MODEL_PATH`), with label mapping verified at load. If the path is empty, missing or fails verification, a **stub backend** returns `model_unavailable` and the rest of the feature keeps working.

Download (offline afterwards):
```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.download_integrity_model
```
