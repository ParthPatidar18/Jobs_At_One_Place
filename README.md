Jobs_At_One_Place :-

It is a platform that automatically collects software engineering jobs from multiple sources, organizes them in one place, and helps job seekers discover the most relevant opportunities through an interactive dashboard.

Instead of checking multiple Telegram channels and career pages every day, Jobs_At_One_Place brings everything together and makes job searching faster and more organized.

Problem Statement ->

Searching for jobs every day is time-consuming.

Most job seekers have to:

Check multiple Telegram channels
Visit different company career pages
Search across job portals
Filter out irrelevant jobs
Keep track of companies that are hiring

Because information is spread across many places, it's easy to miss good opportunities.

Jobs_At_One_Place solves this by collecting jobs automatically, organizing them, and presenting them in a single dashboard.

✨ Features
📡 Automatically collects jobs from multiple sources
🤖 Uses AI to extract structured job information
🔍 Search and filter jobs by company, role, location, and experience
📊 Interactive dashboard with useful insights
🏢 Track companies and hiring trends
⚡ Live updates from Telegram job channels
🎯 Personalized job recommendations
💾 Stores and organizes job data in a database
🛠 Tech Stack

Backend

Python
FastAPI
SQLAlchemy
PostgreSQL

Dashboard

Streamlit
Plotly

Automation

Telethon
APScheduler

AI

OpenAI API
🚀 Installation
1. Clone the repository
git clone https://github.com/ParthPatidar18/Jobs_At_One_Place.git
cd Jobs_At_One_Place
2. Create a virtual environment
python -m venv venv

Activate it:

Windows

venv\Scripts\activate

Mac/Linux

source venv/bin/activate
3. Install dependencies
pip install -r requirements.txt
4. Configure environment variables

Create a .env file and add:

OPENAI_API_KEY=your_key
TELEGRAM_API_ID=your_id
TELEGRAM_API_HASH=your_hash
DATABASE_URL=your_database_url
5. Start the dashboard
streamlit run dashboard/app.py
📸 Screenshots
<img width="1915" height="873" alt="image" src="https://github.com/user-attachments/assets/89c08bb0-c600-4486-993e-9c0848c1f6e1" />

Dashboard

Add a screenshot here.

Job Listings

Add a screenshot here.

AI Recommendations

Add a screenshot here.

🤖 AI in Development

AI was used as a development assistant throughout the project to help with brainstorming, reviewing ideas, improving code quality, and speeding up implementation. All features, architecture, and final decisions were designed, reviewed, and integrated manually.
