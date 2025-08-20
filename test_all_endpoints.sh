#!/bin/bash
TOKEN="eyJhbGciOiJIUzI1NiIsImtpZCI6IktoRUU4WWpLaWEzLzhZTGciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3ZrYnV4ZW1rcHJvcnF4bXp6a3V1LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI5OWIxMDAxYi02OWEwLTRkNzUtOTczMC0zMTc3YmE0MmM2NDIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU1NjkxMzcyLCJpYXQiOjE3NTU2ODc3NzIsImVtYWlsIjoiY2xpZW50QGFuYWx5dGljc2ZvbGxvd2luZy5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJBbmFseXRpY3MgRm9sbG93aW5nIENsaWVudCJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzU1Njg3NzcyfV0sInNlc3Npb25faWQiOiIzOGFhNTY3Ny1jYzM3LTQyNjItYWFmYy1jMTk1NGNjYWIwNDAiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.ITsZtZ8n1Nv7j6BRc7MxbEzI2LeEWeFDjvRmYbynab8"

echo "=== 1. POSTS ENDPOINT ==="
curl -s "http://localhost:8000/api/v1/instagram/profile/latifalshamsi/posts?limit=5" \
  -H "Authorization: Bearer $TOKEN" | head -50

echo -e "\n\n=== 2. AI STATUS ENDPOINT ==="
curl -s "http://localhost:8000/api/v1/ai/status/profile/latifalshamsi" \
  -H "Authorization: Bearer $TOKEN"

echo -e "\n\n=== 3. MAIN PROFILE ENDPOINT ==="
curl -s "http://localhost:8000/api/v1/instagram/profile/latifalshamsi?detailed=true" \
  -H "Authorization: Bearer $TOKEN" | head -100

echo -e "\n\n=== 4. MINIMAL PROFILE ENDPOINT ==="
curl -s "http://localhost:8000/api/v1/instagram/profile/latifalshamsi/minimal" \
  -H "Authorization: Bearer $TOKEN"