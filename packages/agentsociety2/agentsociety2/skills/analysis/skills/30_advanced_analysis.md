---
name: advanced_analysis
priority: 30
description: Advanced statistical, network, temporal, inequality, NLP, and synthesis methodologies.
---

# Advanced Analytical Methodologies

To elevate the analysis from simple observation to rigorous scientific inquiry, apply these methodologies where data permits.

## 1. Statistical Rigor & Hypothesis Testing
When comparing groups (e.g., Control vs. Experiment, or different agent types), visual difference is not enough.
- **Action**: Use `scipy.stats` to perform hypothesis testing.
  - For continuous variables (normal dist): **T-test** (`scipy.stats.ttest_ind`) or **ANOVA** (`scipy.stats.f_oneway`).
  - For non-normal/ordinal data: **Mann-Whitney U** (`scipy.stats.mannwhitneyu`) or **Kruskal-Wallis** (`scipy.stats.kruskal`).
  - For categorical data: **Chi-Square** test (`scipy.stats.chi2_contingency`).
  - For regression/correlation: **OLS Regression** via `statsmodels.api` or `scipy.stats.linregress`.
- **Reporting**: MUST report **p-values** and **effect sizes** (e.g., Cohen's d) in the text. State significance explicitly (e.g., "p < 0.05 indicates a significant difference").

```python
from scipy import stats
# Example: T-test between two groups
group1 = df[df['group'] == 'A']['value']
group2 = df[df['group'] == 'B']['value']
t_stat, p_value = stats.ttest_ind(group1, group2)
print(f"T-statistic: {t_stat:.3f}, P-value: {p_value:.4f}")
```

## 2. Social Network Analysis (SNA)
If interaction logs are available, treat the society as a graph.
- **Construction**: Build a graph `G` where nodes are agents and edges represent interactions (messages, trades, etc.).
- **Metrics to Calculate**:
  - **Degree Centrality**: Who are the influencers?
  - **Clustering Coefficient**: Are echo chambers forming?
  - **Path Length**: How fast can information spread?
  - **Community Detection**: Use Louvain or Leiden algorithms to find subgroups.
- **Visualization**: Plot the network using `networkx` with `matplotlib`, coloring nodes by agent state/opinion.

```python
import networkx as nx
G = nx.from_pandas_edgelist(interactions, 'source', 'target')
centrality = nx.degree_centrality(G)
nx.draw(G, node_size=[v*1000 for v in centrality.values()])
```

## 3. Temporal Dynamics & Convergence
Simulation is a process, not just a final state. Analyze the *trajectory*.
- **Convergence Check**: Do specific metrics (e.g., avg opinion) stabilize over `step`? Calculate the standard deviation of the last N steps to confirm stability.
- **Phase Transitions**: Look for sudden spikes or drops (tipping points) in time-series data using `np.gradient`.
- **Visualization**: Line charts with error bands (confidence intervals) over time.

## 4. Inequality & Distribution Analysis
Averages hide inequality.
- **Metrics**:
  - **Gini Coefficient**: For wealth or resource distribution.
  - **Entropy / Herfindahl Index**: For diversity of opinions or topics.
  - **Polarization Index**: For opinion dynamics (are agents clustering at extremes?).
- **Visualization**: Lorenz Curve, KDE plots (distributions), or Box-plots to show variance.

```python
import seaborn as sns
# Distribution comparison
sns.kdeplot(data=df, x='value', hue='group', fill=True)
plt.title('Distribution by Group')
```

## 5. Text & Sentiment Mining (NLP)
If textual interaction content is relevant:
- **Keyword Extraction**: Use TF-IDF to identify important terms.
- **Sentiment Analysis**: Track how average sentiment changes over time.
- **Correlation**: Does sentiment correlate with decision outcomes?

## 6. Synthesis & Comparative Analysis (Cross-Experiment)
When synthesizing results across multiple experiments:
- **Parameter Sensitivity**: Plot outcome metrics vs. parameter values.
- **Robustness Check**: Do findings hold across different seeds or variations?
- **Meta-Analysis**: If multiple runs exist, aggregate their effect sizes.

## 7. Causal Inference
If observing a strong correlation, attempt to check causality:
- Compare the "Intervention" group against "Control" on the perturbed variable.
- Use `statsmodels` for regression with controls.
