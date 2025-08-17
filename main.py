import firebase_admin
from firebase_admin import credentials, db
import time
from datetime import datetime, timedelta
import numpy as np
from collections import Counter, defaultdict, deque
import random
import statistics
from scipy import stats
import math
import json
import os

# Initialize Firebase from environment variable
service_account_info = json.loads(os.environ['FIREBASE_KEY_JSON'])
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://web-admin-e297c-default-rtdb.asia-southeast1.firebasedatabase.app'
})

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

pattern_tracker = {
    'current_streak': 0,
    'last_type': None,
    'streak_type': None,
    'last_numbers': deque(maxlen=4),
    'zero_nine_history': deque(maxlen=20),
    'trap_patterns': defaultdict(int)
}

def fetch_historical_data():
    ref = db.reference('satta_results')
    results = ref.get()
    return results or {}

def print_analysis_header(analysis):
    print("\n" + "="*80)
    print(" "*30 + "COMPLETE ANALYSIS REPORT")
    print("="*80)
    num_counts = analysis.get('number_frequency', {})
    for num in sorted(num_counts.keys()):
        details = NUMBER_TYPES[num]
        print(f"Number {num}: {details['color']} {details['range']} - {num_counts[num]} times ({num_counts[num]/analysis['total_results']:.1%})")
    print("\n[2] HOT/COLD NUMBERS (LAST 100):")
    print(f"Hot Numbers: {analysis.get('hot_numbers', [])}")
    print(f"Cold Numbers: {analysis.get('cold_numbers', [])}")
    print("\n[3] GROUP ANALYSIS:")
    for group, count in analysis.get('group_frequency', {}).items():
        print(f"{group}: {count} times ({count/analysis['total_results']:.1%})")
    print("\n[4] PATTERN ANALYSIS:")
    print("Last 5 numbers:", list(pattern_tracker['last_numbers']))
    print("Current streak:", f"{pattern_tracker['streak_type']} {pattern_tracker['current_streak']}")
    print("\n[5] 0/9 ANALYSIS:")
    zero_nine_count = analysis['group_frequency'].get('0/9', 0)
    print(f"0/9 appeared {zero_nine_count} times ({zero_nine_count/analysis['total_results']:.1%})")
    print("Last 0/9 sequence:", list(pattern_tracker['zero_nine_history']))
    print("\n[6] TRAP PATTERNS DETECTED:")
    for pattern, count in analysis.get('trap_patterns', {}).items():
        print(f"{pattern}: {count} times")
    print("\n[7] ADVANCED STATISTICS:")
    stats_data = analysis.get('statistical_analysis', {})
    print(f"Mean: {stats_data.get('mean', 0):.2f}")
    print(f"Median: {stats_data.get('median', 0)}")
    print(f"Standard Deviation: {stats_data.get('stdev', 0):.2f}")
    print(f"Skewness: {stats_data.get('skewness', 0):.2f}")
    print(f"Kurtosis: {stats_data.get('kurtosis', 0):.2f}")
    print("\n[8] WEIGHT ADJUSTMENTS:")
    weights = analysis.get('final_weights', [1]*10)
    for num, weight in enumerate(weights):
        print(f"Number {num}: {weight:.2f}x")
    print("="*80 + "\n")

def detect_trap_patterns(numbers):
    if len(numbers) >= 3:
        last_three = numbers[-3:]
        types = ['B' if n >=5 else 'S' for n in last_three]
        pattern = ''.join(types)
        if pattern in ['SSB', 'BBS']:
            pattern_tracker['trap_patterns'][pattern] += 1
            return True, pattern
    return False, None

