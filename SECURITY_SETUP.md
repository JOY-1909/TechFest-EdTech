# Security Setup Guide

## ⚠️ CRITICAL: Credentials have been secured

This repository previously contained exposed API keys and credentials. All sensitive data has been moved to environment variables and removed from version control.

## 🔧 Setup Instructions

### 1. Environment Variables Setup

Each component now requires a `.env` file. Copy the `.env.example` files and fill in your actual credentials:

```bash
# Frontend components
cp frontend/student/.env.example frontend/student/.env
cp frontend/employer/.env.example frontend/employer/.env
cp frontend/admin/.env.example frontend/admin/.env

# Backend components
cp backend/student/.env.example backend/student/.env
cp backend/employer-admin/.env.example backend/employer-admin/.env

# Job Recommendation Engine
cp Job-Recommendation/NLP-Job-Recommendation-main/.env.example Job-Recommendation/NLP-Job-Recommendation-main/.env
```

### 2. Required Credentials

#### MongoDB Atlas (Job Recommendation Engine)
- Create a new MongoDB Atlas cluster
- Generate new database user credentials
- Update `MONGODB_CONNECTION_STRING` in `Job-Recommendation/NLP-Job-Recommendation-main/.env`

#### Firebase Projects
You need to regenerate Firebase credentials for all projects:

1. **Student Project** (`yuvasetu-26ba4`)
2. **Employer Project** (`yuvasetu-employer`) 
3. **Admin Project** (`yuvasetu-admin`)

For each project:
- Go to Firebase Console → Project Settings → General
- Copy the Firebase config values to respective `.env` files
- Go to Service Accounts → Generate new private key
- Store the JSON files outside of version control
- Update paths in backend `.env` files

#### Google OAuth
- Go to Google Cloud Console
- Create new OAuth 2.0 credentials
- Update `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`

#### Email/SMTP
- Generate app-specific passwords for Gmail
- Update SMTP credentials in backend `.env` files

### 3. Security Best Practices

#### Never commit these files:
- `.env` files
- `*firebase-adminsdk*.json` files
- Any files containing API keys or passwords

#### Rotate all exposed credentials:
- ✅ MongoDB Atlas connection string (username: aman, password: Aman_1234)
- ✅ Firebase API keys and service account keys
- ✅ Google OAuth credentials
- ✅ Any SMTP passwords

### 4. Production Deployment

For production:
1. Use environment variables or secrets management (AWS Secrets Manager, etc.)
2. Never use `.env` files in production containers
3. Use strong, randomly generated secrets
4. Enable Firebase security rules
5. Restrict MongoDB Atlas IP access

### 5. Git History Cleanup

⚠️ **IMPORTANT**: The git history still contains exposed credentials. Consider:

```bash
# Option 1: Remove sensitive commits from history (DESTRUCTIVE)
git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch path/to/sensitive/file' --prune-empty --tag-name-filter cat -- --all

# Option 2: Create a fresh repository (RECOMMENDED)
# 1. Create new repository
# 2. Copy current code (without .git folder)
# 3. Initialize new git repository
# 4. Make initial commit with secured code
```

## 🔍 Files That Were Secured

### Removed from version control:
- `backend/student/firebase-adminsdk.json` - Firebase private key
- `backend/employer-admin/yuvasetu-employer-firebase-adminsdk-fbsvc-f7399ddf87.json` - Firebase private key  
- `backend/employer-admin/yuvasetu-admin-firebase-adminsdk.json` - Firebase private key
- All `.env` files with exposed credentials

### Updated to use environment variables:
- `Job-Recommendation/NLP-Job-Recommendation-main/app.py` - MongoDB connection
- `frontend/student/src/firebase.ts` - Firebase configuration
- All backend configuration files

## 📞 Support

If you need help setting up credentials or have questions about security, please refer to the respective service documentation:
- [Firebase Setup Guide](https://firebase.google.com/docs/web/setup)
- [MongoDB Atlas Setup](https://docs.atlas.mongodb.com/getting-started/)
- [Google OAuth Setup](https://developers.google.com/identity/protocols/oauth2)