#!/usr/bin/env python3
"""One-off migration: turn the AOP-Wiki .rq example queries into .ttl example files.

Adapted from the WikiPathways migration (wikipathways/SPARQLQueries, commit 931c654).
Kept for the record of how the .ttl files were made; after the migration the .ttl
files are edited by hand (see AUTHORING.md) and this script is not run again.

For every .rq file it writes a .ttl file next to it, in the format checked by
Snorql-UI's tools/examples/snorql_examples.py:

- identifiers AOPQ001, AOPQ002, ... in folder order, then file name order;
- title, description and category from the comment header (the category of a file
  without one comes from its folder);
- the queries with parameters are rewritten by hand (PARAMETERISED below): every
  {{param}} placeholder becomes a variable bound in a VALUES block that holds the
  default, and a parameter whose blank value meant "all" has no default and
  `VALUES ?x { UNDEF }` (Snorql-UI 1.5);
- PREFIX lines are added for the prefixes the editor used to supply (NAMESPACES);
- created from the git history of the .rq file;
- prov:wasDerivedFrom the .rq file at the commit it was migrated from, and
  snorql:alias the old path, so old ?example=<path>.rq links still work;
- snorql:expect minResults 1 for the queries that return rows today (EMPTY_TODAY
  lists those that don't).

Usage, from the repository root:

    python scripts/migrate_rq_to_ttl.py [--check]
"""

import argparse
import pathlib
import re
import subprocess
import sys
import urllib.parse

from rdflib import Graph

REPO = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://aopwiki.rdf.bigcat-bioinformatics.org/.well-known/sparql-examples/"
TARGET = "https://aopwiki.rdf.bigcat-bioinformatics.org/sparql"
LICENSE = "https://www.gnu.org/licenses/gpl-3.0.html"
SOURCE_BASE = "https://github.com/marvinm2/AOP-Wiki-Queries/blob/"
MARVIN = "https://orcid.org/0000-0003-2230-0840"

FOLDER_CATEGORY = {
    "A. Metadata": ("Metadata", "Metadata"),
    "B. AOPs": ("AOPs", "AOPs"),
    "C. Key Events": ("KeyEvents", "Key Events"),
    "D. KERs": ("KERs", "KERs"),
    "E. Stressors": ("Stressors", "Stressors"),
    "F. Chemicals": ("Chemicals", "Chemicals"),
    "G. Data Export": ("DataExport", "Data Export"),
    "H. Federated": ("Federated", "Federated"),
}
FOLDER_KEYWORDS = {
    "A. Metadata": ["metadata"],
    "B. AOPs": ["AOP"],
    "C. Key Events": ["key event"],
    "D. KERs": ["key event relationship"],
    "E. Stressors": ["stressor"],
    "F. Chemicals": ["chemical"],
    "G. Data Export": ["export"],
    "H. Federated": ["federated"],
}

