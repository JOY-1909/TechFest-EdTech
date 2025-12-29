# YuvaSetu - Complete Internship Platform

**YuvaSetu** is a comprehensive internship platform that connects students with employers through intelligent job matching and seamless application processes.

**🔗 Related Repositories:**
- **Main Platform**: [TechFest-EdTech](https://github.com/JOY-1909/TechFest-EdTech)
- **NLP Recommendation Engine**: [NLP_Based_Recommendation_Engine](https://github.com/Aman-Husain-123/NLP_Based_Recommendation_Engine)

## 🌟 Features

### For Students
- **Smart Job Recommendations** - AI-powered job matching based on skills and preferences
- **Interactive Dashboard** - Track applications, view recommendations, and manage profile
- **Resume Builder Integration** - Built-in OpenResume integration for professional resume creation
- **Geographic Insights** - Interactive map showing internship opportunities across India
- **Skill-based Matching** - Advanced NLP-based recommendation engine

### For Employers
- **Internship Management** - Post, edit, and manage internship listings
- **Candidate Search** - AI-powered semantic search to find ideal candidates
- **Application Tracking** - Streamlined applicant review and management system
- **Analytics Dashboard** - Insights into posting performance and candidate engagement

### For Administrators
- **Platform Oversight** - Monitor and moderate content across the platform
- **User Management** - Manage student and employer accounts
- **Analytics & Reporting** - Comprehensive platform usage statistics

## 🏗️ Architecture

```
YuvaSetu/
├── backend/
│   ├── student/              # Student-focused API (FastAPI)
│   └── employer-admin/       # Employer & Admin API (FastAPI)
├── frontend/
│   ├── student/              # Student portal (React + Vite)
│   ├── employer/             # Employer portal (React + Vite)
│   └── admin/                # Admin dashboard (React + Vite)
├── Job-Recommendation/       # NLP-based recommendation engine (Flask)
└── open-resume/              # Resume builder integration (Next.js)
```

## 🚀 Quick Start

### Prerequisites
- **Node.js** 18+
- **Python** 3.10+
- **MongoDB** 4.4+
- **Redis** (optional, for caching)

### 🔐 Security Setup (Required First)

1. **Read the security guide**
   ```bash
   cat SECURITY_SETUP.md
   ```

2. **Set up environment variables**
   ```bash
   # Copy all environment templates
   cp frontend/student/.env.example frontend/student/.env
   cp frontend/employer/.env.example frontend/employer/.env
   cp frontend/admin/.env.example frontend/admin/.env
   cp backend/student/.env.example backend/student/.env
   cp backend/employer-admin/.env.example backend/employer-admin/.env
   cp Job-Recommendation/NLP-Job-Recommendation-main/.env.example Job-Recommendation/NLP-Job-Recommendation-main/.env
   ```

3. **Configure credentials** in each `.env` file (see `SECURITY_SETUP.md`)

### 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/JOY-1909/TechFest-EdTech.git
   cd TechFest-EdTech
   ```

2. **Clone the NLP Recommendation Engine** (if not already included)
   ```bash
   # If Job-Recommendation folder is empty, clone the recommendation engine
   git clone https://github.com/Aman-Husain-123/NLP_Based_Recommendation_Engine.git Job-Recommendation/NLP-Job-Recommendation-main
   ```

2. **Install backend dependencies**
   ```bash
   # Student API
   cd backend/student
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt

   # Employer-Admin API
   cd ../employer-admin
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt

   # Job Recommendation Engine
   cd ../../Job-Recommendation/NLP-Job-Recommendation-main
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install frontend dependencies**
   ```bash
   # Install for all frontend apps
   cd frontend/student && npm install
   cd ../employer && npm install
   cd ../admin && npm install
   cd ../../open-resume && npm install
   ```

4. **Initialize search indices**
   ```bash
   cd backend/employer-admin
   python -m app.scripts.init_faiss
   ```

### 🏃‍♂️ Running the Platform

Start each service in a separate terminal:

```bash
# Terminal 1: Student Backend
cd backend/student && source venv/bin/activate && uvicorn app.main:app --reload --port 8001

# Terminal 2: Employer-Admin Backend  
cd backend/employer-admin && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 3: Job Recommendation Engine
cd Job-Recommendation/NLP-Job-Recommendation-main && source venv/bin/activate && python app.py

# Terminal 4: Student Frontend
cd frontend/student && npm run dev

# Terminal 5: Employer Frontend
cd frontend/employer && npm run dev

# Terminal 6: Admin Frontend
cd frontend/admin && npm run dev

# Terminal 7: Resume Builder (Optional)
cd open-resume && npm run dev
```

### 🌐 Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Student Portal | http://localhost:8080 | Student dashboard and job search |
| Employer Portal | http://localhost:8082 | Employer internship management |
| Admin Dashboard | http://localhost:8081 | Platform administration |
| Job Recommendations | http://localhost:5000 | AI recommendation engine |
| Resume Builder | http://localhost:3000 | Professional resume creation |

## 🔧 Technology Stack

### Backend
- **FastAPI** - High-performance Python web framework
- **MongoDB** - Document database with Atlas cloud hosting
- **Redis** - Caching and session management
- **FAISS** - Vector similarity search for recommendations
- **Sentence Transformers** - NLP embeddings for job matching

### Frontend
- **React 18** - Modern UI library with hooks
- **Vite** - Fast build tool and dev server
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework
- **React Query** - Server state management

### AI & ML
- **Sentence-BERT** - Semantic text understanding
- **FAISS** - Efficient similarity search
- **scikit-learn** - Machine learning utilities
- **spaCy** - Natural language processing

### Infrastructure
- **Docker** - Containerization
- **Firebase** - Authentication and real-time features
- **MongoDB Atlas** - Cloud database hosting
- **Vercel/Netlify** - Frontend deployment

## 📊 Key Features Deep Dive

### 🤖 AI-Powered Job Matching
- Uses advanced NLP models to understand job descriptions and student profiles
- Semantic similarity matching beyond keyword-based search
- Continuous learning from user interactions and feedback

### 🗺️ Geographic Intelligence
- Interactive map visualization of internship opportunities
- State-wise statistics and trends
- Location-based filtering and recommendations

### 📈 Analytics & Insights
- Real-time dashboard for employers and administrators
- Application tracking and conversion metrics
- Platform usage analytics and reporting

### 🔒 Security & Privacy
- JWT-based authentication
- Role-based access control
- Data encryption and secure API endpoints
- GDPR-compliant data handling

## 🚀 Deployment

### Production Environment Variables
Ensure all production credentials are properly configured:
- MongoDB Atlas connection strings
- Firebase service account keys
- SMTP credentials for email notifications
- Redis connection for caching
- API keys for external services

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up --build
```

### Manual Deployment
1. Set up production MongoDB Atlas clusters
2. Configure Firebase projects for authentication
3. Deploy backends to cloud platforms (AWS, GCP, Azure)
4. Deploy frontends to static hosting (Vercel, Netlify)
5. Set up monitoring and logging

## 📚 Documentation

- [`SECURITY_SETUP.md`](SECURITY_SETUP.md) - **Essential security configuration**
- [`DATABASE_SETUP_GUIDE.md`](DATABASE_SETUP_GUIDE.md) - Database configuration
- [`DEV_NOTES.md`](DEV_NOTES.md) - Development guidelines
- [`TESTING_RECOMMENDATION_ENGINE.md`](TESTING_RECOMMENDATION_ENGINE.md) - AI testing guide

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **NLP Recommendation Engine** - [Aman-Husain-123/NLP_Based_Recommendation_Engine](https://github.com/Aman-Husain-123/NLP_Based_Recommendation_Engine)
- **OpenResume** - Integrated resume builder
- **Sentence Transformers** - NLP embeddings
- **FAISS** - Efficient similarity search
- **FastAPI** - High-performance web framework

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation in the `/docs` folder
- Review the troubleshooting section in `README.md`

---

**Built with ❤️ for connecting students with their dream internships**