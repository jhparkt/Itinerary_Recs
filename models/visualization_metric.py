import pickle
import matplotlib.pyplot as plt

with open('rule_based_metrics.pkl', 'rb') as f:
    eval_metrics_rule_based = pickle.load(f)
with open('llama_metrics.pkl', 'rb') as f:
    eval_metrics_llama = pickle.load(f)

llama_total_time, llama_diversity, llama_coverage = eval_metrics_llama[2], eval_metrics_llama[3], eval_metrics_llama[4]
rule_total_time, rule_diversity, rule_coverage = eval_metrics_rule_based[2], eval_metrics_rule_based[3], eval_metrics_rule_based[4]

methods = ["LLAMA", "Rule-Based"]
total_times = [llama_total_time, rule_total_time]
diversity_scores = [llama_diversity, rule_diversity]
pref_coverages = [llama_coverage, rule_coverage]  # bubble size

# Bubble Plot
plt.figure(figsize=(8, 6))
plt.scatter(total_times, diversity_scores, s=[c * 800 for c in pref_coverages], alpha=0.6, c=["#1f77b4", "#ff7f0e"])

for i, method in enumerate(methods):
    plt.text(total_times[i] + 0.5, diversity_scores[i] + 0.01, f"{method}\nCoverage={pref_coverages[i]:.2f}", fontsize=10)

plt.title("Comparison: Total Time vs POI Diversity\n(Bubble Size = Preference Coverage)")
plt.xlabel("Total Time (minutes)")
plt.ylabel("POI Diversity Score")
plt.ylim(0, 1)
plt.grid(True, linestyle='--', alpha=0.4)
plt.savefig("comparison_total_time_vs_poi_diversity.png")