#!/usr/bin/env python3
"""
White House Briefings & Statements RSS Feed Generator

Scrapes https://www.whitehouse.gov/briefings-statements/ and generates
a valid RSS 2.0 feed.

Usage:
    python whitehouse_rss_scraper.py

Output:
    Creates 'whitehouse_briefings.xml' in the current directory
"""

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import re
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'url': 'https://www.whitehouse.gov/briefings-statements/',
    'base_url': 'https://www.whitehouse.gov',
    'output_file': 'whitehouse_briefings.xml',
    'feed_title': 'White House Briefings & Statements',
    'feed_description': 'Official Briefings and Statements from the White House',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def parse_date(date_str: str) -> datetime:
    """Parse date string like 'November 14, 2025' into datetime object."""
    try:
        # Try common formats
        for fmt in ['%B %d, %Y', '%b %d, %Y', '%Y-%m-%d']:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        
        # If no format matched, return current time
        logger.warning(f"Could not parse date: {date_str}")
        return datetime.now(timezone.utc)
    except Exception as e:
        logger.error(f"Date parsing error: {e}")
        return datetime.now(timezone.utc)


def fetch_page(url: str) -> str:
    """Fetch the webpage content."""
    headers = {
        'User-Agent': CONFIG['user_agent'],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def extract_entries(html: str) -> list[dict]:
    """Extract briefing entries from the HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    entries = []
    
    # Strategy 1: Look for links containing '/briefings-statements/' in href
    # that appear to be article titles (not navigation)
    seen_urls = set()
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        
        # Skip navigation and non-article links
        if not href:
            continue
        
        # We want individual briefing pages, not the archive page itself
        # Pattern: /briefings-statements/some-slug/
        if '/briefings-statements/' in href and href != '/briefings-statements/':
            # Normalize URL
            if href.startswith('/'):
                full_url = CONFIG['base_url'] + href
            else:
                full_url = href
            
            # Skip if we've seen this URL
            if full_url in seen_urls:
                continue
            
            # Skip pagination links
            if '/page/' in href:
                continue
                
            # Get title text
            title = link.get_text(strip=True)
            
            # Skip empty titles or very short ones (likely not articles)
            if not title or len(title) < 10:
                continue
            
            # Skip if title looks like navigation
            nav_words = ['next', 'previous', 'older', 'newer', 'page', '»', '«']
            if any(word in title.lower() for word in nav_words):
                continue
            
            seen_urls.add(full_url)
            
            # Try to find associated date
            # Look in parent elements for date patterns
            date_str = None
            parent = link.parent
            
            # Search up to 5 levels up for a date
            for _ in range(5):
                if parent is None:
                    break
                
                parent_text = parent.get_text()
                
                # Look for date pattern like "November 14, 2025"
                date_match = re.search(
                    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
                    parent_text
                )
                if date_match:
                    date_str = date_match.group(0)
                    break
                
                parent = parent.parent
            
            entry = {
                'title': title,
                'url': full_url,
                'date': parse_date(date_str) if date_str else datetime.now(timezone.utc),
                'date_str': date_str or 'Unknown'
            }
            entries.append(entry)
            logger.info(f"Found: {title[:60]}... ({entry['date_str']})")
    
    # Sort by date, newest first
    entries.sort(key=lambda x: x['date'], reverse=True)
    
    return entries


def generate_rss(entries: list[dict], output_path: str) -> None:
    """Generate RSS feed from entries."""
    fg = FeedGenerator()
    fg.title(CONFIG['feed_title'])
    fg.link(href=CONFIG['url'], rel='alternate')
    fg.link(href=output_path, rel='self')
    fg.description(CONFIG['feed_description'])
    fg.language('en')
    fg.lastBuildDate(datetime.now(timezone.utc))
    
    for entry in entries:
        fe = fg.add_entry()
        fe.title(entry['title'])
        fe.link(href=entry['url'])
        fe.guid(entry['url'], permalink=True)
        fe.pubDate(entry['date'])
        fe.description(f"White House Briefing/Statement: {entry['title']}")
    
    # Write RSS file
    fg.rss_file(output_path, pretty=True)
    logger.info(f"RSS feed written to: {output_path}")


def main():
    """Main function to run the scraper."""
    logger.info(f"Fetching {CONFIG['url']}")
    
    try:
        html = fetch_page(CONFIG['url'])
        logger.info(f"Fetched {len(html)} bytes")
        
        entries = extract_entries(html)
        logger.info(f"Found {len(entries)} entries")
        
        if entries:
            generate_rss(entries, CONFIG['output_file'])
            logger.info("Done!")
        else:
            logger.warning("No entries found. The page structure may have changed.")
            
    except requests.RequestException as e:
        logger.error(f"Failed to fetch page: {e}")
        raise
    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == '__main__':
    main()