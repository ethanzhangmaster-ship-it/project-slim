import sys
sys.path.insert(0, 'src')

from market_ops.experiment_intelligence.experiment_selector import ExperimentSelector
from market_ops.experiment_intelligence.experiment_planner import ExperimentPlanner

# Select
selector = ExperimentSelector()
candidates = selector.select('output/creative_evolution/top_mutations.json', top_n=20)
print(f'Selected: {len(candidates)} candidates')

# Summary
summary = selector.get_selection_summary(candidates)
print(f'By type: {summary["by_mutation_type"]}')
print(f'By archetype: {summary["by_archetype"]}')
print(f'Avg score: {summary["avg_score"]}')

# Plan
planner = ExperimentPlanner()
plans = planner.create_plans(candidates, baseline_path='output/creative_learning/actual_performance.json')
print(f'Plans: {len(plans)}')

# AC2 check
print(f'All have hypothesis: {all(p.hypothesis for p in plans)}')
print(f'All have control: {all(p.control for p in plans)}')
print(f'All have variant: {all(p.variant for p in plans)}')
print(f'All have metrics: {all(p.metrics for p in plans)}')
print(f'All have budget: {all(p.budget > 0 for p in plans)}')
print(f'All have duration: {all(p.duration_days > 0 for p in plans)}')

# Show first plan
p0 = plans[0]
print(f'\nFirst plan:')
print(f'  hypothesis: {p0.hypothesis}')
print(f'  control: {p0.control}')
print(f'  variant: {p0.variant}')
print(f'  budget: {p0.budget}')
print(f'  daily_budget: {p0.daily_budget}')
print(f'  duration: {p0.duration_days}d')

# Plan summary
ps = planner.get_plan_summary(plans)
print(f'\nPlan summary:')
print(f'  total_budget: {ps["total_budget"]}')
print(f'  by_mutation_type: {ps["by_mutation_type"]}')