from typing import Dict, List
from pydantic import BaseModel, Field
import requests
from firecrawl import FirecrawlApp
import streamlit as st
import os
import opik
from opik import track
from dotenv import load_dotenv
opik.configure()

# Load environment variables from .env file if it exists
load_dotenv()

class DefineStructure(BaseModel):
    region: str = Field(description="Region or area where the job is located", default=None)
    role: str = Field(description="Specific role or function within the job category", default=None)
    job_title: str = Field(description="Title of the job position", default=None)
    experience: str = Field(description="Experience required for the position", default=None)
    job_link: str = Field(description="Link to the job posting", default=None)

class ExtractSchema(BaseModel):
    job_postings: List[DefineStructure] = Field(description="List of job postings")

class TrendIndustry(BaseModel):
    industry: str = Field(description="Industry name", default=None)
    avg_salary: float = Field(description="Average salary in the industry", default=None)
    growth_rate: float = Field(description="Growth rate of the industry", default=None)
    demand_level: str = Field(description="Demand level in the industry", default=None)
    top_skills: List[str] = Field(description="Top skills in demand for this industry", default=None)

class IndustryTrendsSchema(BaseModel):
    industry_trends: List[TrendIndustry] = Field(description="List of industry trends")

class FirecrawlResponse(BaseModel):
    success: bool
    data: Dict
    status: str
    expiresAt: str

