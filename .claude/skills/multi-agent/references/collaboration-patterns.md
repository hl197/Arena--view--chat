# 多 Agent 协作模式参考

## 1. Pipeline 模式（流水线）

```
Agent A → Agent B → Agent C
每个 Agent 的输出是下一个的输入
```

```python
class PipelineOrchestrator:
    """串行流水线——Agent 依次处理，结果沿链传递"""

    def __init__(self, agents: list, error_policy: str = "stop"):
        """
        agents: 按执行顺序排列的 Agent 列表
        error_policy: "stop"(遇错即停) | "skip"(跳过继续) | "fallback"(使用兜底值)
        """
        self.agents = agents
        self.error_policy = error_policy

    def execute(self, initial_input: str) -> dict:
        """执行流水线，返回每步的中间结果"""
        result = initial_input
        trace = []

        for i, agent in enumerate(self.agents):
            try:
                result = agent.run(result)
                trace.append({
                    "step": i + 1,
                    "agent": agent.name,
                    "status": "success",
                    "output_preview": result[:100]
                })
            except Exception as e:
                trace.append({
                    "step": i + 1,
                    "agent": agent.name,
                    "status": "error",
                    "error": str(e)
                })

                if self.error_policy == "stop":
                    break
                elif self.error_policy == "fallback":
                    result = f"[{agent.name} 执行失败，使用上一阶段结果]\n{result}"
                # "skip" → 继续用上一个 result

        return {"final_output": result, "trace": trace, "steps_completed": len(trace)}
```

## 2. Parallel 模式（并行探索）

```python
import asyncio

class ParallelOrchestrator:
    """并行编排——多 Agent 同时探索，结果汇总"""

    def __init__(self, agents: list, merge_mode: str = "concat"):
        """
        merge_mode:
          - "concat": 拼接所有结果
          - "voting": 投票选出最佳答案
          - "synthesize": 用合成 Agent 生成综合结果
        """
        self.agents = agents
        self.merge_mode = merge_mode

    async def execute(self, task: str) -> dict:
        results = await asyncio.gather(
            *[self._run_one(agent, task) for agent in self.agents],
            return_exceptions=True
        )

        # 分离成功和失败
        successes = []
        failures = []
        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                failures.append({"agent": agent.name, "error": str(result)})
            else:
                successes.append({"agent": agent.name, "output": result})

        # 合并
        if self.merge_mode == "voting":
            merged = self._voting_merge(successes, task)
        elif self.merge_mode == "synthesize":
            merged = self._synthesize_merge(successes, task)
        else:
            merged = self._concat_merge(successes)

        return {"merged": merged, "successes": len(successes),
                "failures": failures}

    async def _run_one(self, agent, task: str) -> str:
        return await asyncio.to_thread(agent.run, task)

    def _voting_merge(self, results: list, task: str) -> str:
        """让各 Agent 互相评审——选得分最高的"""
        # 简化版：用第一个结果作为"获胜者"
        if not results:
            return "所有 Agent 都失败了"
        return results[0]["output"]

    def _concat_merge(self, results: list) -> str:
        sections = []
        for r in results:
            sections.append(f"## {r['agent']}\n{r['output']}")
        return "\n\n---\n\n".join(sections)
```

## 3. Debate 模式（辩论验证）

```python
class DebateOrchestrator:
    """辩论模式——正反方辩论，裁判裁决"""

    def __init__(self, proposer, critic, judge, max_rounds=3):
        self.proposer = proposer    # 提出方案
        self.critic = critic        # 找出问题
        self.judge = judge          # 裁决
        self.max_rounds = max_rounds

    def debate(self, topic: str) -> dict:
        transcript = []

        # 正方提出方案
        proposal = self.proposer.run(
            f"针对「{topic}」提出最佳方案。要具体、可操作。"
        )
        transcript.append({"role": "PROPOSER", "content": proposal})

        for round_num in range(1, self.max_rounds + 1):
            # 反方批评
            critique = self.critic.run(
                f"请严格审查以下方案，找出逻辑漏洞、实施风险、遗漏的边界情况:\n\n{proposal}"
            )
            transcript.append({"role": "CRITIC", "content": critique})

            # 正方回应
            rebuttal = self.proposer.run(
                f"原始方案:\n{proposal}\n\n"
                f"批评意见:\n{critique}\n\n"
                f"请逐条回应批评。接受合理的、反驳不合理的。必要时修改方案。"
            )
            transcript.append({"role": "PROPOSER_REBUTTAL", "content": rebuttal})
            proposal = rebuttal

            # 裁判裁决
            verdict = self.judge.run(
                f"辩论记录:\n{json.dumps(transcript, ensure_ascii=False, indent=2)}\n\n"
                f"请裁决: 双方是否达成共识(consensus)？还是需要继续辩论(continue)？\n"
                f"如果达成共识，给出最终方案。"
            )
            transcript.append({"role": "JUDGE", "content": verdict})

            if "consensus" in verdict.lower():
                break

        return {"transcript": transcript, "rounds": round_num,
                "consensus_reached": "consensus" in verdict.lower()}
```

