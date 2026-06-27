---
name: agent-training
description: 在 HarnessAgent 项目中实现 Agent 的强化学习训练和能力评估。Use when: (1) 训练 Agent 模型(SFT监督微调/GRPO强化学习), (2) 设计奖励函数(准确性/长度惩罚/步骤奖励), (3) Agent 能力评估(BFCL函数调用/GAIA真实任务), (4) 生成训练数据并评估数据质量, (5) LLM Judge 自动化评估, (6) 配置分布式训练(多GPU/DeepSpeed)。
---

# Agent Training — 训练微调与能力评估

## 概述

本技能覆盖 Agent 模型的完整训练流程：从 SFT 监督微调到 GRPO 强化学习，从奖励函数设计到标准化评估。同时也覆盖训练数据的生成与质量评估——用 LLM 生成训练数据，再用 LLM Judge 评估质量，形成数据闭环。

## 训练流程概览

```
数据准备 → SFT训练 → SFT评估 → GRPO训练 → GRPO评估 → 保存部署
```

```python
class AgenticRLPipeline:
    """Agent 强化学习训练的完整 6 阶段管道"""

    def __init__(self, config: dict):
        self.config = config
        self.results = {}  # 每阶段结果

    def run(self):
        print("📊 阶段1: 数据准备")
        dataset = self.stage1_prepare_data()

        print("🎯 阶段2: SFT 监督微调")
        sft_model_path = self.stage2_sft_training(dataset)

        print("📏 阶段3: SFT 评估")
        sft_metrics = self.stage3_evaluate(sft_model_path, "sft")
        self.results["sft"] = sft_metrics

        print("🚀 阶段4: GRPO 强化学习")
        grpo_model_path = self.stage4_grpo_training(sft_model_path)

        print("📏 阶段5: GRPO 评估")
        grpo_metrics = self.stage5_evaluate(grpo_model_path, "grpo")
        self.results["grpo"] = grpo_metrics

        print("💾 阶段6: 保存结果")
        self.stage6_save_results()

        return self._compare_results()
```

## SFT 监督微调

### 训练配置

```python
sft_config = {
    "action": "train",
    "algorithm": "sft",
    "model_name": "Qwen/Qwen3-0.6B",       # 基座模型
    "dataset_path": "./data/training_data.json",
    "output_dir": "./output/sft_model",
    "max_samples": 1000,                     # None = 使用全部数据
    "num_epochs": 3,
    "batch_size": 4,
    "learning_rate": 5e-5,                   # 推荐起始值
    "warmup_steps": 100,
    "use_lora": True,                        # 参数高效微调
    "lora_r": 16,                            # LoRA 秩
    "lora_alpha": 32,                        # LoRA 缩放
    "lora_target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "use_wandb": False,                      # Weights & Biases 监控
    "use_tensorboard": True,                 # TensorBoard 监控
    "save_steps": 500,
    "eval_steps": 500,
}
```

### 学习率选择指南

| 学习率 | 标签 | 场景 | 预期行为 |
|--------|------|------|---------|
| 1e-5 | 保守 | 模型已经很好，只需微调 | loss 缓慢下降，不易过拟合 |
| 5e-5 | **推荐** | 标准训练，平衡速度和稳定性 | 稳定收敛 |
| 1e-4 | 激进 | 快速实验，小数据集 | 可能不稳定，需监控 loss 震荡 |
| 5e-5→1e-5 | **余弦衰减** | 从推荐值衰减到保守值 | 前期快速学习+后期精细调优 |

### 显存优化配置

```python
# 4GB 显存：最小化配置
config_4gb = {
    "batch_size": 1,
    "gradient_accumulation_steps": 4,  # 累积梯度模拟大 batch
    "use_lora": True,
    "lora_r": 8,
    "lora_alpha": 16,
    "max_seq_length": 512,
    "use_fp16": True,                  # 混合精度
}

# 8GB 显存：标准配置
config_8gb = {
    "batch_size": 2,
    "gradient_accumulation_steps": 2,
    "use_lora": True,
    "lora_r": 16,
    "lora_alpha": 32,
    "max_seq_length": 1024,
    "use_fp16": True,
}

# 16GB+ 显存：高效配置
config_16gb = {
    "batch_size": 4,
    "gradient_accumulation_steps": 1,
    "use_lora": True,
    "lora_r": 32,
    "lora_alpha": 64,
    "max_seq_length": 2048,
    "use_bf16": True,                  # BF16 更稳定
}
```

