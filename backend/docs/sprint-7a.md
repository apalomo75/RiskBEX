# Sprint 7A — Product identity and navigation

The five primary destinations are Overview, Performance, Investment Simulator,
Risk Monitor, and Research & Methodology. Risk Monitor contains Market Risk and
History & Decision Explorer. Research retains Models, Tail Risk, original TFM
research, MAIN/ROBUST comparisons, and Technical Details. Legacy view query
parameters still open their corresponding new destination.

Overview and Performance share strategy explanations and the validated
`/backtesting/comparison` publication. Overview shows all four strategies net of
modelled costs; Performance retains gross/net controls, growth, drawdowns,
exposures, metrics and turnover. Signed metric differences describe each adaptive
strategy against Buy & Hold and both ML strategies against Regime-Based. No
strategy is presumed superior. Publication identifiers, model provenance,
exposure mapping and return conventions remain available in Technical Details.
The Investment Simulator is a v1 preview without simulation controls or results.

## Dark theme

Local Streamlit is 1.56.0; the existing Docker lock specifies 1.67.0. Identical
`.streamlit/config.toml` files support launch from the repository root and backend;
the dashboard Dockerfile includes the backend configuration. Only `[theme]` is
specified, with a dark base and 17px body font. Streamlit's supported single-theme
configuration locks appearance without CSS manipulation of native settings:
[official appearance toggle rules](https://github.com/streamlit/streamlit/blob/develop/lib/streamlit/.agents/skills/developing-with-streamlit/references/theme.md#appearance-toggle-rules).
No light/dark variants or native user theme option are enabled by this project.
CLI/environment overrides or launching from another working directory can bypass
project configuration. Restart Streamlit after updating configuration.

## Validation and limits

23 distinct focused unittest checks passed across dashboard UI, strategy
performance, Decision Explorer and operational API modules. Two outdated UI
assertions initially failed and passed after adapting them to the new structure.
The updated performance interpretation test also passed after its final change.
Runtime theme serialization confirms DARK, configured colors and 17px text.
`git diff --check` passed. Pytest was unavailable; unittest ran without installing
packages. No training, downloads, deployment, scheduler activation or commits.

Browser visual checks at mobile/desktop sizes and the Docker runtime remain
unverified. Existing Streamlit `use_container_width` deprecation warnings remain.
The simulator engine and interactivity belong to subsequent v1 sprints.