class JobSearchingAgent:
    def __init__(self, firecrawl_api_key: str, hf_api_key: str, model_url: str):
        self.firecrawl = FirecrawlApp(api_key=firecrawl_api_key)
        self.hf_api_key = hf_api_key
        self.model_url = model_url

    @track
    def _generate_text(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.hf_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 800}
        }
        try:
            response = requests.post(self.model_url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()[0]['generated_text']
        except Exception as e:
            return f"Error generating text: {e}"

    @track
    def find_jobs(self, job_title: str, location: str, experience_years: int, skills: List[str]) -> str:
        formatted_job_title = job_title.lower().replace(" ", "-")
        formatted_location = location.lower().replace(" ", "-")
        skills_string = ", ".join(skills)
        urls = [
            f"https://www.naukri.com/{formatted_job_title}-jobs-in-{formatted_location}",
            f"https://www.indeed.com/jobs?q={formatted_job_title}&l={formatted_location}",
            f"https://www.monster.com/jobs/search/?q={formatted_job_title}&where={formatted_location}",
        ]
        try:
            raw_response = self.firecrawl.extract(
                urls=urls,
                params={
                    'prompt': f"""Extract job postings by region, roles, job titles, and experience from these job sites.
                    Look for jobs that match these criteria:
                    - Job Title: Should be related to {job_title}
                    - Location: {location} (include remote jobs if available)
                    - Experience: Around {experience_years} years
                    - Skills: Should match at least some of these skills: {skills_string}
                    - Job Type: Full-time, Part-time, Contract, Temporary, Internship
                    Extract:
                    - region, role, job_title, experience, job_link
                    MAX 10 postings.
                    """,
                    'schema': ExtractSchema.model_json_schema()
                }
            )
            if isinstance(raw_response, dict) and raw_response.get('success'):
                jobs = raw_response['data'].get('job_postings', [])
            else:
                jobs = []
            if not jobs:
                return "No job listings found matching your criteria."

            prompt = f"""As a career expert, analyze these job opportunities:
Jobs:
{jobs}
INSTRUCTIONS:
1. Select best matching 5-6 jobs.
2. Provide:
💼 SELECTED JOB OPPORTUNITIES
- Job Title and Role
- Region/Location
- Experience Required
- Pros and Cons
- Job Link
🔍 SKILLS MATCH ANALYSIS
- Skills match
- Experience fit
- Growth potential
💡 RECOMMENDATIONS
- Top 3 jobs
- Career growth
📝 APPLICATION TIPS
- Resume and strategy tips
"""
            return self._generate_text(prompt)
        except Exception as e:
            return f"An error occurred while searching for jobs: {str(e)}"

    @track
    def get_industry_trends(self, job_category: str) -> str:
        urls = [
            f"https://www.payscale.com/research/US/Job={job_category.replace(' ', '_')}/Salary",
            f"https://www.glassdoor.com/Salaries/{job_category.lower().replace(' ', '-')}-salary-SRCH_KO0,{len(job_category)}.htm"
        ]
        try:
            raw_response = self.firecrawl.extract(
                urls=urls,
                params={
                    'prompt': f"""Extract industry trends data for the {job_category} industry.
                    For each, extract:
                    - industry, avg_salary, growth_rate, demand_level, top_skills
                    3-5 roles/sub-categories.
                    """,
                    'schema': IndustryTrendsSchema.model_json_schema()
                }
            )
            if isinstance(raw_response, dict) and raw_response.get('success'):
                industries = raw_response['data'].get('industry_trends', [])
                if not industries:
                    return f"No industry trends data available for {job_category}."
                prompt = f"""Analyze these trends for {job_category}:
{industries}
📊 INDUSTRY TRENDS SUMMARY
🔥 TOP SKILLS IN DEMAND
📈 CAREER GROWTH OPPORTUNITIES
🎯 RECOMMENDATIONS FOR JOB SEEKERS
"""
                return self._generate_text(prompt)
            return f"No industry trends data available for {job_category}."
        except Exception as e:
            return f"An error occurred while fetching industry trends: {str(e)}"

def job_agent_create():
    if 'job_agent' not in st.session_state:
        st.session_state.job_agent = JobSearchingAgent(
            firecrawl_api_key=st.session_state.firecrawl_key,
            hf_api_key=st.session_state.hf_key,
            model_url=st.session_state.model_url
        )

def main():
    st.set_page_config(page_title="AI Job Hunting Assistant", page_icon="💼", layout="wide")
    env_firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
    env_hf_key = os.getenv("HF_API_KEY", "")
    env_model_url = os.getenv("HF_MODEL_URL", "")

    with st.sidebar:
        st.title("🔑 API Configuration")
        st.subheader("🤗 Hugging Face Settings")
        model_url = st.text_input("HF Model Inference URL", value=env_model_url or "")
        hf_key = st.text_input("Hugging Face API Key", type="password", value=env_hf_key or "")
        firecrawl_key = st.text_input("Firecrawl API Key", type="password", value=env_firecrawl_key or "")

        if firecrawl_key and hf_key and model_url:
            st.session_state.firecrawl_key = firecrawl_key
            st.session_state.hf_key = hf_key
            st.session_state.model_url = model_url
            job_agent_create()
        else:
            st.warning("⚠️ Please provide all required API keys and model URL.")

    st.title("💼 AI Job Hunting Assistant")
    st.info("Enter your job search criteria below to get job recommendations and industry insights.")
    col1, col2 = st.columns(2)

    with col1:
        job_title = st.text_input("Job Title", placeholder="Software Engineer")
        location = st.text_input("Location", placeholder="Remote, New York")

    with col2:
        experience_years = st.number_input("Experience (in years)", min_value=0, max_value=30, value=2)
        skills_input = st.text_area("Skills (comma separated)", placeholder="Python, SQL, React")
        skills = [s.strip() for s in skills_input.split(",") if s.strip()]

    job_category = st.selectbox("Industry/Job Category", [
        "Information Technology", "Software Development", "Data Science", "Marketing",
        "Finance", "Healthcare", "Education", "Engineering", "Sales", "Human Resources"
    ])

    if st.button("🔍 Start Job Search", use_container_width=True):
        if 'job_agent' not in st.session_state:
            st.error("⚠️ Please enter your API keys in the sidebar first!")
            return
        if not job_title or not location:
            st.error("⚠️ Please enter both job title and location!")
            return
        if not skills:
            st.warning("⚠️ No skills provided. Adding skills will improve job matching.")
        try:
            with st.spinner("🔍 Searching for jobs..."):
                job_results = st.session_state.job_agent.find_jobs(
                    job_title=job_title,
                    location=location,
                    experience_years=experience_years,
                    skills=skills
                )
                st.success("✅ Job search completed!")
                st.subheader("💼 Job Recommendations")
                st.markdown(job_results)
                st.divider()
                with st.spinner("📊 Analyzing industry trends..."):
                    industry_trends = st.session_state.job_agent.get_industry_trends(job_category)
                    st.success("✅ Industry analysis completed!")
                    with st.expander(f"📈 {job_category} Industry Trends Analysis"):
                        st.markdown(industry_trends)
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
