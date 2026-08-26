#!/bin/sh
set -eu
BASE="http://host.docker.internal:3000"
echo "=== PATH PROBES ==="
for p in \
  /api-docs/swagger.yaml \
  /api-docs \
  /rest \
  /rest/products/search \
  /api/Challenges \
  /api/Users \
  /api/Feedbacks \
  /api/Quantitys \
  /api/Cards \
  /api/Complaints \
  /api/Recycles \
  /api/SecurityQuestions \
  /api/SecurityAnswers \
  /api/Addresss \
  /api/DeliveryMethods \
  /api/PrivacyRequests \
  /metrics \
  /ftp \
  /encryptionkeys \
  /redirect \
  /socket.io \
  /snippets \
  /video \
  /assets/public
do
  meta=$(curl -s -o /tmp/hs_body -w "%{http_code}:%{size_download}:%{content_type}" "$BASE$p" || echo "000:0:err")
  echo "$meta $p"
done
echo "=== SWAGGER PATHS (first 150 lines) ==="
curl -s "$BASE/api-docs/swagger.yaml" | head -n 150
echo "=== METRICS (first 50 lines) ==="
curl -s "$BASE/metrics" | head -n 50
