# main.py
import random

from workflow import InvokingNode, OperatorNode, Workflow
from evaluate import evaluate_workflow, global_call_count
from evolution import crossover, mutate
from selection import pareto_select

# ========== 配置参数 ==========
POP_INIT_SIZE = 15
POP_MAX_SIZE = 15
NUM_ROUNDS = 80
EVAL_REPEATS = 1
EXPLORATION_KEEP = 3
MAX_EVAL_PER_ROUND = 5

# ========== 定义 Operators ==========
def build_operators():
    return [
        OperatorNode("CoT-small", [InvokingNode("small", "Solve step by step", temperature=0.7)]),
        OperatorNode("CoT-medium", [InvokingNode("medium", "Solve step by step", temperature=0.7)]),
        OperatorNode("Debate", [
            InvokingNode("medium", "Propose answer", temperature=0.9),
            InvokingNode("medium", "Critique answer", temperature=0.9),
        ]),
        OperatorNode("SelfRefine", [
            InvokingNode("medium", "Generate solution", temperature=0.8),
            InvokingNode("medium", "Reflect and improve", temperature=0.8),
        ]),
        OperatorNode("Ensemble", [InvokingNode("large", "Solve carefully", temperature=0.7)]),
        OperatorNode("Checker", [InvokingNode("small", "Check format and constraints", temperature=0.2)])
    ]

OPS = build_operators()

# ========== 初始化 Workflow ==========
def random_workflow():
    k = random.choice([1, 2, 2, 3])
    ops = random.sample(OPS, k=k)
    tags_pool = ["easy", "medium", "hard", "math", "reasoning", "code", "format"]
    tags = random.sample(tags_pool, k=random.choice([1, 2, 3]))
    return Workflow(ops, tags=tags)

population = [random_workflow() for _ in range(POP_INIT_SIZE)]

# ========== 任务集 ==========
TASKS = [
    ("What is 7 + 15?", 0.2),
    ("Explain the difference between lists and dictionaries in Python.", 0.4),
    ("If x + y = 10 and x - y = 2, what is x?", 0.6),
    ("Prove that the square root of 2 is irrational.", 0.8),
    ("Write a recursive function in Python to compute Fibonacci numbers.", 0.9)
]

# ========== 路由匹配 ==========
def task_matches_workflow(task, wf):
    _, difficulty = task
    if wf.cost <= 2.0:
        return difficulty <= 0.4
    elif wf.cost <= 4.0:
        return 0.3 <= difficulty <= 0.7
    else:
        return difficulty >= 0.6

# ========== 稳定评估 ==========
def stable_evaluate(wf, task, repeats):
    total_cost = 0.0
    total_perf = 0.0
    for _ in range(repeats):
        evaluate_workflow(wf, task)
        total_cost += wf.cost
        total_perf += wf.performance
    wf.cost = total_cost / repeats
    wf.performance = total_perf / repeats

# ========== 演化选择 ==========
def select_with_exploration(pop):
    try:
        pareto = pareto_select(pop, max_size=POP_MAX_SIZE)
    except TypeError:
        pareto = pareto_select(pop)[:POP_MAX_SIZE]

    remain = [wf for wf in pop if wf not in pareto]
    random.shuffle(remain)
    pareto.extend(remain[:EXPLORATION_KEEP])
    pareto = pareto[:POP_MAX_SIZE]
    if len(pareto) < 2:
        pareto = (pareto * 2)[:2]
    return pareto

# ========== 输出结果 ==========
def summarize(pop):
    cheapest = min(pop, key=lambda w: w.cost)
    best = max(pop, key=lambda w: w.performance)
    try:
        front = pareto_select(pop, max_size=min(6, len(pop)))
    except TypeError:
        front = pareto_select(pop)[:6]
    print(f"  Cheapest: {cheapest}")
    print(f"  BestPerf: {best}")
    print("  ParetoFront:")
    for wf in front:
        print("   ", wf)

# ========== 主循环（符合 EvoFlow 演化流程） ==========
print("===== EvoFlow Local Simulation (FINAL STABLE) =====")

for r in range(NUM_ROUNDS):
    task = random.choice(TASKS)
    print(f"\n--- Round {r} | Task = {task[0]} (difficulty={task[1]}) ---")

    valid_wfs = [wf for wf in population if task_matches_workflow(task, wf)]
    valid_wfs = valid_wfs[:MAX_EVAL_PER_ROUND]
    print(f"→ {len(valid_wfs)} workflows matched this task.")

    for wf in valid_wfs:
        stable_evaluate(wf, task, EVAL_REPEATS)

    parents = random.sample(population, 2) if len(population) >= 2 else population * 2
    child = crossover(parents)
    mutate(child)

    # 始终评估 offspring 以获取 cost/perf，符合论文定义
    stable_evaluate(child, task, EVAL_REPEATS)
    population.append(child)

    for wf in population:
        if wf.cost == 0.0 and wf.performance == 0.0:
            stable_evaluate(wf, task, repeats=1)

    population = select_with_exploration(population)
    summarize(population)
    print(f"[Round {r} Done] PopSize={len(population)} | LLM Calls={global_call_count}\n")

print("\n===== Final Population =====")
summarize(population)