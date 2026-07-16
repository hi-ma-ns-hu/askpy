"""
scripts/finetune_dpo.py — Fine-tune a language model using DPO (Direct Preference
Optimization) on preference pairs from generate_dpo_data.py.

Designed to run on Colab (free T4 GPU) after SFT from Week 10.

Pipeline:
  1. Load the SFT-trained model (or a base model if skipping SFT)
  2. Apply QLoRA — quantize to 4-bit, add trainable LoRA adapters
  3. Train with DPO loss on (prompt, chosen, rejected) triples
  4. Save the merged model or just the adapter

Why QLoRA here:
  A 7B model is ~14GB in fp16. A free Colab T4 has 15GB VRAM.
  That leaves ~1GB for activations and gradients — not enough.
  QLoRA compresses the frozen base model to 4-bit (~3.5GB), leaving ~11GB
  for the LoRA adapter weights and optimizer states. Fits with headroom.

What DPO trains vs what SFT trains:
  SFT:  maximize P(chosen_token | prompt)   — "say this"
  DPO:  maximize P(chosen | prompt) - P(rejected | prompt)
        — "prefer this over that, by this margin"

  The loss function: L = -log σ(β * (log π(chosen) - log π(rejected) - log ref(chosen) + log ref(rejected)))
  β controls how strongly to penalize deviation from the reference model.
  β=0.1 is conservative (stays close to SFT). β=0.5 diverges more aggressively.

Run on Colab:
  !pip install trl peft bitsandbytes transformers datasets accelerate
  !python scripts/finetune_dpo.py --model your-sft-model --epochs 1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_dataset(path: str):
    """Load DPO JSONL into HuggingFace Dataset format."""
    from datasets import Dataset

    rows = []
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            rows.append({
                "prompt":   row["prompt"],
                "chosen":   row["chosen"],
                "rejected": row["rejected"],
            })
    return Dataset.from_list(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune with DPO + QLoRA")
    parser.add_argument("--model",      default="meta-llama/Llama-3.2-1B-Instruct",
                        help="Base or SFT model to fine-tune. Use a small model on CPU.")
    parser.add_argument("--data",       default="data/dpo_train.jsonl")
    parser.add_argument("--output",     default="models/AskPy-dpo")
    parser.add_argument("--epochs",     type=int,   default=1)
    parser.add_argument("--batch-size", type=int,   default=2)
    parser.add_argument("--beta",       type=float, default=0.1,
                        help="DPO beta — how much to diverge from reference model")
    parser.add_argument("--lora-r",     type=int,   default=16,
                        help="LoRA rank — higher = more trainable params = more capacity")
    parser.add_argument("--no-qlora",   action="store_true",
                        help="Disable 4-bit quantization (requires enough VRAM for full model)")
    args = parser.parse_args()

    print(f"loading model: {args.model}")
    print(f"  qlora: {not args.no_qlora}, lora_r: {args.lora_r}, beta: {args.beta}")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import DPOTrainer, DPOConfig

    # ── Step 1: load tokenizer ─────────────────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── Step 2: load model, optionally quantized to 4-bit ─────────────────────
    if not args.no_qlora:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",        # NormalFloat4 — better than int4 for LLMs
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,   # quantize the quantization constants too
        )
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            quantization_config=bnb_config,
            device_map="auto",
        )
        model = prepare_model_for_kbit_training(model)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

    # ── Step 3: add LoRA adapters (the only trainable weights) ────────────────
    # target_modules: which weight matrices to inject LoRA into.
    # q_proj + v_proj = attention query and value projections.
    # These carry most of the "style" information — good default for preference tuning.
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_r * 2,    # alpha=2*r is standard; controls scale of update
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()   # should show ~1% of total params

    # ── Step 4: load dataset ───────────────────────────────────────────────────
    print(f"\nloading pairs from {args.data} ...")
    dataset = _load_dataset(args.data)
    split = dataset.train_test_split(test_size=0.05, seed=42)
    print(f"  train: {len(split['train'])}, eval: {len(split['test'])}")

    # ── Step 5: DPO training ───────────────────────────────────────────────────
    # DPOTrainer needs a reference model (frozen copy of the SFT model) to compute
    # the baseline log-probabilities. When ref_model=None, it uses the model itself
    # before any updates as the reference — fine for small experiments.
    training_args = DPOConfig(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=4,      # effective batch = batch_size * 4
        learning_rate=5e-5,
        beta=args.beta,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        logging_steps=10,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        report_to="none",
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=training_args,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        processing_class=tokenizer,
    )

    print(f"\ntraining {args.epochs} epoch(s) with DPO (beta={args.beta}) ...")
    print("watch: rewards/chosen should rise, rewards/rejected should fall\n")
    trainer.train()

    print(f"\nsaving adapter → {args.output}")
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    print(f"\nnext steps:")
    print(f"  test: load the adapter and ask 'how do I read a CSV in pandas'")
    print(f"  compare directness vs your SFT model")
    print(f"  look for: leads with code, fewer hedge phrases ('you could try...')")


if __name__ == "__main__":
    main()
