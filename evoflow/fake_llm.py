# fake_llm.py
import random

MODEL_STRENGTH = {
    "small": 0.4,
    "medium": 0.7,
    "large": 0.9
}

MODEL_COST = {
    "small": 1.0,
    "medium": 2.0,
    "large": 4.0
}


def run_fake_llm(model, prompt):
    """Return True if answer is correct"""
    strength = MODEL_STRENGTH[model]
    return random.random() < strength
