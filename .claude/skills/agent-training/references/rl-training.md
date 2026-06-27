# Agent 训练参考

## SFT 训练完整流程

```python
class SFTTrainer:
    """监督微调训练器"""

    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self.tokenizer = None

    def train(self, dataset_path: str) -> str:
        """执行 SFT 训练，返回模型保存路径"""
        from transformers import (
            AutoModelForCausalLM, AutoTokenizer,
            TrainingArguments, Trainer,
            DataCollatorForLanguageModeling
        )
        from peft import LoraConfig, get_peft_model, TaskType
        from datasets import Dataset

        # 1. 加载数据
        raw_data = self._load_dataset(dataset_path)
        formatted_data = self._format_conversations(raw_data)
        dataset = Dataset.from_list(formatted_data)

        # 2. 加载模型
        model_name = self.config["model_name"]
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16 if self.config.get("use_bf16") else torch.float16,
            trust_remote_code=True
        )

        # 3. 配置 LoRA
        if self.config.get("use_lora"):
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=self.config.get("lora_r", 16),
                lora_alpha=self.config.get("lora_alpha", 32),
                lora_dropout=0.1,
                target_modules=self.config.get("lora_target_modules",
                    ["q_proj", "v_proj", "k_proj", "o_proj"])
            )
            self.model = get_peft_model(self.model, lora_config)
            self.model.print_trainable_parameters()

        # 4. 分词
        def tokenize(example):
            text = example["text"]
            tokens = self.tokenizer(
                text, truncation=True,
                max_length=self.config.get("max_seq_length", 2048),
                padding="max_length"
            )
            tokens["labels"] = tokens["input_ids"].copy()
            return tokens

        tokenized = dataset.map(tokenize, remove_columns=dataset.column_names)

        # 5. 训练参数
        training_args = TrainingArguments(
            output_dir=self.config["output_dir"],
            num_train_epochs=self.config.get("num_epochs", 3),
            per_device_train_batch_size=self.config.get("batch_size", 4),
            gradient_accumulation_steps=self.config.get("gradient_accumulation_steps", 1),
            learning_rate=self.config.get("learning_rate", 5e-5),
            warmup_steps=self.config.get("warmup_steps", 100),
            logging_steps=50,
            save_steps=self.config.get("save_steps", 500),
            eval_steps=self.config.get("eval_steps", 500),
            fp16=self.config.get("use_fp16", True),
            bf16=self.config.get("use_bf16", False),
            report_to="tensorboard" if self.config.get("use_tensorboard") else "none",
        )

        # 6. 训练
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized,
            data_collator=DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer, mlm=False
            )
        )
        trainer.train()

        # 7. 保存
        output_dir = self.config["output_dir"]
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)

        return output_dir

    def _format_conversations(self, data: list) -> list:
        """将 conversations 格式化为训练文本"""
        texts = []
        for item in data:
            convs = item.get("conversations", [])
            lines = []
            for turn in convs:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role == "system":
                    lines.append(f"<|system|>\n{content}")
                elif role == "user":
                    lines.append(f"<|user|>\n{content}")
                elif role == "assistant":
                    lines.append(f"<|assistant|>\n{content}")
            texts.append({"text": "\n".join(lines)})
        return texts
```

## 训练数据准备

```python
class TrainingDataPreparator:
    """训练数据准备——加载、清洗、格式转换、质量检查"""

    def load_dataset(self, path: str, max_samples: int = None) -> list:
        """支持 .json / .jsonl / .parquet"""
        import json

        if path.endswith(".jsonl"):
            with open(path) as f:
                data = [json.loads(line) for line in f]
        elif path.endswith(".json"):
            with open(path) as f:
                data = json.load(f)
        elif path.endswith(".parquet"):
            import pandas as pd
            data = pd.read_parquet(path).to_dict(orient="records")
        else:
            raise ValueError(f"不支持的数据格式: {path}")

        if max_samples:
            data = data[:max_samples]

        return data

    def validate(self, data: list) -> dict:
        """数据质量检查"""
        issues = []
        stats = {"total": len(data), "valid": 0, "issues": []}

        for i, item in enumerate(data):
            convs = item.get("conversations", [])
            item_issues = []

            # 检查对话结构
            if len(convs) < 2:
                item_issues.append("对话轮次 < 2")

            # 检查是否有 assistant 回复
            if not any(m.get("role") == "assistant" for m in convs):
                item_issues.append("缺少 assistant 回复")

            # 检查内容不为空
            if any(not m.get("content", "").strip() for m in convs):
                item_issues.append("存在空内容")

            # 检查长度
            total_chars = sum(len(m.get("content", "")) for m in convs)
            if total_chars > 100000:
                item_issues.append(f"总字符数 {total_chars} 可能过长")

            if item_issues:
                issues.append({"index": i, "issues": item_issues})
            else:
                stats["valid"] += 1

        stats["issues"] = issues
        return stats
```

## GRPO 训练配置

```python
class GRPOTrainer:
    """GRPO 强化学习训练器"""

    def __init__(self, config: dict, reward_function):
        self.config = config
        self.reward_fn = reward_function
        self.model = None
        self.ref_model = None  # 参考模型——计算 KL 散度

    def train(self, prompts: list[str], references: list[str]):
        """GRPO 训练循环"""
        self.model = self._load_model(self.config["base_model"])
        self.ref_model = self._load_model(self.config["base_model"])
        self.ref_model.eval()  # 参考模型不更新

        for epoch in range(self.config.get("num_epochs", 1)):
            for batch in self._batchify(prompts, references):
                loss = self._train_step(batch)
                yield {"epoch": epoch, "loss": loss}

    def _train_step(self, batch: list[dict]) -> float:
        prompts = [b["prompt"] for b in batch]
        references = [b["reference"] for b in batch]
        num_generations = self.config.get("num_generations", 4)

        # 1. 为每个 prompt 生成多个候选回答
        all_candidates = []
        all_rewards = []
        for prompt, ref in zip(prompts, references):
            candidates = [
                self._generate(prompt)
                for _ in range(num_generations)
            ]
            rewards = [self.reward_fn(c, ref) for c in candidates]
            all_candidates.append(candidates)
            all_rewards.append(rewards)

        # 2. 组内归一化——计算相对优势
        all_advantages = []
        for rewards in all_rewards:
            mean = sum(rewards) / len(rewards)
            std = (sum((r - mean) ** 2 for r in rewards) / len(rewards)) ** 0.5
            if std == 0:
                std = 1.0
            all_advantages.append([(r - mean) / std for r in rewards])

        # 3. 计算 GRPO Loss
        # L = -E[advantage * log π(a|s) / π_old(a|s)]
        total_loss = 0.0
        for candidates, advantages in zip(all_candidates, all_advantages):
            for candidate, advantage in zip(candidates, advantages):
                # 策略损失
                log_prob = self._get_log_prob(candidate)
                ref_log_prob = self._get_ref_log_prob(candidate)
                ratio = torch.exp(log_prob - ref_log_prob)
                policy_loss = -advantage * ratio

                # KL 惩罚
                kl_penalty = self.config.get("kl_penalty", 0.01)
                kl_div = self._compute_kl(log_prob, ref_log_prob)

                total_loss += policy_loss + kl_penalty * kl_div

        # 4. 反向传播
        total_loss.backward()
        self.optimizer.step()
        self.optimizer.zero_grad()

        return total_loss.item()
```
