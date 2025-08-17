import firebase_admin
from firebase_admin import credentials, db
from flask import Flask, jsonify
import os
import json
from datetime import datetime, timedelta
import numpy as np
from collections import Counter, defaultdict, deque
import random
import statistics
import time

# ------------------- Setup Firebase -------------------
key_json = os.getenv('FIREBASE_KEY_JSON')
if not key_json:
    raise ValueError("FIREBASE_KEY_JSON environment variable is missing.")

cred = credentials.Certificate(json.loads(key_json))
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://web-admin-e297c-default-rtdb.asia-southeast1.firebasedatabase.app'
})

# ------------------- Config & Globals -------------------
app = Flask(__name__)
pattern_tracker = {
    'current_streak': 0,
    'last_type': None,
    'streak_type': None,
    'last_numbers': deque(maxlen=4),
    'zero_nine_history': deque(maxlen=20),
    'trap_patterns': defaultdict(int)
}

NUMBER_TYPES = {
    0: {'range': 'SMALL', 'color': 'VIOLET', 'group': '0/9'},
    1: {'range': 'SMALL', 'color': 'GREEN', 'group': '1-4'},
    2: {'range': 'SMALL', 'color': 'RED', 'group': '1-4'},
    3: {'range': 'SMALL', 'color': 'GREEN', 'group': '1-4'},
    4: {'range': 'SMALL', 'color': 'RED', 'group': '1-4'},
    5: {'range': 'BIG', 'color': 'GREEN', 'group': '5-9'},
    6: {'range': 'BIG', 'color': 'RED', 'group': '5-9'},
    7: {'range': 'BIG', 'color': 'GREEN', 'group': '5-9'},
    8: {'range': 'BIG', 'color': 'RED', 'group': '5-9'},
    9: {'range': 'BIG', 'color': 'GREEN', 'group': '0/9'}
}

# ------------------- Core Logic (shortened) -------------------
def fetch_data():
    return db.reference('satta_results').get() or {}

def detect_trap_patterns(numbers):
    if len(numbers) >= 3:
        last_three = numbers[-3:]
        types = ['B' if n >= 5 else 'S' for n in last_three]
        pattern = ''.join(types)
        if pattern in ['SSB', 'BBS']:
            pattern_tracker['trap_patterns'][pattern] += 1
            return True, pattern
    return False, None

def analyze(data):
    results = sorted(data.values(), key=lambda x: x['timestamp'])
    numbers = [r['result_number'] for r in results]
    total = len(numbers)
    analysis = {
        'all_numbers': numbers,
        'total_results': total,
        'group_frequency': Counter(NUMBER_TYPES[n]['group'] for n in numbers),
        'hot_numbers': [],
        'cold_numbers': [],
        'statistical_analysis': {},
        'final_weights': [1.0] * 10
    }

    if numbers:
        counts = Counter(numbers[-100:])
        analysis['hot_numbers'] = [n for n, _ in counts.most_common(3)]
        analysis['cold_numbers'] = [n for n, _ in counts.most_common()[-3:]]
        mean = statistics.mean(numbers)
        stdev = statistics.stdev(numbers) if total > 1 else 0
        analysis['statistical_analysis'] = {
            'mean': mean,
            'stdev': stdev,
            'median': statistics.median(numbers)
        }

        # Manual skew & kurtosis
        if total > 2 and stdev != 0:
            skew = sum(((x - mean) / stdev) ** 3 for x in numbers) * (total / ((total - 1) * (total - 2)))
            kurt = sum(((x - mean) / stdev) ** 4 for x in numbers) * (total * (total + 1)) / ((total - 1) * (total - 2) * (total - 3)) - (3 * (total - 1) ** 2) / ((total - 2) * (total - 3))
            analysis['statistical_analysis']['skew'] = skew
            analysis['statistical_analysis']['kurtosis'] = kurt

    return analysis

def generate_outcome(analysis):
    weights = [1.0] * 10
    for n in analysis['hot_numbers']: weights[n] *= 0.7
    for n in analysis['cold_numbers']: weights[n] *= 1.5
    total = analysis['total_results']
    gcount = analysis['group_frequency']
    zero_nine_ratio = gcount.get('0/9', 0) / total if total else 0
    if zero_nine_ratio < 0.1:
        weights[0] *= 1.8; weights[9] *= 1.8
    elif zero_nine_ratio > 0.2:
        weights[0] *= 0.5; weights[9] *= 0.5

    if pattern_tracker['current_streak'] >= 3:
        rng = range(0, 5) if pattern_tracker['streak_type'] == 'BIG' else range(5, 10)
        for i in rng: weights[i] *= 1.5

    trap, pattern = detect_trap_patterns(analysis['all_numbers'])
    if trap:
        if pattern == 'SSB': weights[0] *= 0.3; weights[9] *= 0.3
        if pattern == 'BBS': [weights.__setitem__(i, weights[i]*0.4) for i in range(5,10)]

    total_weight = sum(weights)
    normalized = [w/total_weight for w in weights]
    result = random.choices(range(10), weights=normalized, k=1)[0]
    return {
        "result_number": result,
        "type": "BIG" if result >= 5 else "SMALL",
        "color": NUMBER_TYPES[result]['color'],
        "group": NUMBER_TYPES[result]['group'],
        "weights": [round(w, 2) for w in normalized],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ------------------- Flask Web Route -------------------
@app.route('/')
def index():
    data = fetch_data()
    analysis = analyze(data)
    outcome = generate_outcome(analysis)
    return jsonify(outcome)

# ------------------- Start -------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
