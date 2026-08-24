import os
import json
import re
from pathlib import Path
from collections import Counter

def build_dictionary_from_book():
    dir_path = Path("output/TRIBES INDIA")
    word_counts = Counter()
    
    if not dir_path.exists():
        return set()
        
    for f in dir_path.glob("page_*.json"):
        # Skip the pages we know are blank or newly OCR'd
        page_num = int(f.stem.split("_")[1])
        if page_num in [10, 12, 13, 14, 15, 16, 17, 18, 50, 51, 82, 83, 84, 191, 196, 198, 199, 200, 205, 206, 240, 263, 281, 290]:
            continue
            
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                for block in data.get("text_blocks", []):
                    text = block.get("text", "")
                    # Extract words
                    words = re.findall(r"\b[a-zA-Z]{2,}\b", text.lower())
                    word_counts.update(words)
        except Exception:
            pass
            
    # Keep words that appear at least once
    dictionary = set(word_counts.keys())
    
    # Add common short words just in case
    dictionary.update(["a", "an", "the", "in", "on", "at", "to", "of", "and", "or", "is", "was", "for", "by", "as", "it", "he", "she", "they", "we", "us", "him", "her", "his", "their", "them", "who", "whom", "its", "our", "you", "your"])
    
    # Common UPSC History/Anthropology keywords to support custom scans
    COMMON_UPSC_KEYWORDS = [
        "indus", "harappa", "harappan", "munda", "naga", "nagas", "tribal", "india", "today", "british", "colonial", 
        "ryotwari", "zamindari", "revolt", "struggle", "independence", "anthropology", "anthropologist", "culture", 
        "racial", "origin", "prehistoric", "history", "civilization", "archaeological", "palaeontological", "mohenjodaro", 
        "aryans", "aryan", "rigvedic", "dasas", "dasyus", "asuras", "hinduism", "sanskrit", "brahmin", "caste", "castes", 
        "chandalas", "buddha", "ashoka", "maurya", "gupta", "mughal", "delhi", "sultanate", "gandhi", "nehru", "congress", 
        "national", "movement", "santhal", "oraon", "gond", "bhil", "todas", "khasi", "garo", "jaintia", "kuki", "chenchu", 
        "kadmbari", "panchatantra", "puran", "vedic", "ramayan", "mahabharat", "elwin", "ghurye", "srinivas", "dube", 
        "majumdar", "bose", "guha", "risley"
    ]
    dictionary.update(COMMON_UPSC_KEYWORDS)
    
    return dictionary

def split_run_together_word(s: str, word_set: set) -> str:
    # If the word is already a valid word in dictionary, don't split
    if s.lower() in word_set:
        return s
        
    memo = {}
    
    def solve(sub):
        if not sub:
            return []
        if sub in memo:
            return memo[sub]
            
        best = None
        for i in range(1, len(sub) + 1):
            prefix = sub[:i]
            if prefix in word_set or (len(prefix) == 1 and prefix in ["a", "i"]):
                suffix_splits = solve(sub[i:])
                if suffix_splits is not None:
                    cand = [prefix] + suffix_splits
                    if best is None or len(cand) < len(best):
                        best = cand
        memo[sub] = best
        return best

    splits = solve(s.lower())
    if splits:
        return " ".join(splits)
    return s

def clean_sentence_locally(sentence: str, word_set: set) -> str:
    # Find all tokens and split if they are run-together
    tokens = sentence.split()
    cleaned_tokens = []
    for token in tokens:
        # Strip punctuation for lookup, but preserve it in output
        clean_match = re.match(r"^([^\w]*)(.*?)([^\w]*)$", token)
        if clean_match:
            prefix, word, suffix = clean_match.groups()
            if len(word) > 7 and not word.lower() in word_set:
                # Try splitting
                split_word = split_run_together_word(word, word_set)
                cleaned_tokens.append(f"{prefix}{split_word}{suffix}")
            else:
                cleaned_tokens.append(token)
        else:
            cleaned_tokens.append(token)
            
    return " ".join(cleaned_tokens)

def main():
    print("Building dictionary from other pages...")
    dictionary = build_dictionary_from_book()
    print(f"Dictionary size: {len(dictionary)} words")
    
    test_word = "briefreviewtheriseand"
    split = split_run_together_word(test_word, dictionary)
    print(f"Test split '{test_word}' -> '{split}'")
    
    test_sentence = "LET us first briefreviewtheriseand fallofIndus valley civilizationand advent"
    cleaned = clean_sentence_locally(test_sentence, dictionary)
    print(f"Test sentence -> '{cleaned}'")

if __name__ == "__main__":
    main()
