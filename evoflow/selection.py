# selection.py

def dominates(a, b):
    return (
        a.performance >= b.performance and
        a.cost <= b.cost and
        (a.performance > b.performance or a.cost < b.cost)
    )


def pareto_select(population, max_size=5):
    pareto = []
    for wf in population:
        if not any(dominates(other, wf) for other in population):
            pareto.append(wf)

    return pareto[:max_size]
