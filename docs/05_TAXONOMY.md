# Taxonomy — Category & Tag System
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Purpose

A consistent, hierarchical taxonomy ensures that APIs from different sources get
classified consistently, searches produce relevant results across categories, and
users can browse the full API landscape by domain.

The taxonomy has three layers:
1. **Top-level categories** — broad domains (e.g. "AI & Machine Learning")
2. **Sub-categories** — specific areas within a domain (e.g. "Text Generation")
3. **Tags** — free-form, non-hierarchical labels (e.g. "llm", "streaming", "no-auth")

---

## 2. Top-Level Category Tree

### AI & Machine Learning
- Text Generation & LLMs
- Image Generation
- Image Recognition & Classification
- Speech & Audio AI
- Translation & Language Detection
- Sentiment Analysis
- Text Extraction & OCR
- Embeddings & Semantic Search
- Code Generation
- Video AI
- Recommendation Systems
- Predictive Analytics

### Data & Analytics
- Business Intelligence
- Data Aggregation
- Statistics & Demographics
- Market Research
- Survey Data
- Social Media Analytics
- Web Analytics

### Document & File Processing
- PDF Processing
- Document Conversion
- Text Extraction
- File Storage
- Image Processing
- Video Processing
- Audio Processing
- Compression & Archiving
- E-Signatures

### Communication
- Email
- SMS & Messaging
- Push Notifications
- Chat & Instant Messaging
- Voice & Telephony
- Video Conferencing
- Fax

### Finance & Payments
- Payment Processing
- Currency & Exchange Rates
- Cryptocurrency
- Banking & Accounts
- Stock Market & Trading
- Financial Data
- Invoice & Billing
- Tax

### Geographic & Location
- Geocoding & Reverse Geocoding
- Mapping
- Places & Points of Interest
- Routing & Directions
- Timezone
- IP Geolocation
- Elevation & Terrain
- Boundaries & Regions

### Weather & Environment
- Current Weather
- Forecasting
- Historical Weather
- Air Quality
- Climate Data
- Natural Disasters
- Astronomy & Space

### Government & Public Data
- Open Government Data
- Legal & Legislation
- Court Records
- Public Health
- Elections & Voting
- Census & Demographics
- Infrastructure
- Public Transport

### Science & Research
- Academic Papers
- Biology & Genomics
- Chemistry
- Physics
- Astronomy
- Environmental Science
- Medical Research
- Mathematics

### Health & Medical
- Medical Information
- Drug & Medication
- Clinical Trials
- Health Records (FHIR)
- Fitness & Activity
- Mental Health
- Nutrition

### E-commerce & Retail
- Product Search & Catalog
- Price Comparison
- Barcode & ISBN Lookup
- Inventory
- Shipping & Logistics
- Reviews & Ratings
- Coupons & Deals

### Travel & Transportation
- Flights
- Hotels & Accommodation
- Car Rental
- Public Transit
- Ride Sharing
- Travel Information
- Booking

### Food & Beverage
- Recipes
- Restaurant Finder
- Nutrition Information
- Ingredient Data
- Barcode Food Lookup
- Allergen Information

### Media & Entertainment
- Music
- Movies & TV
- Books & Literature
- Games
- Sports
- News
- Podcasts & Radio
- Comics & Manga

### Social & Identity
- Social Media Integration
- User Authentication (OAuth)
- Identity Verification
- Avatar & Profile
- Social Graph

### Developer Tools
- Authentication & Authorization
- Webhooks & Events
- Code Execution
- Version Control
- CI/CD
- Error Tracking
- Logging
- Feature Flags
- Testing
- Uptime Monitoring

### Security
- Vulnerability Scanning
- Threat Intelligence
- Domain & IP Reputation
- Password & Credential Checking
- Malware Detection
- SSL Certificate Info
- WHOIS & DNS Lookup

### Search
- Web Search
- Image Search
- Video Search
- Product Search
- Academic Search
- Real-Time Search

