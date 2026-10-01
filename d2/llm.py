"""
llm.py -- envoltorio del modelo local (Hugging Face Transformers).

Dos operaciones, ambas deterministas:

  generate(prompt)          decodificacion greedy libre (baseline y alternativas).
  choose(prompt, options)   decodificacion restringida a un conjunto cerrado:
                            devuelve la opcion con mayor probabilidad de ser la
                            respuesta completa, P(opcion + fin de turno | prompt).

Las respuestas se cachean por prompt: con decodificacion greedy la misma
pregunta siempre da la misma respuesta, asi que repetirla solo gasta computo.
"""

from __future__ import annotations

import copy
import time
from typing import Dict, List, Optional, Sequence, Tuple

SYSTEM_PROMPT = "You are an AI playing Pokemon Blue."   # mismo system prompt que el D1

_END_MARKERS = ("<|im_end|>", "<|eot_id|>", "<|end|>", "<|endoftext|>", "</s>")


class HFModel:
    def __init__(self, model_id: str, device: Optional[str] = None, dtype: Optional[str] = None,
                 system_prompt: str = SYSTEM_PROMPT, verbose: bool = True):
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if dtype is not None:
            dtype = getattr(torch, dtype)
        elif self.device == "cuda" and torch.cuda.get_device_capability(0)[0] >= 8:
            dtype = torch.bfloat16          # Ampere o superior: bf16 nativo
        else:
            # T4 (sm75) y CPU: fp32. Qwen2/2.5 tiene casos documentados de desborde
            # numerico en fp16; en fp32 el modelo de 1.5B ocupa ~6 GB y cabe en la T4.
            dtype = torch.float32

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        # transformers >= 4.56 renombro torch_dtype -> dtype.
        major, minor = (int(x) for x in transformers.__version__.split(".")[:2])
        dtype_kw = "dtype" if (major, minor) >= (4, 56) else "torch_dtype"
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, low_cpu_mem_usage=True, **{dtype_kw: dtype})
        self.model.to(self.device).eval()

        pad = self.tokenizer.pad_token_id
        self.pad_id = pad if pad is not None else self.tokenizer.eos_token_id

        # Greedy con la configuracion de generacion por defecto del modelo, igual
        # que en el D1 (el D1 solo fijaba do_sample=False).
        self.gen_config = copy.deepcopy(self.model.generation_config)
        self.gen_config.do_sample = False
        self.gen_config.temperature = 1.0
        self.gen_config.top_p = 1.0
        self.gen_config.top_k = 50
        self.gen_config.pad_token_id = self.pad_id

        vocab = self.tokenizer.get_vocab()
        self.end_ids = {vocab[t] for t in _END_MARKERS if t in vocab}
        if self.tokenizer.eos_token_id is not None:
            self.end_ids.add(self.tokenizer.eos_token_id)

        self.revision = getattr(self.model.config, "_commit_hash", None)
        self.n_params = sum(p.numel() for p in self.model.parameters())
        self._gen_cache: Dict[Tuple[str, int], str] = {}
        self._choice_cache: Dict[Tuple[str, Tuple[str, ...]], Tuple[str, Dict[str, float]]] = {}
        self.calls = {"generate": 0, "choose": 0, "cache_hits": 0}

        if verbose:
            gpu = torch.cuda.get_device_name(0) if self.device == "cuda" else "-"
            print(f"[llm] {model_id} | revision {self.revision} | "
                  f"{self.n_params / 1e9:.2f}B params | {self.device} ({gpu}) | {dtype}")

    # ------------------------------------------------------------ helpers --
    def _messages(self, user: str) -> List[Dict[str, str]]:
        return [{"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user}]

    def _render(self, messages, add_generation_prompt: bool) -> str:
        return self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=add_generation_prompt)

    def _ids(self, text: str) -> List[int]:
        return self.tokenizer(text, add_special_tokens=False)["input_ids"]

    # ----------------------------------------------------------- generate --
    def generate(self, user: str, max_new_tokens: int = 32) -> str:
        key = (user, max_new_tokens)
        if key in self._gen_cache:
            self.calls["cache_hits"] += 1
            return self._gen_cache[key]
        torch = self.torch
        text = self._render(self._messages(user), add_generation_prompt=True)
        ids = torch.tensor([self._ids(text)], device=self.device)
        config = copy.deepcopy(self.gen_config)
        config.max_new_tokens = max_new_tokens
        with torch.inference_mode():
            out = self.model.generate(
                input_ids=ids, attention_mask=torch.ones_like(ids), generation_config=config)
        answer = self.tokenizer.decode(out[0, ids.shape[1]:], skip_special_tokens=True).strip()
        self._gen_cache[key] = answer
        self.calls["generate"] += 1
        return answer

    # ------------------------------------------------------------- choose --
    def choose(self, user: str, options: Sequence[str]) -> Tuple[str, Dict[str, float]]:
        """
        Decodificacion restringida: puntua cada opcion como respuesta COMPLETA
        (sus tokens + el token de fin de turno) y devuelve la mas probable,
        junto con las probabilidades renormalizadas sobre las opciones.
        """
        key = (user, tuple(options))
        if key in self._choice_cache:
            self.calls["cache_hits"] += 1
            return self._choice_cache[key]
        torch = self.torch
        messages = self._messages(user)
        prefix_ids = self._ids(self._render(messages, add_generation_prompt=True))

        sequences, starts = [], []
        for option in options:
            full = self._ids(self._render(
                messages + [{"role": "assistant", "content": option}],
                add_generation_prompt=False))
            k = 0                                   # prefijo comun con el prompt
            while k < min(len(prefix_ids), len(full)) and prefix_ids[k] == full[k]:
                k += 1
            end = len(full)                         # cortar justo despues del fin de turno
            for j in range(k, len(full)):
                if full[j] in self.end_ids:
                    end = j + 1
                    break
            sequences.append(full[:end])
            starts.append(k)

        width = max(len(s) for s in sequences)
        batch = torch.full((len(sequences), width), self.pad_id, dtype=torch.long)
        mask = torch.zeros_like(batch)
        for i, seq in enumerate(sequences):
            batch[i, :len(seq)] = torch.tensor(seq)
            mask[i, :len(seq)] = 1
        batch, mask = batch.to(self.device), mask.to(self.device)

        with torch.inference_mode():
            logits = self.model(input_ids=batch, attention_mask=mask).logits

        scores = []
        for i, seq in enumerate(sequences):
            k = starts[i]
            logp = torch.log_softmax(logits[i, k - 1:len(seq) - 1].float(), dim=-1)
            target = torch.tensor(seq[k:], device=logp.device)
            scores.append(logp.gather(1, target[:, None]).sum().item())

        probs_t = torch.softmax(torch.tensor(scores), dim=0)
        probs = {opt: round(p.item(), 4) for opt, p in zip(options, probs_t)}
        best = options[max(range(len(options)), key=lambda i: scores[i])]
        self._choice_cache[key] = (best, probs)
        self.calls["choose"] += 1
        return best, probs

    def describe(self) -> Dict:
        torch = self.torch
        import transformers
        return {
            "model_id": self.model_id,
            "revision": self.revision,
            "n_params": self.n_params,
            "device": self.device,
            "gpu": torch.cuda.get_device_name(0) if self.device == "cuda" else None,
            "dtype": str(next(self.model.parameters()).dtype),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "system_prompt": self.system_prompt,
            "decoding": "greedy (do_sample=False), default generation config otherwise",
            "calls": dict(self.calls),
        }
