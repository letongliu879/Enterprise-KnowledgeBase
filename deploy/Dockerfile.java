# =============================================================================
# Enterprise KnowledgeBase — Java Service Dockerfile (TEMPLATE)
# =============================================================================
# Usage:
#   docker build -t ekb-<service> -f deploy/Dockerfile.java \
#     --build-arg SERVICE_DIR=services/<name> .
#
# Verified: NOT YET — template only. Services currently run via smoke script.
# =============================================================================

FROM maven:3.9-eclipse-temurin-17 AS build

ARG SERVICE_DIR
WORKDIR /build

# Copy the specific service pom + source
COPY ${SERVICE_DIR}/pom.xml ./pom.xml
COPY ${SERVICE_DIR}/src/ ./src/

RUN mvn package -DskipTests -q

FROM eclipse-temurin:17-jre

ARG SERVICE_DIR
WORKDIR /app

COPY --from=build /build/target/*.jar ./app.jar

EXPOSE 18181 18182

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
