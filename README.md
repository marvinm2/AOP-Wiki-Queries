# AOP-Wiki SPARQL Queries

SPARQL query examples for the [AOP-Wiki RDF Explorer](https://github.com/marvinm2/AOP-Wiki-Snorql-UI).

## Structure

Queries are organized into lettered category folders (A-H). Each `.rq` file includes comment headers (`# title:`, `# description:`, `# category:`) parsed by the Snorql-UI examples panel.

## Parameterized Queries

Some queries use `# param: name|type|default|label` headers to define input parameters. These generate form fields in the UI and use `{{placeholder}}` syntax for value substitution.

## Categories

- **A. Metadata** -- Dataset statistics and counts
- **B. AOPs** -- Adverse Outcome Pathway queries
- **C. Key Events** -- Key Event and gene/protein annotation queries
- **D. KERs** -- Key Event Relationship queries (placeholder)
- **E. Stressors** -- Stressor-related queries
- **F. Chemicals** -- Chemical entity queries
- **G. Data Export** -- Full data dump queries
- **H. Federated** -- Cross-endpoint federated queries