def analyze_patterns(data):
    sorted_results = sorted(data.values(), key=lambda x: x['timestamp'])
    numbers = [res['result_number'] for res in sorted_results]
    analysis = {
        'all_numbers': numbers,
        'total_results': len(numbers),
        'number_frequency': Counter(numbers),
        'group_frequency': Counter(NUMBER_TYPES[n]['group'] for n in numbers),
        'recent_trends': numbers[-100:] if len(numbers) >= 100 else numbers,
        'hot_numbers': [],
        'cold_numbers': [],
        'statistical_analysis': {},
        'final_weights': [1.0]*10
    }
    recent_counts = Counter(analysis['recent_trends'])
    analysis['hot_numbers'] = [num for num, count in recent_counts.most_common(3)]
    analysis['cold_numbers'] = [num for num, count in recent_counts.most_common()[-3:]]
    if numbers:
        analysis['statistical_analysis'] = {
            'mean': statistics.mean(numbers),
            'median': statistics.median(numbers),
            'stdev': statistics.stdev(numbers) if len(numbers) > 1 else 0,
            'skewness': stats.skew(numbers) if len(numbers) > 2 else 0,
            'kurtosis': stats.kurtosis(numbers) if len(numbers) > 3 else 0
        }
    if numbers:
        last_num = numbers[-1]
        current_type = 'BIG' if last_num >= 5 else 'SMALL'
        current_group = NUMBER_TYPES[last_num]['group']
        if pattern_tracker['last_type'] == current_type:
            pattern_tracker['current_streak'] += 1
        else:
            pattern_tracker['current_streak'] = 1
            pattern_tracker['streak_type'] = current_type
        pattern_tracker['last_type'] = current_type
        pattern_tracker['last_numbers'].append(last_num)
        if current_group == '0/9':
            pattern_tracker['zero_nine_history'].append(last_num)
        detect_trap_patterns(numbers)
    return analysis

def generate_outcome(analysis):
    weights = [1.0] * 10
    for num in analysis.get('hot_numbers', []):
        weights[num] *= 0.7
    for num in analysis.get('cold_numbers', []):
        weights[num] *= 1.5
    group_counts = analysis.get('group_frequency', {})
    total = analysis['total_results']
    zero_nine_ratio = group_counts.get('0/9', 0) / total if total > 0 else 0
    if zero_nine_ratio < 0.1:
        weights[0] *= 1.8
        weights[9] *= 1.8
    elif zero_nine_ratio > 0.2:
        weights[0] *= 0.5
        weights[9] *= 0.5
    if pattern_tracker['current_streak'] >= 3:
        if pattern_tracker['streak_type'] == 'BIG':
            for num in range(5):
                weights[num] *= 1.5
        else:
            for num in range(5, 10):
                weights[num] *= 1.5
    trap_detected, trap_pattern = detect_trap_patterns(analysis['all_numbers'])
    if trap_detected:
        if trap_pattern == 'SSB':
            weights[0] *= 0.3
            weights[9] *= 0.3
        elif trap_pattern == 'BBS':
            for num in range(5, 10):
                weights[num] *= 0.4
    total_weight = sum(weights)
    normalized_weights = [w/total_weight for w in weights]
    analysis['final_weights'] = normalized_weights
    result = random.choices(range(10), weights=normalized_weights, k=1)[0]
    result_type = 'BIG' if result >= 5 else 'SMALL'
    result_color = NUMBER_TYPES[result]['color']
    result_group = NUMBER_TYPES[result]['group']
    if result in [0, 9]:
        if len(pattern_tracker['zero_nine_history']) > 0:
            zero_nine_status = "BREAK" if result == pattern_tracker['zero_nine_history'][-1] else "START"
        else:
            zero_nine_status = "START"
    else:
        zero_nine_status = "N/A"
    return {
        'result_number': result,
        'type': result_type,
        'color': result_color,
        'group': result_group,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'zero_nine_status': zero_nine_status,
        'streak_status': f"{pattern_tracker['streak_type']} {pattern_tracker['current_streak']}",
        'weights': [round(w, 2) for w in normalized_weights]
    }

def game_loop():
    print("Starting advanced game engine...")
    historical_data = fetch_historical_data()
    while True:
        try:
            analysis = analyze_patterns(historical_data)
            outcome = generate_outcome(analysis)
            print_analysis_header(analysis)
            print(f"\nTIME STAMP: {outcome['timestamp']}")
            print(f"RESULT: {outcome['type']} {outcome['result_number']} {outcome['color']}")
            print(f"GROUP: {outcome['group']} | 0/9 STATUS: {outcome['zero_nine_status']}")
            print(f"STREAK: {outcome['streak_status']}")
            print(f"WEIGHTS USED: {outcome['weights']}\n")
            ref = db.reference('DEVIL_V1')
            new_result_ref = ref.push()
            save_data = {k: v for k, v in outcome.items() if k not in ['weights']}
            new_result_ref.set(save_data)
            historical_data[new_result_ref.key] = save_data
            now = datetime.now()
            next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
            sleep_time = (next_minute - now).total_seconds()
            time.sleep(max(0, sleep_time))
        except Exception as e:
            print(f"Error in game loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    game_loop()