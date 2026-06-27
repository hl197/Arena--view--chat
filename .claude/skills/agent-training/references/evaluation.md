# Agent 能力评估参考

## BFCL 函数调用评估

```python
class BFCLEvaluator:
    """Berkeley Function Calling Leaderboard 评估"""

    CATEGORIES = [
        "simple_python", "multiple_python", "parallel_python",
        "multi_turn", "live", "agentic", "format_sensitivity",
    ]

    def __init__(self, agent, dataset_path: str):
        self.agent = agent
        self.dataset = self._load_dataset(dataset_path)

    def evaluate(self) -> dict:
        results = {cat: {"correct": 0, "total": 0} for cat in self.CATEGORIES}
        for item in self.dataset:
            category = item.get("category", "unknown")
            if category not in results:
                continue
            prediction = self.agent.run(item["question"])
            is_correct = self._check_correctness(prediction, item["ground_truth"], category)
            results[category]["total"] += 1
            if is_correct:
                results[category]["correct"] += 1

        metrics = {}
        for cat, r in results.items():
            metrics[cat] = {
                "accuracy": r["correct"] / r["total"] if r["total"] > 0 else 0,
                "total": r["total"]
            }
        total_correct = sum(r["correct"] for r in results.values())
        total_all = sum(r["total"] for r in results.values())
        metrics["overall"] = total_correct / total_all if total_all > 0 else 0
        return metrics

    def _check_correctness(self, pred: str, truth: str, category: str) -> bool:
        if category in ["simple_python", "multiple_python", "parallel_python"]:
            return self._match_function_call(pred, truth)
        return pred.strip().lower() == truth.strip().lower()
```

## GAIA 真实任务评估

```python
class GAIARunner:
    """GAIA 评估 Agent 解决真实世界问题的能力"""

    def evaluate(self, agent, dataset_path: str) -> dict:
        questions = self._load_dataset(dataset_path)
        results = {"Level 1": [], "Level 2": [], "Level 3": []}

        for q in questions:
            try:
                prediction = agent.run(q["question"])
                score = 1.0 if self._exact_match(prediction, q["ground_truth"]) else 0.0
            except Exception as e:
                prediction = f"ERROR: {e}"
                score = 0.0

            results[q["level"]].append({
                "question": q["question"][:100],
                "prediction": prediction[:200],
                "ground_truth": q["ground_truth"],
                "score": score
            })

        metrics = {}
        for level, items in results.items():
            if items:
                metrics[level] = {
                    "accuracy": sum(i["score"] for i in items) / len(items),
                    "total": len(items)
                }
        metrics["overall"] = {
            "accuracy": sum(m["accuracy"] * m["total"] for m in metrics.values()) /
                        sum(m["total"] for m in metrics.values())
        }
        return metrics

    def _exact_match(self, pred: str, truth: str) -> bool:
        """严格匹配——清理后比较"""
        import re
        def clean(s):
            s = s.strip().lower()
            s = re.sub(r'\s+', ' ', s)
            return s
        return clean(pred) == clean(truth)
```

## LLM Judge 多维度评估

```python
class LLMJudge:
    """用 LLM 作为评判者评估生成内容质量"""

    DIMENSIONS = {
        "正确性": {"weight": 0.35, "desc": "答案和推理是否准确无误"},
        "清晰度": {"weight": 0.25, "desc": "表述是否清晰连贯"},
        "难度匹配": {"weight": 0.20, "desc": "难度是否达标"},
        "完整性": {"weight": 0.20, "desc": "信息是否完整无遗漏"},
    }

    def __init__(self, model: str = "gpt-4o"):
        self.llm = HelloAgentsLLM(model=model)

    def evaluate(self, content: dict, context: str = "") -> dict:
        scores = {}
        for dim, config in self.DIMENSIONS.items():
            prompt = (
                f"评分维度: {dim} ({config['desc']})\n"
                f"评分范围: 1(很差)-5(优秀)\n\n"
                f"待评估内容:\n{json.dumps(content, ensure_ascii=False, indent=2)}\n\n"
                f"请回复 JSON: {{\"score\": <1-5>, \"reason\": \"<理由>\"}}"
            )
            response = self.llm.invoke([{"role": "user", "content": prompt}])
            try:
                result = json.loads(self._extract_json(response))
                scores[dim] = result.get("score", 0)
            except Exception:
                scores[dim] = 0

        weighted = sum(scores.get(d, 0) * c["weight"] for d, c in self.DIMENSIONS.items())
        return {"scores": scores, "weighted_score": weighted}

    def _extract_json(self, text: str) -> str:
        import re
        match = re.search(r'\{[^{}]*\}', text)
        return match.group(0) if match else "{}"
```

## Win Rate 对比评估

```python
class WinRateEvaluator:
    """A vs B 成对比较——评估生成质量是否达到参考水平"""

    def __init__(self, judge_model: str = "gpt-4o"):
        self.judge_llm = HelloAgentsLLM(model=judge_model)

    def compare(self, model_a_outputs: list, model_b_outputs: list,
                tasks: list, count: int = 100) -> dict:
        import random
        indices = random.sample(
            range(min(len(model_a_outputs), len(model_b_outputs))),
            min(count, len(model_a_outputs), len(model_b_outputs))
        )
        results = {"win": 0, "tie": 0, "loss": 0}
        for idx in indices:
            prompt = (
                f"比较两个回答:\n\n"
                f"A: {model_a_outputs[idx]}\n\n"
                f"B: {model_b_outputs[idx]}\n\n"
                f"只回复: A更好 / B更好 / 差不多"
            )
            verdict = self.judge_llm.invoke([{"role": "user", "content": prompt}])
            if "A更好" in verdict: results["win"] += 1
            elif "B更好" in verdict: results["loss"] += 1
            else: results["tie"] += 1

        total = len(indices)
        quality = (
            "✅ 达标" if 0.4 <= results["win"] / total <= 0.6
            else "⚠️ 需改进" if results["win"] / total < 0.4
            else "🌟 超参考"
        )
        return {
            "win_rate": results["win"] / total,
            "tie_rate": results["tie"] / total,
            "loss_rate": results["loss"] / total,
            "quality": quality
        }
```

## 综合评估报告

```python
def generate_report(bfcl: dict, gaia: dict, judge: dict, win_rate: dict) -> str:
    """生成综合评估报告"""
    return f"""# Agent 评估报告

## BFCL 函数调用
| 类别 | 准确率 | 样本 |
|------|--------|------|
{chr(10).join(f"| {c} | {m['accuracy']:.1%} | {m['total']} |" for c, m in bfcl.items() if c != 'overall')}
**总分: {bfcl.get('overall', {}).get('accuracy', 0):.1%}**

## GAIA 真实任务
{chr(10).join(f"- {l}: {m['accuracy']:.1%} ({m['total']}题)" for l, m in gaia.items() if l != 'overall')}

## LLM Judge
| 维度 | 得分 |
|------|------|
{chr(10).join(f"| {d} | {s:.1f}/5 |" for d, s in judge.get('scores', {}).items())}
**加权: {judge.get('weighted_score', 0):.1f}/5**

## Win Rate
- Win: {win_rate['win_rate']:.1%} | Tie: {win_rate['tie_rate']:.1%} | Loss: {win_rate['loss_rate']:.1%}
- 评估: {win_rate['quality']}
"""
```
