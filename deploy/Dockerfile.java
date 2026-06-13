# =============================================================================
# Enterprise KnowledgeBase — Java Service Dockerfile
# =============================================================================
# Build per service:
#   docker build -t ekb-access:latest -f deploy/Dockerfile.java \
#     --build-arg SERVICE_DIR=services/access .
# =============================================================================

FROM maven:3.9-eclipse-temurin-21 AS build

ARG SERVICE_DIR
WORKDIR /build

# Copy the specific service POM and source.
COPY ${SERVICE_DIR}/pom.xml ./pom.xml
COPY ${SERVICE_DIR}/src/ ./src/

# If the service references a parent POM or sibling modules, copy them too.
# (access and retrieval are currently standalone; adjust if build fails.)
RUN mvn package -DskipTests -q

FROM eclipse-temurin:21-jre

ARG SERVICE_DIR
WORKDIR /app

# Install curl for compose health checks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root runtime user.
RUN groupadd -r ekb && useradd -r -m -g ekb ekb

COPY --from=build /build/target/*.jar ./app.jar
RUN chown -R ekb:ekb /app
USER ekb

EXPOSE 18081 18082

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
