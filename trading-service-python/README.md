# Trading Service Environment Variables
# Neon Database Configuration

DB_HOST=ep-rapid-term-ajfumxok-pooler.c-3.us-east-2.aws.neon.tech
DB_NAME=neondb
DB_USER=neondb_owner
DB_PASSWORD=npg_s0y6NUqwkSEB
DB_PORT=5432

# Database URL (for psycopg2)
DATABASE_URL=postgresql://neondb_owner:npg_s0y6NUqwkSEB@ep-rapid-term-ajfumxok-pooler.c-3.us-east-2.aws.neon.tech:5432/neondb?sslmode=require

# API Configuration
API_PORT=8001
API_HOST=0.0.0.0
DEBUG=False

# AI Service Configuration
AI_SERVICE_URL=http://localhost:8002

# Logging
LOG_LEVEL=INFO
