# evolution.py
import random
from workflow import Workflow


def crossover(parents):
    """Combine operators from parent workflows"""
    new_ops = []
    for p in parents:
        new_ops.append(random.choice(p.operators))

    new_tags = list(set(tag for p in parents for tag in p.tags))
    return Workflow(new_ops, new_tags)


def mutate(workflow):
    """Simple mutation: change model size"""
    for op in workflow.operators:
        for node in op.nodes:
            if random.random() < 0.3:
                node.model = random.choice(["small", "medium", "large"])
