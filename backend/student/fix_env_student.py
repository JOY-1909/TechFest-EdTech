content = """MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=yuva_setu
SECRET_KEY=your-secret-key-here-change-in-production
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=test@example.com
SMTP_PASSWORD=test-password
SMTP_FROM=test@example.com
SMTP_FROM_NAME=Yuva Setu
GOOGLE_CLIENT_ID=placeholder-google-client-id
GOOGLE_CLIENT_SECRET=placeholder-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
EMPLOYER_MONGODB_URL=mongodb://localhost:27017
EMPLOYER_DATABASE_NAME=yuvasetu
"""
with open('.env', 'w', encoding='utf-8') as f:
    f.write(content)
print("Rewrote student .env with utf-8 encoding (no BOM)")
