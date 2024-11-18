import os
import itertools
import pickle
import random
import time
from tqdm import tqdm
from collections import defaultdict, Counter
from scipy.stats import entropy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from multiprocessing import Pool, cpu_count

N_GUESSES = 6
DICT_FILE_ALL = 'all_words.txt'
DICT_FILE = 'words.txt'

# wordle Browser Setup
def setup_browser():
    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-notifications')
    options.add_argument('--start-maximized')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    service = Service(ChromeDriverManager().install())
    browser = webdriver.Chrome(service=service, options=options)
    browser.get("https://www.nytimes.com/games/wordle/index.html")
    time.sleep(3)
    
    # Close any popups
    close_popups(browser)
    return browser

def close_popups(browser):
    try:
        close_buttons = browser.find_elements(By.CSS_SELECTOR, "button[data-testid='modal-close'], button[aria-label='Close']")
        for button in close_buttons:
            if button.is_displayed():
                button.click()
                time.sleep(1)
    except Exception:
        pass

def calculate_pattern(guess, answer):
    """Determine pattern feedback for a given guess against the answer."""
    pattern, answer_chars = [0] * len(guess), list(answer)
    
    for i, char in enumerate(guess):
        if char == answer[i]:
            pattern[i], answer_chars[i] = 2, None
    
    for i, char in enumerate(guess):
        if pattern[i] == 0 and char in answer_chars:
            pattern[i], answer_chars[answer_chars.index(char)] = 1, None
    return tuple(pattern)

def convert_feedback(feedback):
    """Convert feedback from Wordle interface to numerical pattern."""
    state_map = {'correct': 2, 'present': 1, 'absent': 0}
    return tuple(state_map[state] for state in feedback)

# Entering Guesses and Retrieving Feedback
def input_guess(browser, guess):
    """Submit a guess into the Wordle game on the browser."""
    try:
        body = browser.find_element(By.TAG_NAME, "body")
        for char in guess:
            body.send_keys(char)
            time.sleep(0.1)
        body.send_keys(Keys.RETURN)
        return True
    except Exception as e:
        print(f"Error entering guess: {e}")
        return False

def retrieve_feedback(browser, attempt):
    """Extract feedback from the Wordle interface after a guess."""
    time.sleep(2)
    try:
        rows = browser.find_elements(By.CSS_SELECTOR, "div[class*='Row-module_row__']")
        tiles = rows[attempt - 1].find_elements(By.CSS_SELECTOR, "div[class*='Tile-module_tile__']")
        return [tile.get_attribute('data-state') for tile in tiles]
    except Exception as e:
        print(f"Error retrieving feedback: {e}")
        return None

# Dictionary Handling
def load_dictionaries():
    """Load dictionary words from text files."""
    with open(DICT_FILE_ALL) as f:
        all_words = [word.strip() for word in f]
    with open(DICT_FILE) as f:
        main_words = [word.strip() for word in f]
    return all_words, main_words

def generate_patterns_dict(words):
    """Generate a dictionary mapping each word to patterns against other words."""
    pattern_dict = defaultdict(lambda: defaultdict(set))
    for word in tqdm(words):
        for answer in words:
            pattern = calculate_pattern(word, answer)
            pattern_dict[word][pattern].add(answer)
    return dict(pattern_dict)

# Entropy Calculation
def compute_entropy(word, possible_words):
    """Calculate the entropy for a specific word against possible words."""
    patterns = Counter(calculate_pattern(word, w) for w in possible_words)
    return word, entropy(list(patterns.values()))

def calculate_entropies(words, possible_words):
    """Compute entropies for a list of words using multiprocessing."""
    with Pool(min(cpu_count(), len(words))) as pool:
        return dict(pool.starmap(compute_entropy, [(word, possible_words) for word in words]))

# Main Solver Logic
def wordle_solver(browser, all_words, main_words):
    """Solve the Wordle puzzle by iteratively guessing based on feedback."""
    possible_words = set(all_words)

    for attempt in range(1, N_GUESSES + 1):
        print(f"\nAttempt {attempt}/{N_GUESSES}")
        print(f"Words remaining: {len(possible_words)}")

        entropies = calculate_entropies(main_words if len(possible_words) > 2 else possible_words, possible_words)
        guess = max(entropies, key=entropies.get)
        
        if not input_guess(browser, guess):
            break
        
        feedback = retrieve_feedback(browser, attempt)
        if feedback is None:
            break
        
        pattern = convert_feedback(feedback)
        print(f"Pattern: {pattern}")
        
        if all(state == 'correct' for state in feedback):
            print(f"Solved in {attempt} attempts!")
            return

        possible_words = {word for word in possible_words if calculate_pattern(guess, word) == pattern}

    print("No possible words remaining or failed to solve.")

# Main Entry Point
def main():
    browser = setup_browser()
    all_words, main_words = load_dictionaries()
    pattern_dict = generate_patterns_dict(all_words) if 'pattern_dict.p' not in os.listdir() else pickle.load(open('pattern_dict.p', 'rb'))
    
    try:
        wordle_solver(browser, all_words, main_words)
        time.sleep(5)
    finally:
        browser.quit()

if __name__ == "__main__":
    main()
