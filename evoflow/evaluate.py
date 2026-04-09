# === evaluate.py ===（确保调用真实 LLM + 成本估计 + 调用耗时）
import random
import time
from real_llm import run_qwen_llm
from fake_llm import MODEL_COST  # 用于成本估计（静态表）

global_call_count = 0

def evaluate_workflow(workflow, task):
    global global_call_count
    task_prompt, difficulty = task

    total_score = 0.0
    total = 0
    cost = 0.0

    for op in workflow.operators:
        for node in op.nodes:
            total += 1
            cost += MODEL_COST[node.model]

            try:
                print(f"[Eval]  Calling LLM ({node.model}) with prompt: {task_prompt[:30]}...")
                start_time = time.time()
                answer = run_qwen_llm(
                    node.model,
                    task_prompt,
                    temperature=node.temperature
                )
                duration = time.time() - start_time
                print(f"[Eval]  Duration: {duration:.2f}s")

                global_call_count += 1

                if not answer or answer.strip().lower() == "error":
                    print("[Eval]  Skipped empty or failed answer")
                    continue

                length_score = min(len(answer) / 200.0, 1.0)
                keyword_bonus = 0.0
                for kw in task_prompt.lower().split():
                    if kw in answer.lower():
                        keyword_bonus += 0.1

                score = min(length_score + keyword_bonus, 1.0)
                total_score += score

            except Exception as e:
                print("LLM error:", e)
                continue

    workflow.performance = total_score / max(total, 1)
    workflow.cost = cost
    workflow.performance += 0.01 * random.random()

