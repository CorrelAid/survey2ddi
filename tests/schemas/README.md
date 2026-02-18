# DDI-Codebook 2.5 XML Schema files

Used by `test_ddi_xml.py` to validate generated XML against the official schema.

**Source:** https://ddialliance.org/hubfs/Specification/DDI-Codebook/2.5/XMLSchema/

**Entry point:** `codebook.xsd` — this is the schema we validate against.

Everything else is a transitive dependency:
- `xml.xsd` — W3C XML namespace (xml:lang etc.)
- `dcterms.xsd`, `dc.xsd`, `dcmitype.xsd` — Dublin Core metadata
- `ddi-xhtml11*.xsd` + `XHTML/` — DDI's XHTML subset for rich text in elements