### 训练数据格式

```python
# SFT 训练数据——conversations 格式
training_data = [
    {
        "conversations": [
            {"role": "system", "content": "你是一个数学解题助手。"},
            {"role": "user", "content": "计算 123 * 456"},
            {"role": "assistant", "content": "让我一步步计算...\n123 × 456 = 56088"}
        ]
    },
    {
        "conversations": [
            {"role": "system", "content": "你是一个代码助手。"},
            {"role": "user", "content": "写一个快速排序"},
            {"role": "assistant", "content": "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    ..."}
        ]
    }
]

# 数据质量检查
def validate_training_data(data: list) -> dict:
    issues = []
    for i, item in enumerate(data):
        convs = item.get("conversations", [])
        if len(convs) < 2:
            issues.append(f"第{i}条: 对话轮次不足")
        if not any(m["role"] == "assistant" for m in convs):
            issues.append(f"第{i}条: 缺少 assistant 回复")
        total_tokens = sum(len(str(m["content"]).split()) for m in convs)
        if total_tokens > 4096:
            issues.append(f"第{i}条: Token 数 {total_tokens} 可能超出限制")
    return {"total": len(data), "issues": len(issues), "details": issues}
```

## 奖励函数设计

### 三种奖励函数类型

```python
class RewardFunctionFactory:
    """奖励函数工厂——创建不同类型的奖励函数"""

    @staticmethod
    def create(config: dict):
        reward_type = config.get("reward_type", "accuracy")

        if reward_type == "accuracy":
            return AccuracyReward()
        elif reward_type == "length_penalty":
            return LengthPenaltyReward(
                penalty_weight=config.get("penalty_weight", 0.001),
                max_length=config.get("max_length", 512)
            )
        elif reward_type == "step":
            return StepReward(
                step_bonus=config.get("step_bonus", 0.1),
                max_steps=config.get("max_steps", 10)
            )
        elif reward_type == "composite":
            # 组合多种奖励
            return CompositeReward([
                AccuracyReward(),
                LengthPenaltyReward(),
                StepReward()
            ], weights=[0.6, 0.2, 0.2])
        else:
            raise ValueError(f"未知奖励类型: {reward_type}")
```

### 准确性奖励

```python
class AccuracyReward:
    """只关注答案正确性——正确+1.0，错误0.0"""

    def __call__(self, prediction: str, ground_truth: str) -> float:
        pred_answer = self._extract_answer(prediction)
        truth_answer = self._extract_answer(ground_truth)

        if pred_answer is None or truth_answer is None:
            return 0.0

        # 数值比较（容差范围内）
        if self._is_numeric(pred_answer) and self._is_numeric(truth_answer):
            return 1.0 if abs(float(pred_answer) - float(truth_answer)) < 1e-4 else 0.0

        # 字符串精确匹配
        return 1.0 if pred_answer.strip().lower() == truth_answer.strip().lower() else 0.0

    def _extract_answer(self, text: str) -> str:
        """按优先级提取答案: Final Answer > #### > 最后数字 > 全文最后一行"""
        import re

        # 模式1: "Final Answer: 42" 或 "最终答案：42"
        match = re.search(r'(?:Final Answer|最终答案)[：:]\s*(.+?)(?:\n|$)', text)
        if match:
            return match.group(1).strip()

        # 模式2: "#### 100"
        match = re.search(r'####\s*(.+?)(?:\n|$)', text)
        if match:
            return match.group(1).strip()

        # 模式3: 最后一个数字
        numbers = re.findall(r'-?\d+\.?\d*', text)
        if numbers:
            return numbers[-1]

        # 模式4: 最后一行
        lines = text.strip().split('\n')
        return lines[-1].strip() if lines else None

    def _is_numeric(self, s: str) -> bool:
        try:
            float(s)
            return True
        except ValueError:
            return False
```

### 长度惩罚奖励

