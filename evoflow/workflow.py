# workflow.py

class InvokingNode:
    def __init__(self, model, prompt, temperature=0.7):
        self.model = model
        self.prompt = prompt
        self.temperature = temperature


class OperatorNode:
    def __init__(self, name, nodes):
        self.name = name            # e.g. "CoT", "Debate"
        self.nodes = nodes          # list of InvokingNode


class Workflow:
    def __init__(self, operators, tags):
        self.operators = operators  # list of OperatorNode
        self.tags = tags            # list of strings

        self.cost = 0.0
        self.performance = 0.0

    def __repr__(self):
        return f"Workflow(tags={self.tags}, cost={self.cost:.2f}, perf={self.performance:.2f})"
