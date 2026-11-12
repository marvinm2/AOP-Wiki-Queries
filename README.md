# AOP-Wiki SPARQL Queries

Example SPARQL queries for the [AOP-Wiki RDF SPARQL editor](https://aopwiki.rdf.bigcat-bioinformatics.org/)
([AOP-Wiki-Snorql-UI](https://github.com/marvinm2/AOP-Wiki-Snorql-UI)). They help people explore
the AOP-Wiki RDF and start their own queries.

Each example is a Turtle file with the query and its metadata (title, description, version,
creator, category, parameters), in the format of
[SIB's sparql-examples](https://github.com/sib-swiss/sparql-examples). Every example has a
permanent identifier and IRI, for example
[`AOPQ012`](https://aopwiki.rdf.bigcat-bioinformatics.org/?example=AOPQ012) is
`https://aopwiki.rdf.bigcat-bioinformatics.org/.well-known/sparql-examples/AOPQ012`. Files can be
moved and renamed without breaking links.

- [AUTHORING.md](AUTHORING.md): how to write or change an example, and how versions work.
- `categories.ttl`: the categories that make up the editor's tree (Metadata, AOPs, Key Events,
  Key Event Relationships, Stressors, Chemicals, Data Export, Federated).
- `contributors.ttl`: names of creators and contributors.
- `collection.ttl`: the collection itself.

On every push to `main`, CI publishes the `examples-index` branch, which the editor reads; it
also holds every past version of every example and plain `.rq` copies. Once a week CI runs every
example against the endpoint.

The examples used to be `.rq` files with a comment header; the last commit with them is
`23d5204`. `scripts/migrate_rq_to_ttl.py` converted them and `scripts/compare_live.py` checked
that each `.ttl` query returns what its `.rq` returned (both scripts need that commit checked
out). Old links to an `.rq` path still open the right example, and the `rq/` folder of the
`examples-index` branch has generated `.rq` copies for tools that read that format.

## License

[GPLv3](LICENSE)
