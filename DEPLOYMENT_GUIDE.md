# YuvaSetu Platform - Deployment Guide

## 🚀 GitHub Deployment Steps

### 1. Repository Setup

1. **Main Platform Repository**
   ```bash
   # The main YuvaSetu platform is at:
   # https://github.com/JOY-1909/TechFest-EdTech
   ```

2. **NLP Recommendation Engine Repository**
   ```bash
   # The recommendation engine is at:
   # https://github.com/Aman-Husain-123/NLP_Based_Recommendation_Engine
   ```

2. **Initialize and push the code**
   ```bash
   # If starting fresh (recommended for security)
   git init
   git add .
   git commit -m "Initial commit: YuvaSetu Platform with secured credentials"
   git branch -M main
   git remote add origin https://github.com/your-username/yuvasetu-platform.git
   git push -u origin main
   ```

### 2. Environment Variables for Deployment

#### Frontend Deployment (Vercel/Netlify)

**Student Frontend:**
```env
VITE_API_URL=https://your-student-api.herokuapp.com
VITE_FIREBASE_API_KEY=your_firebase_api_key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
```

**Employer Frontend:**
```env
VITE_FIREBASE_API_KEY=your_employer_firebase_api_key
VITE_FIREBASE_AUTH_DOMAIN=your-employer-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-employer-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-employer-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=your_employer_sender_id
VITE_FIREBASE_APP_ID=your_employer_app_id
VITE_FIREBASE_MEASUREMENT_ID=your_measurement_id
```

#### Backend Deployment (Heroku/Railway/DigitalOcean)

**Student Backend:**
```env
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/
DATABASE_NAME=yuva_setu
SECRET_KEY=your-super-secret-key-for-production
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
REDIS_URL=redis://your-redis-instance:6379
```

**Employer-Admin Backend:**
```env
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DB=yuvasetu
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY=your-firebase-private-key
FIREBASE_CLIENT_EMAIL=your-firebase-client-email
```

### 3. Platform-Specific Deployment

#### Option A: Vercel (Recommended for Frontend)

1. **Deploy Frontend Apps**
   ```bash
   # Connect your GitHub repo to Vercel
   # Deploy each frontend separately:
   # - frontend/student -> student.yuvasetu.com
   # - frontend/employer -> employer.yuvasetu.com  
   # - frontend/admin -> admin.yuvasetu.com
   # - open-resume -> resume.yuvasetu.com
   ```

2. **Configure Build Settings**
   ```json
   {
     "buildCommand": "npm run build",
     "outputDirectory": "dist",
     "installCommand": "npm install",
     "rootDirectory": "frontend/student"
   }
   ```

#### Option B: Heroku (Backend Services)

1. **Deploy Student Backend**
   ```bash
   # Create Heroku app
   heroku create yuvasetu-student-api
   
   # Set environment variables
   heroku config:set MONGODB_URL=your_mongodb_url
   heroku config:set SECRET_KEY=your_secret_key
   # ... add all other env vars
   
   # Deploy
   git subtree push --prefix=backend/student heroku main
   ```

2. **Deploy Employer-Admin Backend**
   ```bash
   heroku create yuvasetu-employer-api
   heroku config:set MONGODB_URI=your_mongodb_uri
   # ... configure and deploy
   ```

3. **Deploy Job Recommendation Engine**
   ```bash
   heroku create yuvasetu-recommendations
   heroku config:set MONGODB_CONNECTION_STRING=your_mongodb_string
   # ... configure and deploy
   ```

#### Option C: Docker Deployment

1. **Create Docker Compose for Production**
   ```yaml
   # docker-compose.prod.yml
   version: '3.8'
   services:
     student-backend:
       build: ./backend/student
       environment:
         - MONGODB_URL=${MONGODB_URL}
         - SECRET_KEY=${SECRET_KEY}
       ports:
         - "8001:8001"
     
     employer-backend:
       build: ./backend/employer-admin
       environment:
         - MONGODB_URI=${MONGODB_URI}
       ports:
         - "8000:8000"
     
     recommendation-engine:
       build: ./Job-Recommendation/NLP-Job-Recommendation-main
       environment:
         - MONGODB_CONNECTION_STRING=${MONGODB_CONNECTION_STRING}
       ports:
         - "5000:5000"
   ```

2. **Deploy to Cloud Provider**
   ```bash
   # AWS ECS, Google Cloud Run, or DigitalOcean App Platform
   docker-compose -f docker-compose.prod.yml up --build
   ```

