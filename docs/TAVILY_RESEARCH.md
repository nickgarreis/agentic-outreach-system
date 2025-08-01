# Tavily Lead Research System

## Overview
The Tavily Lead Research System provides intelligent, automated research capabilities for leads in the Agentic Outreach System. It uses Tavily's advanced search API to gather comprehensive information about leads and their companies, enabling highly personalized outreach.

## Architecture

### Components
1. **Database Trigger**: `lead_research_trigger` monitors campaigns and creates jobs
2. **Job Queue**: Individual `lead_research` jobs for each lead
3. **AutopilotAgent**: Processes jobs and orchestrates research
4. **TavilyTool**: Executes searches and extractions
5. **Database Updates**: Enriches lead data with research findings

### Data Flow
```
Active Campaign → Trigger Fires → Create Jobs → AutopilotAgent → TavilyTool → Update Lead
                     ↑                                                              ↓
                     └─────────── Daily Limit Check ←──────────────────────────────┘
```

## Trigger Logic

### When the Trigger Fires
The `lead_research_trigger` activates when:
1. **Message Changes**: INSERT/UPDATE/DELETE on messages table
2. **Lead Status Changes**: UPDATE on leads.status column

### Trigger Conditions
For each active campaign, the trigger checks:
1. **Campaign Status**: Must be "active"
2. **Daily Limits**: Must have email/LinkedIn limits configured
3. **Message Gap**: `daily_limit - scheduled_today_count > 0`
4. **Available Leads**: Leads with status = "enriched" (not yet researched)
5. **Cooldown**: No research jobs created in the last hour

### Job Creation
- Creates individual jobs for each lead
- Limits to 10 jobs per trigger execution
- Prioritizes newer leads
- Includes lead and campaign context in job data

## Research Process

### 1. Job Processing
When the AutopilotAgent picks up a `lead_research` job:
```python
# Job data structure
{
    "lead_id": "uuid",
    "campaign_id": "uuid",
    "campaign_name": "Campaign Name",
    "lead_name": "First Last",
    "company": "Company Name",
    "triggered_by": "lead_research_trigger"
}
```

### 2. Research Execution
The TavilyTool performs parallel searches:

#### Search Types
1. **Person Research**
   - Query: Optimized using name, company, title, location
   - Domains: LinkedIn, Twitter, GitHub, Medium, Crunchbase
   - Depth: Advanced (10 credits)

2. **Company Research**
   - Query: Company with industry, location, recent developments
   - Domains: Crunchbase, TechCrunch, Reuters, Bloomberg
   - Depth: Advanced (10 credits)

3. **Recent News**
   - Query: Latest company announcements
   - Time Range: Last 7 days
   - Depth: Advanced (10 credits)

4. **Industry Insights**
   - Query: Role challenges and trends
   - Domains: Gartner, Forrester, McKinsey, HBR
   - Depth: Advanced (10 credits)

#### LinkedIn Extraction
If the lead has a LinkedIn URL:
- Extracts profile content with advanced depth
- Parses structured data: headline, about, experience, skills, education
- Enhances research with LinkedIn insights

### 3. Data Enhancement
Research data is structured as:
```json
{
    "research_data": {
        "person_info": {
            "query": "John Doe Acme Corp CTO San Francisco",
            "answer": "AI-generated summary...",
            "sources": [...],
            "linkedin_summary": "CTO at Acme | Tech Leader",
            "linkedin_headline": "Building the future of..."
        },
        "company_info": {
            "query": "Acme Corp technology San Francisco recent developments 2024",
            "answer": "Company overview...",
            "sources": [...]
        },
        "recent_news": {
            "articles": [
                {
                    "title": "Acme Raises $50M Series B",
                    "url": "https://...",
                    "published_date": "2024-01-15",
                    "summary": "..."
                }
            ]
        },
        "industry_insights": {
            "query": "CTO role challenges trends technology 2024",
            "answer": "Industry analysis...",
            "trends": [...]
        },
        "linkedin_profile": {
            "profile_summary": "...",
            "headline": "CTO at Acme Corp",
            "experience": [...],
            "skills": [...],
            "education": [...],
            "connections": 500
        }
    },
    "summary": {
        "lead_name": "John Doe",
        "company": "Acme Corp",
        "title": "CTO",
        "key_insights": [...],
        "recent_developments": [...],
        "conversation_starters": [...]
    },
    "research_timestamp": "2024-01-20T10:30:00Z"
}
```

### 4. Database Update
The lead record is updated with:
- `full_context`: Merged with research data
- `status`: Changed to "researched"
- Timestamp of research completion

## Features

### Intelligent Query Optimization
- Dynamic query building with templates
- Current year calculation
- Location and industry context extraction
- Query length optimization (max 400 chars)

### Parallel Search Execution
- All searches execute simultaneously
- 3-5x performance improvement
- Individual search failure doesn't break the process

### Retry Logic
- Exponential backoff: 1s, 2s, 4s... (max 30s)
- 3 retry attempts per search
- Rate limit awareness