```python
class LengthPenaltyReward:
    """鼓励简洁——过长的回答会受到惩罚"""

    def __init__(self, penalty_weight: float = 0.001, max_length: int = 512):
        self.penalty_weight = penalty_weight
        self.max_length = max_length

    def __call__(self, prediction: str, ground_truth: str = "") -> float:
        token_count = len(prediction.split())

        if token_count <= self.max_length:
            return 0.0  # 没超出，不惩罚

        # 超出 max_length 部分的线性惩罚
        excess = token_count - self.max_length
        penalty = excess * self.penalty_weight
        return max(-1.0, -penalty)  # 惩罚上限 -1.0
```

### 步骤奖励

```python
class StepReward:
    """鼓励详细推理——有推理步骤的回答获得额外奖励"""

    def __init__(self, step_bonus: float = 0.1, max_steps: int = 10):
        self.step_bonus = step_bonus
        self.max_steps = max_steps

    def __call__(self, prediction: str, ground_truth: str = "") -> float:
        # 通过关键词检测推理步骤
        step_markers = [
            r'步骤\s*\d+', r'Step\s*\d+',
            r'第[一二三四五六七八九十\d]+步',
            r'\d+\.\s',  # 编号列表
            r'(?:首先|然后|接着|最后|其次|再|接下来)',
        ]

        total_steps = 0
        for marker in step_markers:
            total_steps += len(re.findall(marker, prediction))

        # 有步骤但不超过最大步数
        if total_steps > 0:
            bonus = min(total_steps, self.max_steps) * self.step_bonus
            return min(bonus, 1.0)  # 奖励上限 1.0

        return 0.0  # 无步骤，无额外奖励
```

### 组合奖励

```python
class CompositeReward:
    """组合多种奖励——加权求和"""

    def __init__(self, rewards: list, weights: list[float] = None):
        self.rewards = rewards
        self.weights = weights or [1.0 / len(rewards)] * len(rewards)

    def __call__(self, prediction: str, ground_truth: str) -> float:
        total = 0.0
        for reward_fn, weight in zip(self.rewards, self.weights):
            score = reward_fn(prediction, ground_truth)
            total += score * weight
        return total
```

## 分布式训练配置

```yaml
# accelerate_configs/multi_gpu_ddp.yaml
compute_environment: LOCAL_MACHINE
distributed_type: MULTI_GPU
num_processes: 4                    # 4 GPU
mixed_precision: fp16
gradient_accumulation_steps: 2

# accelerate_configs/deepspeed_zero2.yaml
compute_environment: LOCAL_MACHINE
distributed_type: DEEPSPEED
deepspeed_config:
  zero_stage: 2                     # 优化器状态 + 梯度分片
  offload_optimizer_device: cpu     # 优化器状态卸载到 CPU
  offload_param_device: none
  zero3_init_flag: false

# accelerate_configs/deepspeed_zero3.yaml
deepspeed_config:
  zero_stage: 3                     # 参数 + 优化器 + 梯度全分片
  offload_optimizer_device: cpu
  offload_param_device: cpu         # 参数也卸载到 CPU
  zero3_save_16bit_model: true      # 保存时合并为 16bit
  zero3_init_flag: true
```

## Agent 评估

### BFCL — 函数调用能力评估

```python
# BFCL (Berkeley Function Calling Leaderboard) 评估维度
BFCL_DIMENSIONS = {
    "simple_python":       "简单 Python 函数调用——单个函数、单轮",
    "multi_turn":          "多轮函数调用——需要上下文传递",
    "parallel":            "并行调用多个函数",
    "live":                "实时 API 调用——需要真实网络请求",
    "agentic":             "Agent 自主决策——何时调用、调用什么",
    "format_sensitivity":  "格式敏感性——对 prompt 变化的鲁棒性",
}

# 评估结果输出
# score/
# ├── data_overall.csv           # 总体得分
# ├── data_simple_python.csv     # 各维度得分
# ├── data_multi_turn.csv
# ├── data_live.csv
# ├── data_agentic.csv
# └── data_format_sensitivity.csv
```

### GAIA — 真实世界任务评估