### 4. Database Setup

#### MongoDB Atlas Production

1. **Create Production Clusters**
   ```bash
   # Create separate clusters for:
   # - Student data (yuva_setu database)
   # - Employer data (yuvasetu-main database)
   ```

2. **Configure Network Access**
   ```bash
   # Add IP addresses of your deployed services
   # Or use 0.0.0.0/0 for development (not recommended for production)
   ```

3. **Set up Database Users**
   ```bash
   # Create separate users with minimal required permissions
   # Student DB user: read/write to yuva_setu only
   # Employer DB user: read/write to yuvasetu-main only
   ```

### 5. Firebase Production Setup

1. **Create Production Firebase Projects**
   - Student project: `yuvasetu-student-prod`
   - Employer project: `yuvasetu-employer-prod`
   - Admin project: `yuvasetu-admin-prod`

2. **Configure Authentication**
   ```bash
   # Enable Google Sign-in
   # Configure authorized domains
   # Set up security rules
   ```

3. **Generate Service Account Keys**
   ```bash
   # Download service account JSON files
   # Store securely (not in version control)
   # Use environment variables for deployment
   ```

### 6. Domain Configuration

1. **Purchase Domain** (e.g., yuvasetu.com)

2. **Set up Subdomains**
   ```
   student.yuvasetu.com -> Student Frontend
   employer.yuvasetu.com -> Employer Frontend
   admin.yuvasetu.com -> Admin Frontend
   api.yuvasetu.com -> Student Backend
   employer-api.yuvasetu.com -> Employer Backend
   recommendations.yuvasetu.com -> Recommendation Engine
   resume.yuvasetu.com -> Resume Builder
   ```

3. **Configure SSL Certificates**
   ```bash
   # Most platforms (Vercel, Heroku) provide automatic SSL
   # For custom deployments, use Let's Encrypt
   ```

### 7. Monitoring and Analytics

1. **Set up Application Monitoring**
   - Sentry for error tracking
   - Google Analytics for user analytics
   - Uptime monitoring (Pingdom, UptimeRobot)

2. **Database Monitoring**
   - MongoDB Atlas built-in monitoring
   - Set up alerts for performance issues

3. **Performance Monitoring**
   - Lighthouse CI for frontend performance
   - API response time monitoring

### 8. CI/CD Pipeline

1. **GitHub Actions Workflow**
   ```yaml
   # .github/workflows/deploy.yml
   name: Deploy YuvaSetu Platform
   
   on:
     push:
       branches: [main]
   
   jobs:
     deploy-frontend:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v2
         - name: Deploy to Vercel
           # Configure Vercel deployment
     
     deploy-backend:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v2
         - name: Deploy to Heroku
           # Configure Heroku deployment
   ```

### 9. Security Checklist for Production

- [ ] All environment variables configured
- [ ] Firebase security rules enabled
- [ ] MongoDB IP whitelist configured
- [ ] HTTPS enabled on all domains
- [ ] CORS properly configured
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] Error messages don't expose sensitive data
- [ ] Logging configured (but not logging sensitive data)
- [ ] Regular security updates scheduled

### 10. Post-Deployment Testing

1. **Functional Testing**
   ```bash
   # Test all user flows:
   # - Student registration and login
   # - Job search and applications
   # - Employer posting and management
   # - Admin oversight functions
   ```

2. **Performance Testing**
   ```bash
   # Load testing with tools like:
   # - Artillery.io
   # - Apache Bench
   # - Lighthouse CI
   ```

3. **Security Testing**
   ```bash
   # Run security scans:
   # - OWASP ZAP
   # - Snyk for dependency vulnerabilities
   # - Firebase security rules testing
   ```

## 🔧 Troubleshooting Common Deployment Issues

### Build Failures
- Check Node.js version compatibility
- Verify all dependencies are in package.json
- Ensure environment variables are set

### Database Connection Issues
- Verify MongoDB connection strings
- Check IP whitelist settings
- Confirm database user permissions

### Authentication Problems
- Verify Firebase configuration
- Check CORS settings
- Confirm redirect URLs

### Performance Issues
- Enable caching (Redis)
- Optimize database queries
- Use CDN for static assets

## 📞 Support

For deployment support:
- Check the troubleshooting section above
- Review platform-specific documentation
- Create an issue on GitHub with deployment logs

---

**Ready to launch YuvaSetu and connect students with their dream internships! 🚀**