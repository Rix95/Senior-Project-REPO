from neo4j_connection import get_neo4j_driver

schema_statements = [
    "CREATE CONSTRAINT UniqueVulnerabilityId FOR (v:Vulnerability) REQUIRE v.id IS UNIQUE;",
    "CREATE CONSTRAINT UniquePackagePurl FOR (p:Package) REQUIRE p.purl IS UNIQUE;",

    "CREATE INDEX VulnerabilityModifiedIndex FOR (v:Vulnerability) ON (v.modified);",
    "CREATE INDEX VulnerabilityPublishedIndex FOR (v:Vulnerability) ON (v.published);",
    "CREATE INDEX PackageEcosystemIndex FOR (p:Package) ON (p.ecosystem);",
    "CREATE INDEX PackageNameIndex FOR (p:Package) ON (p.name);",
    "CREATE INDEX AliasValueIndex FOR (a:Alias) ON (a.value);",
    "CREATE INDEX SeverityTypeIndex FOR (s:Severity) ON (s.type);",
    "CREATE INDEX VersionValueIndex FOR (ver:Version) ON (ver.value);",
    "CREATE INDEX RangeTypeIndex FOR (r:Range) ON (r.type);",
    "CREATE INDEX EventIntroducedIndex FOR (e:Event) ON (e.introduced);",
    "CREATE INDEX ReferenceTypeIndex FOR (ref:Reference) ON (ref.type);",
    "CREATE INDEX CreditNameIndex FOR (c:Credit) ON (c.name);",
    "CREATE INDEX EcosystemSpecificKeyIndex FOR (es:EcosystemSpecific) ON (es.key);",
    "CREATE INDEX PackageDatabaseSpecificKeyIndex FOR (pds:PackageDatabaseSpecific) ON (pds.key);"
]

def create_schema():
    driver = get_neo4j_driver()

    if driver is None:
        print("Failed to get neo4j driver.")
        return
    
    with driver.session() as session:
        for statement in schema_statements:
            try:
                session.run(statement)
                print(f"Successfully created: {statement.split()[2]}")  # Prints the created constraint/index name
            except Exception as e:
                print(f"Error creating schema: {e}")

if __name__ == "__main__":
    create_schema()