### Domain Filtering
- Curated trusted domains per search type
- Excluded domains: Pinterest, Quora, Reddit, Facebook
- Score-based filtering (0.5 for person/company, 0.4 for insights)

### LinkedIn Integration
- Automatic extraction when LinkedIn URL available
- Advanced parsing for structured data
- Profile enrichment with experience, skills, education

### Credit Management
- All searches use advanced depth (10 credits each)
- Extraction costs: 2 credits per LinkedIn profile
- Usage tracking and cost estimation
- Rate limiting: 30 requests/minute

## Configuration

### Environment Variables
```bash
TAVILY_API_KEY=tvly-your-api-key
```

### Database Schema
The system uses existing tables:
- `campaigns`: Daily sending limits configuration
- `leads`: Status tracking and full_context storage
- `messages`: Scheduled message counting
- `jobs`: Background job queue

### Lead Status Flow
```
enrichment_failed → enriched → researched
                        ↑           ↓
                   (Apollo)    (Tavily)
```

## Usage Example

### Automatic Trigger
1. Campaign is active with daily limits set
2. Less than daily limit messages scheduled for today
3. Enriched leads available
4. Trigger creates research jobs
5. AutopilotAgent processes jobs
6. Leads marked as "researched"

### Manual Testing
```python
# Create a test job
from src.background.render_worker import JobScheduler

await JobScheduler.schedule_job(
    job_type="lead_research",
    data={
        "lead_id": "lead-uuid-here",
        "triggered_by": "manual_test"
    }
)
```

## Monitoring

### Key Metrics
- Average research time per lead: ~2-3 seconds
- Credit usage per lead: ~40-42 credits
- Success rate by search type
- LinkedIn extraction success rate

### Logs to Monitor
```
INFO: Starting lead research for lead: {lead_id}
INFO: Executing 4 parallel searches for lead research
INFO: Successfully extracted and parsed LinkedIn profile content
INFO: Lead research completed for {lead_id}
INFO: Tavily credit usage - Total: 42, Estimated cost: $0.42
```

### Error Handling
- Individual search failures logged but don't stop the process
- LinkedIn extraction failures are non-fatal
- Rate limit errors trigger backoff
- Failed jobs retry up to 3 times

## Best Practices

### Campaign Configuration
1. Set reasonable daily limits (e.g., 50 emails, 20 LinkedIn)
2. Ensure leads are properly enriched before research
3. Monitor credit usage and costs

### Lead Data Quality
1. Provide complete lead information (name, company, title)
2. Include LinkedIn URLs when available
3. Add location and industry to full_context

### Performance Optimization
1. The 1-hour cooldown prevents excessive job creation
2. Parallel searches maximize efficiency
3. Retry logic handles transient failures

## Troubleshooting

### Common Issues

1. **No Jobs Created**
   - Check campaign is active
   - Verify daily limits are set
   - Ensure enriched leads exist
   - Check 1-hour cooldown

2. **Research Failures**
   - Verify TAVILY_API_KEY is set
   - Check rate limits (30/minute)
   - Review search query quality
   - Monitor credit balance

3. **LinkedIn Extraction Issues**
   - Ensure valid LinkedIn URLs
   - Check for profile accessibility
   - Review parsing patterns

### Debug Queries
```sql
-- Check campaign readiness
SELECT 
    c.name,
    c.status,
    c.daily_sending_limit_email,
    c.daily_sending_limit_linkedin,
    COUNT(CASE WHEN l.status = 'enriched' THEN 1 END) as enriched_leads,
    COUNT(CASE WHEN m.send_at::date = CURRENT_DATE THEN 1 END) as scheduled_today
FROM campaigns c
LEFT JOIN leads l ON l.campaign_id = c.id
LEFT JOIN messages m ON m.campaign_id = c.id AND m.status = 'scheduled'
WHERE c.status = 'active'
GROUP BY c.id;

-- Check recent research jobs
SELECT 
    j.created_at,
    j.status,
    j.data->>'lead_name' as lead,
    j.data->>'company' as company,
    j.result->>'credit_usage' as credits
FROM jobs j
WHERE j.job_type = 'lead_research'
ORDER BY j.created_at DESC
LIMIT 10;
```

## Integration Points

### With Apollo Integration
- Apollo enriches leads (status → "enriched")
- Tavily researches enriched leads (status → "researched")
- Both tools complement each other

### With Message Scheduling
- Research ensures personalization data available
- Daily limits drive research needs
- Scheduled messages trigger research checks

### With Campaign Management
- Active campaigns drive the process
- Daily limits control research volume
- Campaign context enhances search quality

## Security & Privacy

1. **API Key Security**: Stored in environment variables
2. **No Sensitive Data in Logs**: Lead PII excluded from logs
3. **Domain Filtering**: Reduces exposure to malicious content
4. **Rate Limiting**: Prevents abuse and cost overruns

## Future Enhancements

1. **Caching Layer**: Cache research for 24-48 hours
2. **Dynamic Domains**: Per-campaign domain configuration
3. **Advanced Parsing**: Company websites, PDF extraction
4. **Real-time Updates**: Webhook notifications
5. **Research Quality Scoring**: ML-based relevance scoring