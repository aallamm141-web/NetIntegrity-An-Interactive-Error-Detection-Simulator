"""
analyze.py
==========
Command-line interface for the Network Error Detection Analyzer.
Runs the simulation, prints a report, and saves charts to output/.

Usage:
    python analyze.py
    python analyze.py --rates 1 25 --steps 25 --trials 800
"""

import argparse
import json
import os
import sys
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np

# same directory imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from error_detection import run_simulation, simulate_single, TECHNIQUES

OUT = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(OUT, exist_ok=True)

BG   = '#080c12'; PANEL='#0d1420'; GRID='#1a2640'; TEXT='#c8d8f0'; MUTED='#5a7299'
C    = {'Parity Check':'#ff6b6b','Checksum':'#4ecdc4','CRC-16':'#45b7d1'}


def _style(fig, axes):
    fig.patch.set_facecolor(BG)
    for ax in (axes if hasattr(axes,'__iter__') else [axes]):
        ax.set_facecolor(PANEL)
        for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
            item.set_color(TEXT)
        ax.tick_params(colors=MUTED)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.grid(color=GRID, lw=0.6, ls='--', alpha=0.9)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    print(f'  [✓] {p}')
    return p


def plot_detection(results):
    fig, ax = plt.subplots(figsize=(9,5))
    _style(fig, ax)
    for name, d in results.items():
        ax.plot([r*100 for r in d['error_rates']],
                [v*100 for v in d['detection_rates']],
                color=C[name], lw=2.4, marker='o', ms=4, label=name)
    ax.set(xlabel='Bit Error Rate (%)', ylabel='Detection Rate (%)',
           title='Detection Rate vs Bit Error Rate', ylim=(0,108))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=10)
    return save(fig, 'plot1_detection_rate.png')


def plot_undetected(results):
    fig, ax = plt.subplots(figsize=(9,5))
    _style(fig, ax)
    for name, d in results.items():
        ax.plot([r*100 for r in d['error_rates']],
                [v*100 for v in d['undetected_rates']],
                color=C[name], lw=2.4, marker='s', ms=4, ls='--', label=name)
    ax.set(xlabel='Bit Error Rate (%)', ylabel='Undetected Rate (%)',
           title='Undetected Error Rate vs Bit Error Rate', ylim=(0,108))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=10)
    return save(fig, 'plot2_undetected_rate.png')


def plot_bar(results):
    key_rates = [0.01, 0.05, 0.10, 0.15, 0.20]
    bar_labels = [f"{int(r*100)}%" for r in key_rates]
    techniques = list(results.keys())
    x = np.arange(len(bar_labels)); width = 0.22

    fig, ax = plt.subplots(figsize=(10,5))
    _style(fig, ax)
    for j, name in enumerate(techniques):
        rates = results[name]['error_rates']
        vals = [results[name]['detection_rates'][
                    min(range(len(rates)), key=lambda i: abs(rates[i]-kr))] * 100
                for kr in key_rates]
        bars = ax.bar(x + (j-1)*width, vals, width, label=name,
                      color=C[name], alpha=0.88, edgecolor=BG, lw=0.5)
        for bar in bars:
            h = bar.get_height()
            ax.annotate(f'{h:.0f}%',
                        xy=(bar.get_x()+bar.get_width()/2, h),
                        xytext=(0,3), textcoords='offset points',
                        ha='center', va='bottom', color=TEXT, fontsize=8)
    ax.set(xticks=x, xticklabels=bar_labels,
           xlabel='Bit Error Rate', ylabel='Detection Rate (%)',
           title='Technique Comparison at Key Error Rates', ylim=(0,118))
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=10)
    return save(fig, 'plot3_bar_comparison.png')