## 4. Hierarchical 模式（层级委派）

```python
class HierarchicalOrchestrator:
    """层级编排——Manager 分解任务、委派 Worker、汇总结果"""

    def __init__(self, manager, workers: dict):
        self.manager = manager        # 规划和分配
        self.workers = workers        # {"专家名": Agent}

    def execute(self, task: str) -> dict:
        # Step 1: Manager 制定执行计划
        plan = self._create_plan(task)

        # Step 2: 按优先级和依赖关系执行
        results = {}
        for item in sorted(plan, key=lambda x: x.get("priority", 99)):
            assigned = item.get("assigned_to", "")
            subtask = item.get("subtask", item.get("description", ""))

            worker = self.workers.get(assigned)
            if not worker:
                results[subtask] = f"⚠️ 无 '{assigned}' 专家，跳过"
                continue

            # 注入上下文
            context = item.get("context", "")
            depends_on = item.get("depends_on", [])
            dep_results = {d: results.get(d, "未完成") for d in depends_on}

            full_task = (
                f"任务: {subtask}\n"
                + (f"参考上下文: {context}\n" if context else "")
                + (f"依赖任务结果: {json.dumps(dep_results, ensure_ascii=False)}\n" if dep_results else "")
            )
            results[subtask] = worker.run(full_task)

        # Step 3: Manager 汇总
        summary = self.manager.run(
            f"原始任务: {task}\n\n"
            f"子任务执行结果:\n{json.dumps(results, ensure_ascii=False, indent=2)}\n\n"
            f"请整合所有子任务结果，生成最终报告。"
        )
        return {"plan": plan, "results": results, "summary": summary}

    def _create_plan(self, task: str) -> list[dict]:
        prompt = (
            f"任务: {task}\n\n"
            f"可用专家: {list(self.workers.keys())}\n\n"
            f"请将任务分解为子任务，并输出 JSON 格式的计划。\n"
            f'每项包含: subtask(子任务描述), assigned_to(专家名), '
            f'priority(优先级数字), depends_on(依赖的子任务描述列表), '
            f'context(需要传递给专家的上下文)'
        )
        response = self.manager.run(prompt)
        try:
            return json.loads(self._extract_json(response))
        except json.JSONDecodeError:
            return [{"subtask": task, "assigned_to": list(self.workers.keys())[0], "priority": 1}]

    def _extract_json(self, text: str) -> str:
        import re
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        return match.group(1) if match else text
```

## 协作模式选择决策树

```python
def select_collaboration_mode(task: str, available_agents: int) -> str:
    """根据任务特征自动选择协作模式"""
    task_lower = task.lower()

    # Debate 模式检测
    debate_keywords = ["评审", "审查", "辩论", "验证", "检查方案",
                       "review", "debate", "verify"]
    if any(kw in task_lower for kw in debate_keywords) and available_agents >= 3:
        return "debate"

    # Hierarchical 模式检测
    hierarchical_keywords = ["多个子任务", "分配", "委派", "团队",
                             "multi-task", "delegate", "orchestrate"]
    if any(kw in task_lower for kw in hierarchical_keywords) and available_agents >= 3:
        return "hierarchical"

    # Parallel 模式检测
    parallel_keywords = ["同时", "并行", "各自", "分别",
                         "parallel", "concurrent", "independently"]
    if any(kw in task_lower for kw in parallel_keywords) and available_agents >= 2:
        return "parallel"

    # Pipeline 模式检测
    pipeline_keywords = ["然后", "接着", "之后", "下一步",
                         "pipeline", "sequential", "chain"]
    if any(kw in task_lower for kw in pipeline_keywords) and available_agents >= 2:
        return "pipeline"

    # 默认单 Agent
    return "single"
```
