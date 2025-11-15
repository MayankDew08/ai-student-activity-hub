from google import genai
import os
import json

def find_jobs_with_serpapi(profile_file="profile_template.json"):
    """
    Load profile JSON and find relevant jobs using SerpAPI + Gemini
    """
    if not os.path.exists(profile_file):
        print(f"❌ Profile file not found: {profile_file}")
        return
    
    print("="*70)
    print("   AUTOMATIC JOB FINDER WITH SERPAPI + GEMINI AI")
    print("="*70)
    
    # Load the profile JSON
    print(f"\n📂 Loading profile: {profile_file}...")
    
    try:
        with open(profile_file, 'r', encoding='utf-8') as f:
            profile_data = json.load(f)
        
        print(f"✅ Profile loaded: {profile_data.get('personal_info', {}).get('name', 'Unknown')}")
        
        # Check if serpapi is installed
        try:
            from serpapi import GoogleSearch
        except ImportError:
            print("\n⚠️  SerpAPI not installed. Installing now...")
            import subprocess
            subprocess.check_call(['pip', 'install', 'google-search-results'])
            from serpapi import GoogleSearch
        
        # Extract key information from profile
        location = profile_data.get('personal_info', {}).get('location', 'United States')
        
        # Determine seniority from work experience
        work_exp = profile_data.get('work_experience', [])
        seniority = "Senior" if len(work_exp) >= 3 else "Mid-level" if len(work_exp) >= 2 else "Junior"
        
        # Create search query
        search_query = f"{seniority} Software Engineer {location}"
        
        print(f"\n🔍 Searching for jobs matching: {search_query}")
        print(f"   Using SerpAPI Google Jobs engine...")
        
        # SerpAPI parameters
        serpapi_key = os.getenv("SERPAPI_KEY", "")
        
        params = {
            "engine": "google_jobs",
            "q": search_query,
            "hl": "en",
            "api_key": serpapi_key
        }
        
        # Check if API key looks valid (at least 32 characters)
        if not params["api_key"] or len(params["api_key"]) < 32:
            print("\n⚠️  WARNING: SerpAPI key not configured!")
            print("   Get your free API key at: https://serpapi.com/")
            print("   Set environment variable: SERPAPI_KEY=your_key")
            print("   Or update the key in the code.")
            print("\n   Falling back to Gemini-only mode...\n")
            return find_jobs_with_gemini_only(profile_data)
        
        # Search for jobs
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "jobs_results" not in results:
            print("❌ No job results found from SerpAPI")
            print("   Falling back to Gemini-only mode...\n")
            return find_jobs_with_gemini_only(profile_data)
        
        jobs_results = results["jobs_results"]
        print(f"✅ Found {len(jobs_results)} jobs from Google Jobs\n")
        
        # Now use Gemini to analyze and rank these jobs
        client = genai.Client(api_key="AIzaSyDbA6T8H5U0RdNoBFra3dB7bm6AhYgA_zk")
        
        profile_text = json.dumps(profile_data, indent=2)
        jobs_text = json.dumps(jobs_results[:20], indent=2)  # Top 20 jobs
        
        prompt = f"""You are a job matching expert. I have a candidate profile and a list of real job openings from Google Jobs.

CANDIDATE PROFILE:
{profile_text}

AVAILABLE JOBS (from Google Jobs):
{jobs_text}

YOUR TASK:
1. Analyze the candidate's skills, experience, and qualifications
2. Review all the available jobs
3. Rank and select the TOP 10-15 jobs that best match this candidate
4. For each selected job, explain why it's a good match

FORMAT YOUR RESPONSE:

1. [Job Title] - [Company Name]
   Location: [Location]
   Match: [Explain why this job fits the candidate - 1-2 sentences]
   Apply: [Use the apply link from the job data]

Continue for all selected jobs, ordered from best match to good match.

IMPORTANT:
- Use the actual job data provided
- Include the real application links from the job data
- Focus on jobs that truly match the candidate's experience level and skills
- Order by best fit first

Provide your ranked job list now:"""

        print("🤖 Analyzing jobs with Gemini AI...\n")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Print results
        print("="*70)
        print("   JOB SEARCH RESULTS (LIVE DATA FROM SERPAPI)")
        print("="*70)
        print()
        print(response.text)
        print()
        print("="*70)
        print("✅ Job search complete!")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def find_jobs_with_gemini_only(profile_data):
    """
    Fallback: Use only Gemini when SerpAPI is not available
    """
    client = genai.Client(api_key="AIzaSyDbA6T8H5U0RdNoBFra3dB7bm6AhYgA_zk")
    
    profile_text = json.dumps(profile_data, indent=2)
    location = profile_data.get('personal_info', {}).get('location', 'their location')
    
    prompt = f"""You are a job search assistant. Based on this candidate's profile, provide a list of REAL job openings with direct links.

CANDIDATE PROFILE:
{profile_text}

YOUR TASK:
Find and list real job openings that match this candidate's profile. The candidate is looking for positions in or near {location}.

Provide 10-15 actual job listings from platforms like LinkedIn Jobs, Indeed, Glassdoor, company career pages, etc.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

1. Senior Software Engineer - Google
   Location: San Francisco, CA
   Match: Perfect fit for someone with 5+ years experience in full-stack development.
   Apply: https://www.google.com/about/careers/applications/jobs/results/123456

Continue for all jobs.

REQUIREMENTS:
✓ Provide REAL job links - use actual URLs
✓ List jobs from best match to good match
✓ Include full URLs starting with https://
✓ Make sure links are for currently open positions

Please provide the job listings now:"""

    print("🔍 Analyzing profile and searching for relevant jobs with Gemini...")
    print("   (This may take a moment...)\n")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    print("="*70)
    print("   JOB SEARCH RESULTS (GEMINI SUGGESTIONS)")
    print("="*70)
    print()
    print(response.text)
    print()
    print("="*70)
    print("✅ Job search complete!")
    print("="*70)

if __name__ == "__main__":
    find_jobs_with_serpapi()