# The prefixes the editor declared for every query (AOP-Wiki-Snorql-UI config.js), plus
# skos and nci, which the endpoint knows but the editor did not list.
NAMESPACES = {
    "aop": "https://identifiers.org/aop/",
    "aop.events": "https://identifiers.org/aop.events/",
    "aop.relationships": "https://identifiers.org/aop.relationships/",
    "aop.stressor": "https://identifiers.org/aop.stressor/",
    "aopo": "http://aopkb.org/aop_ontology#",
    "cheminf": "http://semanticscience.org/resource/CHEMINF_",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "edam": "http://edamontology.org/",
    "fn": "http://www.w3.org/2005/xpath-functions#",
    "mmo": "http://purl.obolibrary.org/obo/MMO_",
    "ncbitaxon": "http://purl.bioontology.org/ontology/NCBITAXON/",
    "nci": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#",
    "pato": "http://purl.obolibrary.org/obo/PATO_",
    "pav": "http://purl.org/pav/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "void": "http://rdfs.org/ns/void#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

AOP_TEMPLATE = "https://identifiers.org/aop/{value}"
KE_TEMPLATE = "https://identifiers.org/aop.events/{value}"
TAXON_TEMPLATE = "http://purl.uniprot.org/taxonomy/{value}"


def P(name, label, *, variable=None, default=None, template=None, autocomplete=None,
      options=None, order=1):
    return dict(name=name, label=label, variable=variable or name, default=default,
                template=template, autocomplete=autocomplete, options=options, order=order)


# Queries with parameters, rewritten by hand: the new body and the parameters.
PARAMETERISED = {
    "A. Metadata/text-search.rq": ([P("search_term", "Search term", default="nanotube")], """
SELECT ?item ?name ?predicate ?text
WHERE {
  VALUES ?search_term { "nanotube" }
  ?item ?predicate ?text ;
    dc:title ?name .
  FILTER regex(?text, ?search_term, "i")
}
ORDER BY DESC(?item)
"""),
    "B. AOPs/get-ao-for-mie.rq": ([P("mie_id", "MIE", variable="MIEwebpage", default="18",
                                    template=KE_TEMPLATE, autocomplete="keyEvent")], """
SELECT ?MIEwebpage ?MolecularInitiatingEventName ?AOwebpage ?AdverseOutcomeName
WHERE {
  VALUES ?MIEwebpage { <https://identifiers.org/aop.events/18> }
  ?MIEwebpage dc:identifier ?MIELookup ;
    dc:title ?MolecularInitiatingEventName .
  ?AOPwebpage a aopo:AdverseOutcomePathway ;
    aopo:has_molecular_initiating_event ?MIELookup ;
    aopo:has_adverse_outcome ?AOwebpage .
  ?AOwebpage dc:title ?AdverseOutcomeName .
}
"""),
    "B. AOPs/get-aop-for-ao.rq": ([P("ao_id", "AO", variable="AO", default="1276",
                                   template=KE_TEMPLATE, autocomplete="keyEvent")], """
SELECT ?AOP ?AOPTitle
WHERE {
  VALUES ?AO { <https://identifiers.org/aop.events/1276> }
  ?AOP a aopo:AdverseOutcomePathway ;
    dc:title ?AOPTitle ;
    aopo:has_adverse_outcome ?AO .
}
"""),
    "B. AOPs/methods-for-aops.rq": ([P("aop_id", "AOP", variable="aop", default="12",
                                     template=AOP_TEMPLATE, autocomplete="aop")], """
SELECT DISTINCT ?aop ?ke
  (GROUP_CONCAT(DISTINCT ?speciesname; separator=" | ") AS ?speciesnames)
  ?method
WHERE {
  VALUES ?aop { <https://identifiers.org/aop/12> }
  ?aop aopo:has_key_event ?ke .
  ?ke ncbitaxon:131567 ?taxon .
  ?taxon a ncbitaxon:131567 ;
    dc:title ?speciesname .
  OPTIONAL { ?ke mmo:0000000 ?method . }
}
GROUP BY ?aop ?ke ?method
ORDER BY ASC(?aop)
"""),
    "C. Key Events/genes-for-aop-annotated.rq": ([P("aop_id", "AOP (blank = all)", variable="aop",
                                                  template=AOP_TEMPLATE, autocomplete="aop")], """
SELECT DISTINCT ?aop ?aoptitle ?ketitle ?objectname ?prot
WHERE {
  # Optional AOP: left blank, ?aop stays unbound and all AOPs are returned.
  VALUES ?aop { UNDEF }
  ?aop a aopo:AdverseOutcomePathway ;
    aopo:has_key_event ?ke ;
    dc:title ?aoptitle .
  ?ke pato:0001241 ?object ;
    dc:title ?ketitle ;
    rdfs:label ?keid .
  ?object dc:title ?objectname ;
    skos:exactMatch ?prot .
  ?prot a edam:data_1027 .
}
ORDER BY DESC(?aop)
"""),
    "C. Key Events/genes-for-aop-mapped.rq": ([
        P("aop_id", "AOP (blank = all)", variable="aop", template=AOP_TEMPLATE, autocomplete="aop"),
        P("method", "Detection method", default="any", order=2, options=[
            ("any", "Any detector"), ("regex", "Dictionary (incl. both)"), ("ner", "BERN2 NER (incl. both)"),
            ("both", "Both detectors"), ("regex_only", "Dictionary only"), ("ner_only", "BERN2 NER only")]),
    ], """
PREFIX p: <https://aopwiki.rdf.bigcat-bioinformatics.org/>

SELECT DISTINCT ?aop ?aoptitle ?ketitle ?HGNC ?id ?detectedBy
WHERE {
  # Optional AOP: left blank, ?aop stays unbound and all AOPs are returned.
  VALUES ?aop { UNDEF }
  VALUES ?method { "any" }
  ?aop a aopo:AdverseOutcomePathway ;
    dc:title ?aoptitle ;
    aopo:has_key_event ?ke .
  ?ke a aopo:KeyEvent ;
    edam:data_1025 ?object ;
    dc:title ?ketitle ;
    rdfs:label ?keid .
  ?object edam:data_2298 ?HGNC ;
    skos:exactMatch ?id .
  ?id a edam:data_1027 ;
    edam:data_1027 ?ncbi .
  # Detector provenance for this Key Event–gene link.
  OPTIONAL { ?ke p:geneDetectedByRegex ?object . BIND(1 AS ?byRegex) }
  OPTIONAL { ?ke p:geneDetectedByNER ?object . BIND(1 AS ?byNER) }
  BIND(IF(BOUND(?byRegex) && BOUND(?byNER), "both",
       IF(BOUND(?byRegex), "regex_only",
       IF(BOUND(?byNER), "ner_only", "unrecorded"))) AS ?detectedBy)
  # Detection method filter — "regex" and "ner" include links found by both detectors.
  FILTER(?method = "any" || ?method = ?detectedBy ||
    (?method = "regex" && BOUND(?byRegex)) ||
    (?method = "ner" && BOUND(?byNER)))
}
ORDER BY DESC(?aop)
"""),
    "C. Key Events/search-ke-by-level.rq": ([P("level", "Biological level", default="All", options=[
        (v, v) for v in ["All", "Molecular", "Cellular", "Tissue", "Organ", "Individual", "Population"]])], """
SELECT DISTINCT ?ke ?label ?bioLevel
WHERE {
  VALUES ?level { "All" }
  ?ke a aopo:KeyEvent ;
    dc:title ?label ;
    nci:C25664 ?bioLevel .
  # "All" returns every level.
  FILTER(?level = "All" || ?bioLevel = ?level)
}
ORDER BY ?bioLevel
"""),
    "D. KERs/list-kers-for-aop.rq": ([P("aop_id", "AOP", variable="aop", default="12",
                                      template=AOP_TEMPLATE, autocomplete="aop")], """
SELECT ?KER ?upstreamKE ?upstreamTitle ?downstreamKE ?downstreamTitle
WHERE {
  VALUES ?aop { <https://identifiers.org/aop/12> }
  ?aop aopo:has_key_event_relationship ?KER .
  ?KER aopo:has_upstream_key_event ?upstreamKE ;
       aopo:has_downstream_key_event ?downstreamKE .
  ?upstreamKE dc:title ?upstreamTitle .
  ?downstreamKE dc:title ?downstreamTitle .
}
ORDER BY ?upstreamKE
"""),
    "E. Stressors/stressors-for-ao-searched.rq": ([P(
        "ao_name", "Adverse outcome: pick one, or type part of a name", default="fibrosis",
        autocomplete="keyEvent")], """
SELECT ?AO ?AOname ?AOP ?MIETitle
  (CONCAT('"', GROUP_CONCAT(?StressorName; SEPARATOR='","'), '"') AS ?StressorNames)
  (CONCAT('"', GROUP_CONCAT(?ChemicalName; SEPARATOR='","'), '"') AS ?ChemicalNames)
WHERE {
  VALUES ?ao_name { "fibrosis" }
  ?AO a aopo:KeyEvent ;
    dc:identifier ?AOLookup ;
    dc:title ?AOname .
  ?AOP a aopo:AdverseOutcomePathway ;
    aopo:has_adverse_outcome ?AOLookup ;
    aopo:has_molecular_initiating_event ?MIE ;
    nci:C54571 ?Stressor .
  ?MIE dc:title ?MIETitle .
  ?Stressor dc:title ?StressorName .
  OPTIONAL {
    ?Stressor aopo:has_chemical_entity ?Chemical .
    ?Chemical dc:title ?ChemicalName .
  }
  # A picked Key Event gives its numeric id, matched exactly; any other text is a
  # case-insensitive substring of the adverse outcome name.
  FILTER(IF(regex(?ao_name, "^[0-9]+$"),
    STR(?AO) = CONCAT("https://identifiers.org/aop.events/", ?ao_name),
    regex(?AOname, ?ao_name, "i")))
}
ORDER BY DESC(?AO)
"""),
    "F. Chemicals/chemicals-for-aop.rq": ([P("aop_id", "AOP (blank = all)", variable="aop",
                                           template=AOP_TEMPLATE, autocomplete="aop")], """
SELECT ?aop ?aoptitle ?CASID ?chemicalname
WHERE {
  # Optional AOP: left blank, ?aop stays unbound and all AOPs are returned.
  VALUES ?aop { UNDEF }
  ?aop a aopo:AdverseOutcomePathway ;
    nci:C54571 ?Stressor ;
    dc:title ?aoptitle .
  ?Stressor aopo:has_chemical_entity ?Chemical .
  ?Chemical cheminf:000446 ?CASID ;
    dc:title ?chemicalname .
}
"""),
    "F. Chemicals/get-matching-ids-for-chems.rq": ([P(
        "chem_name", "Chemical: pick one, or type part of a name (blank = all)", autocomplete="chemical")], """
SELECT ?CASID ?ChemicalName ?MatchingIDs
WHERE {
  # Optional chemical: left blank, all chemicals are returned. A picked chemical gives its
  # CAS number, which is matched exactly; any other text is a case-insensitive name substring.
  VALUES ?chem_name { UNDEF }
  ?CAS a cheminf:000000 ;
    dc:title ?ChemicalName ;
    cheminf:000446 ?CASID ;
    skos:exactMatch ?MatchingIDs .
  FILTER(!BOUND(?chem_name) ||
    IF(regex(?chem_name, "^[0-9]+-[0-9]+-[0-9]$"),
       STR(?CASID) = ?chem_name,
       regex(?ChemicalName, ?chem_name, "i")))
}
"""),
    "H. Federated/aops-for-taxon.rq": ([P("taxon_id", "NCBI Taxon ID (40674 = Mammalia)", variable="taxonGroup",
                                         default="40674", template=TAXON_TEMPLATE)], """
SELECT ?aop ?aopTitle
  (GROUP_CONCAT(DISTINCT ?species; separator=" | ") AS ?mammalianSpecies)
WHERE {
  ?aop a aopo:AdverseOutcomePathway ;
       dc:title ?aopTitle ;
       ncbitaxon:131567 ?taxon2 .
  ?taxon2 a ncbitaxon:131567 ;
          dc:title ?species .
  BIND(STRAFTER(STR(?taxon2), "NCBITAXON/") AS ?tax2)
  SERVICE <https://sparql.uniprot.org/sparql/> {
    VALUES ?taxonGroup { <http://purl.uniprot.org/taxonomy/40674> }
    ?taxon rdfs:subClassOf* ?taxonGroup .
    BIND(STRAFTER(STR(?taxon), "taxonomy/") AS ?taxu)
  }
  FILTER(?tax2 = ?taxu)
}
GROUP BY ?aop ?aopTitle
ORDER BY ?aopTitle
"""),
    "H. Federated/applicable-to-taxon-tree.rq": ([P("taxon_id", "NCBI Taxon ID", variable="taxonGroup",
                                                   default="39107", template=TAXON_TEMPLATE)], """
SELECT DISTINCT ?tax
  (GROUP_CONCAT(DISTINCT ?name; separator=" | ") AS ?names)
  (COUNT(DISTINCT ?keker) AS ?n)
WHERE {
  ?keker ncbitaxon:131567 ?taxon2 .
  ?taxon2 a ncbitaxon:131567 ;
    dc:title ?name .
  BIND(SUBSTR(STR(?taxon2), 48) AS ?tax2)
  SERVICE <http://sparql.uniprot.org/sparql/> {
    VALUES ?taxonGroup { <http://purl.uniprot.org/taxonomy/39107> }
    ?taxon rdfs:subClassOf* ?taxonGroup .
  }
  BIND(SUBSTR(STR(?taxon), 34) AS ?tax)
  FILTER (?tax = ?tax2)
}
ORDER BY DESC(?n)
"""),
    "H. Federated/pathways-with-chem.rq": ([P("aop_id", "AOP (blank = all)", variable="LinkedAOPURI",
                                             template=AOP_TEMPLATE, autocomplete="aop")], """
PREFIX wp: <http://vocabularies.wikipathways.org/wp#>

SELECT ?ChemicalName ?ChEBI ?LinkedStressor
  (GROUP_CONCAT(DISTINCT ?LinkedAOP; separator=', ') AS ?AOPs)
  (STR(?PathwayID) AS ?Pathway_ID)
  (STR(?PathwayTitle) AS ?PathwayName)
  ?PathwayURI
WHERE {
  # Fetch human pathway metabolites from WikiPathways once, then join locally on the ChEBI
  # number. Joining the other way round sends one remote request per chemical and times out.
  SERVICE <https://sparql.wikipathways.org/sparql> {
    ?metabolite wp:bdbChEBI ?wpChebi ;
      dcterms:isPartOf ?PathwayURI .
    ?PathwayURI a wp:Pathway ;
      dcterms:identifier ?PathwayID ;
      dc:title ?PathwayTitle ;
      wp:organismName "Homo sapiens" .
  }
  BIND(STRAFTER(STR(?wpChebi), "CHEBI:") AS ?ChEBI)
  ?chebiRef cheminf:000407 ?ChEBI .
  ?cheLook a cheminf:000000 ;
    dc:title ?ChemicalName ;
    dcterms:isPartOf ?LinkedStressor ;
    skos:exactMatch ?chebiRef .
  # Optional AOP: left blank, ?LinkedAOPURI stays unbound and all AOPs are returned.
  VALUES ?LinkedAOPURI { UNDEF }
  ?LinkedStressor dcterms:isPartOf ?LinkedAOPURI .
  ?LinkedAOPURI a aopo:AdverseOutcomePathway ;
    rdfs:label ?LinkedAOP .
}
GROUP BY ?ChemicalName ?ChEBI ?LinkedStressor ?PathwayID ?PathwayTitle ?PathwayURI
ORDER BY ?ChemicalName ?PathwayTitle
"""),
}

# Queries that return no rows today (filled in from a live run, see --check); they get no
# snorql:expect, so the weekly live test does not fail on them.
EMPTY_TODAY = set()

HEADER_FIELD = re.compile(r"^#\s*(title|category|description|param):\s?(.*)$")

TTL_PREFIXES = """@prefix aopcat: <https://aopwiki.rdf.bigcat-bioinformatics.org/.well-known/sparql-examples/category/> .
@prefix aopq: <https://aopwiki.rdf.bigcat-bioinformatics.org/.well-known/sparql-examples/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix param: <https://w3id.org/snorql/param#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix snorql: <https://w3id.org/snorql/ns#> .
@prefix spex: <https://purl.expasy.org/sparql-examples/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True,
                          text=True).stdout


def mask(query):
    """The query with comments, strings and IRIs blanked out (same length)."""
    out, i, n = [], 0, len(query)
    while i < n:
        c = query[i]
        if c == "#":
            j = query.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif c in "\"'":
            j = i + 1
            while j < n and query[j] != c and query[j] != "\n":
                j += 2 if query[j] == "\\" else 1
            out.append(" " * (j + 1 - i)); i = j + 1
        elif c == "<" and re.match(r"<[^<>\s]*>", query[i:]):
            j = query.index(">", i)
            out.append(" " * (j + 1 - i)); i = j + 1
        else:
            out.append(c); i += 1
    return "".join(out)[:n]


def with_prefixes(body):
    code = mask(body)
    declared = set(re.findall(r"(?i)\bPREFIX\s+([\w.-]*):", code))
    used = set(re.findall(r"(?<![\w?$:.-])([A-Za-z][\w.-]*):(?=[\w])", code))
    missing = sorted(used - declared)
    unknown = [p for p in missing if p not in NAMESPACES]
    if unknown:
        raise SystemExit(f"unknown prefixes {unknown}")
    lines = [f"PREFIX {p}: <{NAMESPACES[p]}>" for p in missing]
    body = body.strip("\n")
    if not lines:
        return body
    return "\n".join(lines) + ("\n" if body.upper().startswith("PREFIX") else "\n\n") + body


def parse_rq(path):
    lines = path.read_text(encoding="utf-8").split("\n")
    fields, n, last = {"param": []}, 0, None
    while n < len(lines) and lines[n].startswith("#"):
        m = HEADER_FIELD.match(lines[n])
        if m:
            last = m.group(1)
            if last == "param":
                fields["param"].append(m.group(2).strip())
            else:
                fields[last] = m.group(2).strip()
        elif last == "description" and lines[n].startswith("#  "):
            fields["description"] += " " + lines[n][1:].strip()
        n += 1
    fields["body"] = "\n".join(lines[n:]).strip("\n") + "\n"
    return fields


def ttl_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ttl_long_string(text):
    text = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    if text.endswith('"'):
        text = text[:-1] + '\\"'
    return '"""' + text + '"""'


def param_ttl(p):
    lines = [f"    sh:parameter [ a sh:Parameter ; sh:path param:{p['name']} ;"]
    if p["variable"] != p["name"]:
        lines.append(f"        snorql:variable {ttl_string(p['variable'])} ;")
    lines.append(f"        sh:name {ttl_string(p['label'])} ; sh:order {p['order']} ;")
    if p["default"] is not None:
        lines.append(f"        sh:defaultValue {ttl_string(p['default'])} ;")
    if p["template"]:
        lines.append(f"        sh:nodeKind sh:IRI ; snorql:valueTemplate {ttl_string(p['template'])} ;")
    else:
        lines.append("        sh:datatype xsd:string ;")
    if p["autocomplete"]:
        lines.append(f"        snorql:autocomplete {ttl_string(p['autocomplete'])} ;")
    for i, (value, label) in enumerate(p["options"] or [], 1):
        lines.append(f"        snorql:option [ rdf:value {ttl_string(value)} ; rdfs:label {ttl_string(label)} ; "
                     f"sh:order {i} ] ;")
    lines[-1] = lines[-1].rstrip(" ;") + " ] ;"
    return lines


def created(rel):
    dates = git("log", "--format=%as", "--", rel).split()
    return dates[-1]


def render(ident, rel, rq, commit):
    folder = rel.split("/")[0]
    concept, label = FOLDER_CATEGORY[folder]
    if rq.get("category") and rq["category"] != label:
        raise SystemExit(f"{rel}: category {rq['category']!r} does not match its folder")
    if rel in PARAMETERISED:
        params, body = PARAMETERISED[rel]
        names = sorted(re.findall(r"\{\{\s*(\w+)", rq["body"]))
        if sorted({p["name"] for p in params}) != sorted(set(names)):
            raise SystemExit(f"{rel}: parameters {names} do not match the rewrite")
    else:
        if "{{" in rq["body"]:
            raise SystemExit(f"{rel} has placeholders but no rewrite")
        params, body = [], rq["body"]
    query = with_prefixes(body)
    services = sorted(set(re.findall(r"(?i)\bSERVICE\s+(?:SILENT\s+)?<([^>]+)>", query)))
    out = [TTL_PREFIXES, f"aopq:{ident} a sh:SPARQLExecutable, sh:SPARQLSelectExecutable ;",
           f'    dcterms:identifier "{ident}" ;',
           f"    rdfs:label {ttl_string(rq['title'])}@en ;",
           f"    rdfs:comment {ttl_string(rq['description'])}@en ;",
           '    schema:version "1.0.0" ;',
           f'    dcterms:created "{created(rel)}"^^xsd:date ;',
           f"    dcterms:creator <{MARVIN}> ;",
           f"    dcterms:license <{LICENSE}> ;",
           f"    dcterms:subject aopcat:{concept} ;",
           "    schema:keywords " + ", ".join(ttl_string(k) for k in FOLDER_KEYWORDS[folder]) + " ;",
           f"    schema:target <{TARGET}> ;"]
    for s in services:
        out.append(f"    spex:federatesWith <{s}> ;")
    out.append(f"    snorql:alias {ttl_string(rel)} ;")
    out.append(f"    prov:wasDerivedFrom <{SOURCE_BASE}{commit}/{urllib.parse.quote(rel)}> ;")
    if ident not in EMPTY_TODAY:
        out.append("    snorql:expect [ snorql:minResults 1 ] ;")
    for p in params:
        out += param_ttl(p)
    out.append(f"    sh:select {ttl_long_string(query)} .")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="parse every result, write nothing")
    args = ap.parse_args()
    commit = git("rev-parse", "HEAD").strip()
    files = sorted(p.relative_to(REPO).as_posix() for p in REPO.glob("*/*.rq"))
    for n, rel in enumerate(files, 1):
        ident = f"AOPQ{n:03d}"
        text = render(ident, rel, parse_rq(REPO / rel), commit)
        Graph().parse(data=text, format="turtle")
        if not args.check:
            (REPO / rel).with_suffix(".ttl").write_text(text, encoding="utf-8")
        print(ident, rel)
    unused = set(PARAMETERISED) - set(files)
    if unused:
        raise SystemExit(f"rewrites for missing files: {sorted(unused)}")


if __name__ == "__main__":
    sys.exit(main())
