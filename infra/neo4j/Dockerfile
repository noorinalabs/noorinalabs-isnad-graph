# Custom Neo4j image with GDS plugin pre-installed.
# The GDS plugin requires downloading from graphdatascience.ninja at startup,
# which fails when the container is on an internal-only Docker network.
# Pre-installing the JAR into /var/lib/neo4j/products/ lets the entrypoint
# detect it locally and skip the download.
#
# When upgrading Neo4j, check the compatible GDS version at:
#   https://graphdatascience.ninja/versions.json

ARG NEO4J_VERSION=5.26.23-community
FROM neo4j:${NEO4J_VERSION}

ARG GDS_VERSION=2.13.8
ARG GDS_JAR_URL=https://graphdatascience.ninja/neo4j-graph-data-science-${GDS_VERSION}.jar

RUN wget -q --timeout=120 -O \
    /var/lib/neo4j/products/neo4j-graph-data-science-${GDS_VERSION}.jar \
    "${GDS_JAR_URL}"