```python
# GAIA 评估 Agent 解决真实问题的能力
GAIA_CONFIG = {
    "levels": {
        "Level 1": "简单信息检索和推理",
        "Level 2": "多步推理和工具使用",
        "Level 3": "复杂规划、多工具协同"
    },
    "evaluation": {
        "metric": "exact_match",     # 答案与 ground truth 精确匹配
        "timeout_per_task": 300,     # 每任务 5 分钟
        "max_tool_calls": 20,        # 最多 20 次工具调用
    }
}

class GAIARunner:
    def evaluate(self, agent, dataset_path: str) -> dict:
        questions = self._load_dataset(dataset_path)
        results = {"Level 1": [], "Level 2": [], "Level 3": []}

        for q in questions:
            result = agent.run(q["question"])
            score = 1.0 if self._match(result, q["ground_truth"]) else 0.0
            results[q["level"]].append({
                "question": q["question"],
                "prediction": result,
                "ground_truth": q["ground_truth"],
                "score": score
            })

        # 计算各级别准确率
        metrics = {}
        for level, items in results.items():
            metrics[level] = {
                "accuracy": sum(i["score"] for i in items) / len(items),
                "total": len(items)
            }

        metrics["overall"] = {
            "accuracy": sum(
                m["accuracy"] * m["total"] for m in metrics.values()
            ) / sum(m["total"] for m in metrics.values())
        }
        return metrics
```

## 数据生成与质量评估

### LLM 生成训练数据

```python
class TrainingDataGenerator:
    """用 LLM 生成 Agent 训练数据——数学题、代码题等"""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.llm = HelloAgentsLLM(model=model)

    def generate_math_problems(self, count: int = 30,
                                difficulty: str = "medium") -> list[dict]:
        """生成 AIME 风格的数学题"""
        prompt = (
            f"生成 {count} 道 {difficulty} 难度的数学题。\n"
            f"每道题包含:\n"
            f"1. 问题描述\n"
            f"2. 完整的逐步解答过程\n"
            f"3. 最终答案\n\n"
            f"输出 JSON 格式:\n"
            f'[{{"question": "...", "solution": "...", "answer": "..."}}, ...]\n\n'
            f"要求:\n"
            f"- 问题有唯一确定答案\n"
            f"- 解答过程逻辑清晰、步骤完整\n"
            f"- 答案格式统一（数字/表达式）"
        )
        response = self.llm.invoke([{"role": "user", "content": prompt}])
        return json.loads(self._extract_json(response))

    def generate_code_tasks(self, count: int = 30) -> list[dict]:
        """生成代码任务"""
        prompt = (
            f"生成 {count} 个 Python 编程任务。\n"
            f"每道题包含: 问题描述、函数签名、测试用例、参考解答\n"
            f"输出 JSON 格式。难度分布: 简单30%、中等50%、困难20%"
        )
        response = self.llm.invoke([{"role": "user", "content": prompt}])
        return json.loads(self._extract_json(response))
```

### LLM Judge 质量评估

```python
class LLMJudge:
    """用 LLM 作为评判者评估生成内容质量"""

    DIMENSIONS = {
        "正确性": "答案和推理过程是否正确，答案是否无歧义",
        "清晰度": "问题表述是否清晰，无二义性，易于理解",
        "难度匹配": "是否达到目标难度等级，不过于简单或困难",
        "完整性": "是否包含完整的解题所需信息，无缺失条件",
    }

    RUBRIC = """请按以下维度评分(1-5分):

1. 正确性 (5分: 完全正确，答案和推理无瑕疵; 1分: 答案错误或推理有严重缺陷)
2. 清晰度 (5分: 表述非常清晰，无歧义; 1分: 混乱难懂)
3. 难度匹配 (5分: 完美匹配目标难度; 1分: 严重偏离)
4. 完整性 (5分: 信息完整，无需额外假设; 1分: 缺失关键信息)

只回复 JSON: {"正确性": N, "清晰度": N, "难度匹配": N, "完整性": N, "总评": "一句话"}"""

    def evaluate(self, item: dict, target_difficulty: str = "medium") -> dict:
        prompt = (
            f"评估以下生成内容:\n\n"
            f"目标难度: {target_difficulty}\n\n"
            f"内容:\n{json.dumps(item, ensure_ascii=False, indent=2)}\n\n"
            f"{self.RUBRIC}"
        )
        response = self.llm.invoke([{"role": "user", "content": prompt}])
        try:
            scores = json.loads(self._extract_json(response))
            scores["average"] = sum(
                scores.get(d, 0) for d in self.DIMENSIONS
            ) / len(self.DIMENSIONS)
            return scores
        except json.JSONDecodeError:
            return {"error": "无法解析评分", "raw": response}
```