def plot_heatmap(results):
    techs = list(results.keys())
    rates = results[techs[0]]['error_rates']
    matrix = np.array([[results[t]['detection_rates'][i]*100
                        for i in range(len(rates))] for t in techs])

    fig, ax = plt.subplots(figsize=(14,3.5))
    _style(fig, ax)
    im = ax.imshow(matrix, aspect='auto', cmap='RdYlGn', vmin=0, vmax=100)
    ax.set_xticks(range(len(rates)))
    ax.set_xticklabels([f"{r*100:.0f}%" for r in rates], rotation=45, ha='right', fontsize=8)
    ax.set_yticks(range(len(techs)))
    ax.set_yticklabels(techs, fontsize=10)
    ax.set_title('Detection Rate Heatmap', fontsize=13, fontweight='bold', color=TEXT)
    for i in range(len(techs)):
        for j in range(len(rates)):
            v = matrix[i,j]
            ax.text(j, i, f'{v:.0f}', ha='center', va='center',
                    color='black' if 25<v<80 else 'white', fontsize=7, fontweight='bold')
    cbar = fig.colorbar(im, ax=ax, pad=0.01)
    cbar.ax.tick_params(colors=TEXT); cbar.set_label('Detection %', color=TEXT, fontsize=9)
    return save(fig, 'plot4_heatmap.png')


def print_report(results, single, elapsed):
    sep = '═' * 62
    print(f'\n{sep}')
    print('  NETWORK ERROR DETECTION ANALYZER – SIMULATION REPORT')
    print(sep)
    print(f'  Simulation time : {elapsed:.2f}s')
    print(f'  Techniques      : {", ".join(results.keys())}')
    print()
    for name, d in results.items():
        dr = d['detection_rates']
        avg  = sum(dr)/len(dr)*100
        peak = max(dr)*100
        worst= min(dr)*100
        oh   = TECHNIQUES[name].overhead_bits
        print(f'  ▸ {name}')
        print(f'    Avg Detection Rate   : {avg:.1f}%')
        print(f'    Peak / Worst         : {peak:.1f}% / {worst:.1f}%')
        print(f'    Overhead             : +{oh} bit{"s" if oh>1 else ""}')
        print()

    print('─' * 62)
    print("  SINGLE TRANSMISSION EXAMPLE  (msg='Hello!', rate=5%)")
    print('─' * 62)
    for name, info in single.items():
        status = '✓ DETECTED' if info['error_detected'] else ('✗ MISSED' if info['errors_injected'] else 'NO ERRORS')
        print(f"  {name:15s} | {info['original_bits']:3d}→{info['encoded_bits']:3d} bits"
              f" | errors: {info['errors_injected']:2d} | {status}"
              f" | received: '{info['received_msg']}'")
    print(sep + '\n')


def main():
    parser = argparse.ArgumentParser(description='Network Error Detection Analyzer')
    parser.add_argument('--rates', nargs=2, type=float, default=[1, 20],
                        metavar=('MIN', 'MAX'), help='Error rate range in percent')
    parser.add_argument('--steps',  type=int, default=20, help='Number of rate steps')
    parser.add_argument('--trials', type=int, default=600, help='Trials per rate')
    args = parser.parse_args()

    error_rates = [args.rates[0]/100 + i*(args.rates[1]-args.rates[0])/100/(args.steps-1)
                   for i in range(args.steps)]

    print(f'\n{"="*55}')
    print('  Network Error Detection Analyzer — CLI Mode')
    print(f'{"="*55}')
    print(f'  Error rates: {args.rates[0]:.0f}% → {args.rates[1]:.0f}%  ({args.steps} steps)')
    print(f'  Trials/rate: {args.trials}')
    print()

    print('[1/3] Running Monte-Carlo simulation...')
    t0 = time.time()
    results = run_simulation(error_rates, trials=args.trials)
    elapsed = time.time() - t0

    print('[2/3] Simulating single transmission...')
    single = simulate_single('Hello!', 0.05)

    print('[3/3] Generating plots...')
    plot_detection(results)
    plot_undetected(results)
    plot_bar(results)
    plot_heatmap(results)

    # save JSON
    json_path = os.path.join(OUT, 'results.json')
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'  [✓] {json_path}')

    print_report(results, single, elapsed)
    print(f'  All output saved to: {OUT}\n')


if __name__ == '__main__':
    main()