### Utilities
- URL Shortening
- QR Code Generation
- Barcode Generation
- Random Data Generation
- UUID Generation
- Color & Design
- Math & Calculation
- Unit Conversion
- Text Utilities
- Time & Date

### Infrastructure & Networking
- DNS
- CDN
- IP & Network Info
- SSL/TLS
- Domain Registration
- WHOIS
- Ping & Uptime

### Industrial & IoT
- Sensor Data
- Device Management
- Industrial Automation
- Energy & Power
- Smart Home
- Fleet Management

### Agriculture & Food Supply
- Crop Data
- Soil & Weather (Agriculture)
- Food Safety
- Supply Chain

### Education
- Courses & Learning
- Quiz & Assessment
- Language Learning
- Math Education
- Science Education

---

## 3. Classification Rules

### Primary Category Assignment
An API receives exactly one primary category (the `categories[0]` value) based on
its primary function. If an API serves multiple purposes, choose the most specific
or dominant use case.

### Multi-Category Assignment
An API may have up to 5 categories total. Add additional categories only when the
API has substantial functionality in those areas — not just marginal overlap.

### Examples
- OpenWeatherMap → `["Weather & Environment > Current Weather", "Weather & Environment > Forecasting"]`
- Stripe → `["Finance & Payments > Payment Processing", "Finance & Payments > Invoice & Billing"]`
- Google Maps (free tier) → `["Geographic & Location > Mapping", "Geographic & Location > Geocoding & Reverse Geocoding", "Geographic & Location > Routing & Directions"]`

---

## 4. Tag Vocabulary

Tags are free-form but we maintain a preferred vocabulary for consistency.
The enrichment pipeline uses these canonical tags when applicable.

### Auth & Access Tags
```
no-auth          apikey-free      oauth-required
instant-signup   no-signup        rate-limited
unlimited        free-tier
```

### Format Tags
```
rest  graphql  soap  grpc  websocket  sse
json  xml  csv  binary  protobuf  jsonld
openapi  swagger  postman
```

### Data Type Tags
```
real-time  historical  batch  streaming  static
geospatial  time-series  text  image  audio  video
structured  unstructured  multilingual
```

### Quality / Reliability Tags
```
official  community  government  academic  enterprise
well-documented  minimal-docs  stable  beta  deprecated
high-availability  sla-guaranteed
```

### Domain Tags (additional specifics)
```
llm  nlp  ocr  computer-vision  speech-to-text  text-to-speech
sentiment  translation  summarization  embeddings
pdf  word  excel  markdown  html  latex
payment  cryptocurrency  stocks  forex  banking
weather  satellite  radar  forecast  climate
election  legislation  court  patents  trademarks
dna  protein  molecule  drug  clinical
barcode  isbn  upc  ean  qr-code
```

---

## 5. LLM Classification Prompt

The enrichment pipeline uses this prompt to assign categories and tags:

```
You are classifying an API for a developer reference database.

API Name: {name}
Description: {description}
Base URL: {base_url}
Auth Type: {auth_type}

Available top-level categories:
{category_list}

Task:
1. Assign 1–5 categories from the list above. Use the format "Parent > Child".
   Put the most relevant category first.
2. Assign 5–15 tags from the preferred vocabulary or invent new ones.
   Tags should help developers find this API in searches.
3. Write 3–7 use cases in plain language starting with "Use to..."
4. Write a 2–3 sentence plain-language summary of what this API does
   and who would use it.

Respond in JSON:
{
  "categories": ["..."],
  "tags": ["..."],
  "use_cases": ["Use to...", ...],
  "description_llm": "..."
}
```

---

## 6. Category Maintenance

Categories should be reviewed when:
- A new technology domain emerges (e.g. "AI Agents" may need its own category)
- More than 500 APIs accumulate under "Utilities" (may need splitting)
- A category has fewer than 3 APIs (may need merging)

Category changes require:
1. Update this document
2. Update the LLM classification prompt
3. Run a re-classification job on affected APIs
4. Update the `mv_category_counts` materialized view