### Win Rate 评估

```python
class WinRateEvaluator:
    """对比评估——生成题目 vs 参考数据集"""

    def __init__(self, judge_model: str = "gpt-4o"):
        self.judge = LLMJudge(model=judge_model)

    def compare(self, generated: list[dict],
                reference: list[dict], count: int = 100) -> dict:
        """逐对比较，统计 Win Rate"""
        import random
        pairs = list(zip(
            random.sample(generated, min(count, len(generated))),
            random.sample(reference, min(count, len(reference)))
        ))

        results = {"win": 0, "tie": 0, "loss": 0}

        for gen, ref in pairs:
            prompt = (
                f"请比较以下两道数学题的质量:\n\n"
                f"题目 A:\n{json.dumps(gen, ensure_ascii=False)}\n\n"
                f"题目 B:\n{json.dumps(ref, ensure_ascii=False)}\n\n"
                f"哪个更好？只回复: A更好 / B更好 / 差不多"
            )
            response = self.judge.llm.invoke([{"role": "user", "content": prompt}])
            if "A更好" in response:
                results["win"] += 1
            elif "B更好" in response:
                results["loss"] += 1
            else:
                results["tie"] += 1

        total = len(pairs)
        return {
            "win_rate": results["win"] / total,
            "tie_rate": results["tie"] / total,
            "loss_rate": results["loss"] / total,
            "total_pairs": total
        }
        # 理想结果: Win Rate ≈ 50%（生成质量与参考数据相当）
```

## GRPO 强化学习

### GRPO 训练配置

```python
grpo_config = {
    "action": "train",
    "algorithm": "grpo",
    "base_model": "./output/sft_model",     # SFT 模型作为起点
    "output_dir": "./output/grpo_model",
    "num_epochs": 1,
    "batch_size": 8,
    "learning_rate": 1e-6,                   # GRPO 用更小的学习率
    "num_generations": 4,                    # 每个 prompt 生成 N 个候选
    "reward_function": "composite",          # 使用组合奖励
    "kl_penalty": 0.01,                      # KL 散度惩罚（防止偏离太远）
    "max_new_tokens": 512,
    "temperature": 0.7,                      # 生成多样性控制
}
```

### GRPO 训练循环核心

```python
class GRPOTrainer:
    """GRPO (Group Relative Policy Optimization) 训练器"""

    def train_step(self, batch: list[dict]) -> dict:
        """单步训练"""
        prompts = [item["prompt"] for item in batch]
        references = [item["reference"] for item in batch]

        # 1. 对每个 prompt 生成多个候选回答
        all_candidates = []
        all_rewards = []
        for prompt, reference in zip(prompts, references):
            candidates = [
                self.model.generate(prompt, temperature=self.temperature)
                for _ in range(self.config["num_generations"])
            ]
            # 计算每个候选的奖励
            rewards = [
                self.reward_function(c, reference)
                for c in candidates
            ]
            all_candidates.append(candidates)
            all_rewards.append(rewards)

        # 2. 计算相对优势（组内归一化）
        advantages = []
        for rewards in all_rewards:
            mean_r = sum(rewards) / len(rewards)
            std_r = (sum((r - mean_r) ** 2 for r in rewards) / len(rewards)) ** 0.5
            if std_r == 0:
                std_r = 1.0
            advantages.append([(r - mean_r) / std_r for r in rewards])

        # 3. 用优势加权更新策略
        loss = self._compute_grpo_loss(all_candidates, advantages)

        # 4. 添加 KL 惩罚
        kl_div = self._compute_kl_divergence()
        total_loss = loss + self.config["kl_penalty"] * kl_div

        return {"loss": total_loss, "kl_divergence": kl_div}
```

## 参考资源

| 文件 | 内容 | 何时查阅 |
|------|------|---------|
| [rl-training.md](references/rl-training.md) | SFT 配置、GRPO 训练循环、奖励函数完整实现 | 训练 Agent 模型时 |
| [evaluation.md](references/evaluation.md) | BFCL/GAIA 评估、LLM Judge、Win Rate、数据生成 | 评估 Agent 能力时 |

> 📌 本技能覆盖 Hello Agent 教程 Ch11,12。Agent 核心范式见 agent-builder 技能，工具系统见 agent-tools 技能。
