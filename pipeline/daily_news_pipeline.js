const axios = require('axios');
const cheerio = require('cheerio');
const cron = require('node-cron');
const { MongoClient } = require('mongodb');
require('dotenv').config();

/**
 * UPSC Daily Current Affairs Pipeline
 * This script automates fetching news from The Hindu and PIB,
 * processes them using AI (GPT-4o-mini), and stores the result in MongoDB.
 */

// Configuration
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017';
const DATABASE_NAME = 'upsc_chatbot';
const COLLECTION_NAME = 'current_affairs';
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

/**
 * AI Transformation Node
 * Converts raw news articles into UPSC structured JSON format.
 */
const aiUpscFormat = async (articles, date) => {
  if (!OPENAI_API_KEY) {
    console.warn("OPENAI_API_KEY not found. Using rule-based fallback categorization.");
    return fallbackCategorization(articles, date);
  }

  try {
    const prompt = `You are a UPSC Current Affairs Expert.

Convert the given news articles into UPSC structured JSON.

Date: ${date}
Articles: ${JSON.stringify(articles)}

Output format:
{
  "date": "${date}",
  "overview": "5-6 lines summary of entire content",
  "categories": {
    "polity_governance": [],
    "international_relations": [],
    "economy": [],
    "science_technology": [],
    "environment_ecology": [],
    "defense_security": [],
    "government_schemes": []
  }
}

Rules:
- Keep summaries short (1-2 lines max)
- Categorize properly based on UPSC syllabus
- No extra text outside JSON`;

    const response = await axios.post('https://api.openai.com/v1/chat/completions', {
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      response_format: { type: "json_object" }
    }, {
      headers: { 'Authorization': `Bearer ${OPENAI_API_KEY}` }
    });

    return JSON.parse(response.data.choices[0].message.content);
  } catch (error) {
    console.error("AI Node failed:", error.message);
    return fallbackCategorization(articles, date);
  }
};

/**
 * Simple rule-based fallback if AI is unavailable
 */
const fallbackCategorization = (articles, date) => {
  const result = {
    date,
    overview: `UPSC News Roundup for ${date} covering ${articles.length} updates from The Hindu and PIB.`,
    categories: {
      polity_governance: [],
      international_relations: [],
      economy: [],
      science_technology: [],
      environment_ecology: [],
      defense_security: [],
      government_schemes: []
    }
  };

  articles.forEach(article => {
    const text = (article.title + " " + article.content).toLowerCase();
    if (text.includes('election') || text.includes('supreme court') || text.includes('bill')) {
      result.categories.polity_governance.push(article.title);
    } else if (text.includes('india-') || text.includes('treaty') || text.includes('ambassador')) {
      result.categories.international_relations.push(article.title);
    } else if (text.includes('gdp') || text.includes('inflation') || text.includes('rbi')) {
      result.categories.economy.push(article.title);
    } else {
      result.categories.polity_governance.push(article.title); // Default
    }
  });

  return result;
};

/**
 * Main Pipeline Execution
 */
const runPipeline = async () => {
  const selected_date = new Date().toISOString().split('T')[0];
  console.log(`\n[${new Date().toLocaleString()}] Starting UPSC Daily Pipeline...`);

  try {
    // 1. Fetch Hindu Links
    console.log("-> Fetching The Hindu...");
    const { data: hinduHtml } = await axios.get('https://www.thehindu.com/');
    const $h = cheerio.load(hinduHtml);
    let hinduLinks = [];
    $h('a').each((i, el) => {
      const href = $h(el).attr('href');
      if (href && href.includes('/news/')) hinduLinks.push(href.startsWith('http') ? href : 'https://www.thehindu.com' + href);
    });
    const selectedHindu = [...new Set(hinduLinks)].slice(0, 5);

    // 2. Fetch PIB Links
    console.log("-> Fetching PIB...");
    const { data: pibHtml } = await axios.get('https://pib.gov.in/PressReleasePage.aspx');
    const $p = cheerio.load(pibHtml);
    let pibLinks = [];
    $p('a').each((i, el) => {
      const href = $p(el).attr('href');
      if (href && href.includes('PRID')) pibLinks.push(href.startsWith('http') ? href : 'https://pib.gov.in/' + href);
    });
    const selectedPib = [...new Set(pibLinks)].slice(0, 5);

    // 3. Merge and Scrape
    const allLinks = [...selectedHindu, ...selectedPib];
    console.log(`-> Scraping ${allLinks.length} articles...`);
    let articles = [];
    for (let url of allLinks) {
      try {
        const { data } = await axios.get(url);
        const $ = cheerio.load(data);
        const title = $('h1').first().text().trim();
        const content = $('p').map((i, p) => $(p).text()).get().join(' ').substring(0, 3000); // Truncate for AI context
        if (title && content) articles.push({ title, content, url });
      } catch (e) {
        console.error(`   ! Failed: ${url}`);
      }
    }

    // 4. AI Formatting
    console.log("-> Processing with AI...");
    const finalData = await aiUpscFormat(articles, selected_date);

    // 5. MongoDB Upsert
    console.log("-> Upserting to MongoDB...");
    const client = new MongoClient(MONGODB_URI);
    await client.connect();
    const db = client.db(DATABASE_NAME);
    const collection = db.collection(COLLECTION_NAME);
    
    await collection.updateOne(
      { date: finalData.date },
      { $set: finalData },
      { upsert: true }
    );
    
    await client.close();
    console.log("✓ Pipeline Completed Successfully.\n");

  } catch (error) {
    console.error("Critical Error:", error.message);
  }
};

// Scheduler: 6 AM IST
cron.schedule('0 6 * * *', runPipeline, {
  timezone: "Asia/Kolkata"
});

// Run once on startup
runPipeline();
