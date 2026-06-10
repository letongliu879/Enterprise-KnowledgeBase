@echo off
cd /d "E:\AI\My-Project\Enterprise KnowledgeBase\services\access"
set DATABASE_URL=jdbc:postgresql://127.0.0.1:5432/rag_flow
set DATABASE_USERNAME=rag_flow
set DATABASE_PASSWORD=infini_rag_flow
"E:\AI\My-Project\Enterprise KnowledgeBase\tools\apache-maven-3.9.16\bin\mvn.cmd" spring-boot:run -DskipTests > target\access.log 2>&1
