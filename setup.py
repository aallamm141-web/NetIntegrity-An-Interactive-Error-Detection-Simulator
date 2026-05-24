#!/usr/bin/env python3
"""
setup.py  —  Network Error Detection Analyzer
==============================================
Run this ONCE on your machine. It creates every project file:
    python setup.py

Then start the server:
    python server.py
    # Open → http://localhost:5000
"""

import os, sys, textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, 'static')
os.makedirs(STATIC, exist_ok=True)
os.makedirs(os.path.join(ROOT, 'output'), exist_ok=True)

# ══════════════════════════════════════════════════════════════════════
# 1. error_detection.py
# ══════════════════════════════════════════════════════════════════════
ED = r'''
import random
from typing import List, Tuple

def str_to_bits(data):
    bits = []
    for ch in data:
        for b in format(ord(ch),'08b'): bits.append(int(b))
    return bits

def bits_to_str(bits):
    chars=[]
    for i in range(0,len(bits)-len(bits)%8,8):
        chars.append(chr(int(''.join(map(str,bits[i:i+8])),2)))
    return ''.join(chars)

def introduce_errors(bits, rate):
    corrupted=bits.copy(); flipped=[]
    for i in range(len(corrupted)):
        if random.random()<rate: corrupted[i]^=1; flipped.append(i)
    return corrupted, flipped

def _xor(a,b): return [x^y for x,y in zip(a,b)]

class ParityCheck:
    name="Parity Check"; overhead_bits=1
    @staticmethod
    def _p(bits): return sum(bits)%2
    @staticmethod
    def encode(bits): return bits+[ParityCheck._p(bits)]
    @staticmethod
    def detect(bits):
        if len(bits)<1: return False
        return ParityCheck._p(bits[:-1])!=bits[-1]

class Checksum:
    name="Checksum"; overhead_bits=16
    @staticmethod
    def _words(bits):
        p=bits+[0]*((-len(bits))%16)
        return [int(''.join(map(str,p[i:i+16])),2) for i in range(0,len(p),16)]
    @staticmethod
    def _compute(bits):
        t=0
        for w in Checksum._words(bits):
            t+=w
            if t>0xFFFF: t=(t&0xFFFF)+(t>>16)
        return (~t)&0xFFFF
    @staticmethod
    def _i2b(n): return [int(b) for b in format(n&0xFFFF,'016b')]
    @staticmethod
    def encode(bits): return bits+Checksum._i2b(Checksum._compute(bits))
    @staticmethod
    def detect(bits):
        if len(bits)<16: return False
        return Checksum._compute(bits[:-16])!=int(''.join(map(str,bits[-16:])),2)

class CRC:
    name="CRC-16"; overhead_bits=16
    POLY=[1,0,0,0,1,0,0,0,0,0,0,1,0,0,0,0,1]
    @staticmethod
    def _div(dividend,divisor):
        n=len(divisor); cur=list(dividend[:n])
        for i in range(n,len(dividend)+1):
            if cur[0]==1: cur=_xor(cur,divisor)
            cur=cur[1:]
            if i<len(dividend): cur.append(dividend[i])
        return cur
    @staticmethod
    def encode(bits): return bits+CRC._div(bits+[0]*16,CRC.POLY)
    @staticmethod
    def detect(bits):
        if len(bits)<16: return False
        return any(b!=0 for b in CRC._div(bits,CRC.POLY))

TECHNIQUES={"Parity Check":ParityCheck,"Checksum":Checksum,"CRC-16":CRC}
SAMPLE_MESSAGES=["Hello, World!","Network Error Detection","Data Communication Systems",
                 "ABCDEFGHIJKLMNOP","0123456789ABCDEF","The quick brown fox","Error detection test"]

def run_simulation(error_rates, trials=600):
    import random
    results={name:{"error_rates":[],"detection_rates":[],"undetected_rates":[]}
             for name in TECHNIQUES}
    for rate in error_rates:
        for name,tech in TECHNIQUES.items():
            detected=0; total=0
            for _ in range(trials):
                msg=random.choice(SAMPLE_MESSAGES)
                orig=str_to_bits(msg); enc=tech.encode(orig)
                corr,flipped=introduce_errors(enc,rate)
                if not flipped: continue
                total+=1
                if tech.detect(corr): detected+=1
            det=detected/total if total else 0.0
            results[name]["error_rates"].append(round(rate,4))
            results[name]["detection_rates"].append(round(det,6))
            results[name]["undetected_rates"].append(round(1-det,6))
    return results

def simulate_single(message, error_rate):
    orig=str_to_bits(message); output={}
    for name,tech in TECHNIQUES.items():
        enc=tech.encode(orig); corr,flipped=introduce_errors(enc,error_rate)
        detected=tech.detect(corr) if flipped else False
        try: recv=bits_to_str(corr[:len(orig)])
        except: recv="???"
        output[name]={"original_bits":len(orig),"encoded_bits":len(enc),
                      "overhead_bits":tech.overhead_bits,"errors_injected":len(flipped),
                      "error_positions":flipped[:20],"error_detected":detected,
                      "received_msg":recv,"original_msg":message}
    return output
'''

# ══════════════════════════════════════════════════════════════════════
# 2. server.py
# ══════════════════════════════════════════════════════════════════════
SRV = r'''
import io, os, base64, time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
from flask import Flask, request, jsonify
from error_detection import run_simulation, simulate_single, TECHNIQUES

app = Flask(__name__, static_folder='static')

BG='#080c12'; PANEL='#0d1420'; GRID='#1a2640'; TEXT='#c8d8f0'; MUTED='#5a7299'
C={'Parity Check':'#ff6b6b','Checksum':'#4ecdc4','CRC-16':'#45b7d1'}

def _style(fig, axes):
    fig.patch.set_facecolor(BG)
    for ax in (axes if hasattr(axes,'__iter__') else [axes]):
        ax.set_facecolor(PANEL)
        for item in [ax.title,ax.xaxis.label,ax.yaxis.label]: item.set_color(TEXT)
        ax.tick_params(colors=MUTED)
        for spine in ax.spines.values(): spine.set_color(GRID)
        ax.grid(color=GRID,lw=0.6,ls='--',alpha=0.9)

def fig_b64(fig):
    buf=io.BytesIO(); fig.savefig(buf,format='png',dpi=130,bbox_inches='tight',facecolor=BG)
    plt.close(fig); buf.seek(0); return base64.b64encode(buf.read()).decode()

def plot_detection(results):
    fig,ax=plt.subplots(figsize=(8,4.5)); _style(fig,ax)
    for name,d in results.items():
        ax.plot([r*100 for r in d['error_rates']],[v*100 for v in d['detection_rates']],
                color=C[name],lw=2.4,marker='o',ms=4,label=name)
    ax.set(xlabel='Bit Error Rate (%)',ylabel='Detection Rate (%)',
           title='Detection Rate vs Bit Error Rate',ylim=(0,108))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(facecolor=PANEL,edgecolor=GRID,labelcolor=TEXT,fontsize=10)
    return fig_b64(fig)

def plot_undetected(results):
    fig,ax=plt.subplots(figsize=(8,4.5)); _style(fig,ax)
    for name,d in results.items():
        ax.plot([r*100 for r in d['error_rates']],[v*100 for v in d['undetected_rates']],
                color=C[name],lw=2.4,marker='s',ms=4,ls='--',label=name)
    ax.set(xlabel='Bit Error Rate (%)',ylabel='Undetected Rate (%)',
           title='Undetected Error Rate vs Bit Error Rate',ylim=(0,108))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(facecolor=PANEL,edgecolor=GRID,labelcolor=TEXT,fontsize=10)
    return fig_b64(fig)

def plot_bar(results):
    key_rates=[0.01,0.05,0.10,0.15,0.20]
    bar_labels=[f"{int(r*100)}%" for r in key_rates]
    techniques=list(results.keys()); x=np.arange(len(bar_labels)); width=0.22
    fig,ax=plt.subplots(figsize=(9,4.5)); _style(fig,ax)
    for j,name in enumerate(techniques):
        rates=results[name]['error_rates']
        vals=[results[name]['detection_rates'][
              min(range(len(rates)),key=lambda i:abs(rates[i]-kr))]*100
              for kr in key_rates]
        bars=ax.bar(x+(j-1)*width,vals,width,label=name,
                    color=C[name],alpha=0.88,edgecolor=BG,lw=0.5)
        for bar in bars:
            h=bar.get_height()
            ax.annotate(f'{h:.0f}%',xy=(bar.get_x()+bar.get_width()/2,h),
                        xytext=(0,3),textcoords='offset points',
                        ha='center',va='bottom',color=TEXT,fontsize=8)
    ax.set(xticks=x,xticklabels=bar_labels,xlabel='Bit Error Rate',
           ylabel='Detection Rate (%)',title='Technique Comparison at Key Error Rates',ylim=(0,118))
    ax.legend(facecolor=PANEL,edgecolor=GRID,labelcolor=TEXT,fontsize=10)
    return fig_b64(fig)

def plot_heatmap(results):
    techs=list(results.keys()); rates=results[techs[0]]['error_rates']
    matrix=np.array([[results[t]['detection_rates'][i]*100
                      for i in range(len(rates))] for t in techs])
    fig,ax=plt.subplots(figsize=(12,3)); _style(fig,ax)
    im=ax.imshow(matrix,aspect='auto',cmap='RdYlGn',vmin=0,vmax=100)
    ax.set_xticks(range(len(rates)))
    ax.set_xticklabels([f"{r*100:.0f}%" for r in rates],rotation=45,ha='right',fontsize=8)
    ax.set_yticks(range(len(techs))); ax.set_yticklabels(techs,fontsize=10)
    ax.set_title('Detection Rate Heatmap',fontsize=13,fontweight='bold',color=TEXT)
    for i in range(len(techs)):
        for j in range(len(rates)):
            v=matrix[i,j]
            ax.text(j,i,f'{v:.0f}',ha='center',va='center',
                    color='black' if 25<v<80 else 'white',fontsize=7,fontweight='bold')
    cbar=fig.colorbar(im,ax=ax,pad=0.01)
    cbar.ax.tick_params(colors=TEXT); cbar.set_label('Detection %',color=TEXT,fontsize=9)
    return fig_b64(fig)

@app.route('/')
def index():
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'static','index.html')
    with open(path,encoding='utf-8') as f: return f.read()

@app.route('/api/simulate', methods=['POST'])
def api_simulate():
    body=request.get_json(force=True,silent=True) or {}
    min_r=float(body.get('min_rate',1)); max_r=float(body.get('max_rate',20))
    steps=int(body.get('steps',20));    trials=int(body.get('trials',600))
    steps=max(steps,2)
    error_rates=[round(min_r/100+i*(max_r-min_r)/100/(steps-1),4) for i in range(steps)]
    t0=time.time(); results=run_simulation(error_rates,trials=trials); elapsed=round(time.time()-t0,2)
    summary={}
    for name,d in results.items():
        dr=d['detection_rates']
        summary[name]={'avg_detection':round(sum(dr)/len(dr)*100,1),
                       'min_detection':round(min(dr)*100,1),
                       'max_detection':round(max(dr)*100,1),
                       'overhead_bits':TECHNIQUES[name].overhead_bits}
    plots={'detection':plot_detection(results),'undetected':plot_undetected(results),
           'bar':plot_bar(results),'heatmap':plot_heatmap(results)}
    return jsonify({'ok':True,'elapsed':elapsed,'trials':trials,
                    'results':results,'summary':summary,'plots':plots})

@app.route('/api/transmit', methods=['POST'])
def api_transmit():
    body=request.get_json(force=True,silent=True) or {}
    message=body.get('message','Hello!')[:64]
    error_rate=float(body.get('error_rate',5))/100
    detail=simulate_single(message,error_rate)
    return jsonify({'ok':True,'detail':detail})

if __name__=='__main__':
    print("="*55)
    print("  Network Error Detection Analyzer")
    print("  Open → http://localhost:5000")
    print("="*55)
    app.run(debug=False,port=5000,host='0.0.0.0')
'''

# ══════════════════════════════════════════════════════════════════════
# 3. static/index.html  (full interactive dashboard)
# ══════════════════════════════════════════════════════════════════════
HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Network Error Detection Analyzer</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap');
:root{
  --bg:#060a0f;--panel:#0b1118;--card:#0e1620;--border:#162030;--border2:#1e3050;
  --c1:#00c8ff;--c2:#ff4060;--c3:#30ff80;
  --parity:#ff6b6b;--chk:#4ecdc4;--crc:#45b7d1;
  --text:#c5d8f0;--muted:#4a6680;
  --mono:'Share Tech Mono',monospace;--sans:'Rajdhani',sans-serif;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:15px;min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(rgba(0,200,255,.03) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(0,200,255,.03) 1px,transparent 1px);
  background-size:48px 48px;}
.wrap{position:relative;z-index:1;max-width:1280px;margin:0 auto;padding:16px 20px 40px}
.topbar{display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid var(--border2);padding-bottom:14px;margin-bottom:24px;}
.logo{font-family:var(--mono);font-size:13px;color:var(--c1);letter-spacing:3px;opacity:.8}
.status-dot{width:8px;height:8px;border-radius:50%;background:var(--c3);
  box-shadow:0 0 10px var(--c3);display:inline-block;margin-right:8px;
  animation:pulse 2s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.status-txt{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:2px}
header{text-align:center;padding:10px 0 28px;position:relative}
header::after{content:'';position:absolute;bottom:0;left:50%;transform:translateX(-50%);
  width:300px;height:1px;background:linear-gradient(90deg,transparent,var(--c1),transparent);}
.header-tag{display:inline-block;font-family:var(--mono);font-size:10px;letter-spacing:4px;
  color:var(--c1);border:1px solid rgba(0,200,255,.3);padding:3px 12px;border-radius:2px;margin-bottom:14px;}
h1{font-size:clamp(22px,4vw,46px);font-weight:700;line-height:1.1;
  background:linear-gradient(135deg,#fff 0%,var(--c1) 55%,var(--crc) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:10px;}
.subtitle{color:var(--muted);font-size:14px;letter-spacing:1px}
.controls-panel{background:var(--panel);border:1px solid var(--border2);border-radius:10px;padding:22px 24px;margin:24px 0;}
.controls-title{font-family:var(--mono);font-size:11px;letter-spacing:3px;color:var(--c1);
  margin-bottom:18px;display:flex;align-items:center;gap:8px;}
.controls-title::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--c1);
  box-shadow:0 0 10px var(--c1);flex-shrink:0;}
.controls-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;align-items:end;}
.ctrl-group{display:flex;flex-direction:column;gap:6px}
.ctrl-label{font-size:10px;letter-spacing:2px;color:var(--muted);text-transform:uppercase}
.ctrl-val{font-family:var(--mono);font-size:12px;color:var(--c1);float:right}
input[type=range]{width:100%;accent-color:var(--c1);cursor:pointer;background:transparent;height:20px;}
input[type=text]{width:100%;background:#060e18;border:1px solid var(--border2);border-radius:5px;
  color:var(--text);font-family:var(--mono);font-size:13px;padding:9px 12px;outline:none;transition:border-color .2s;}
input[type=text]:focus{border-color:var(--c1);box-shadow:0 0 0 2px rgba(0,200,255,.1)}
.btn{padding:10px 24px;border-radius:5px;font-family:var(--sans);font-weight:700;font-size:13px;
  letter-spacing:2px;cursor:pointer;border:none;transition:all .2s;white-space:nowrap;}
.btn-primary{background:linear-gradient(135deg,#003c5a,#006688);border:1px solid var(--c1);
  color:var(--c1);box-shadow:0 0 16px rgba(0,200,255,.2);}
.btn-primary:hover{background:linear-gradient(135deg,#005580,#0099bb);transform:translateY(-1px)}
.btn-primary:disabled{opacity:.4;cursor:not-allowed;transform:none}
.progress-bar{height:3px;background:var(--border);border-radius:2px;margin-top:16px;display:none;overflow:hidden;}
.progress-fill{height:100%;width:0%;background:linear-gradient(90deg,var(--c1),var(--c3));
  border-radius:2px;transition:width .3s ease;}
.loading-msg{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:8px;letter-spacing:1px}
.cards-row{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:24px 0}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;
  padding:18px;position:relative;overflow:hidden;transition:transform .2s;}
.card:hover{transform:translateY(-2px)}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.card.p1::before{background:var(--parity)}.card.p2::before{background:var(--chk)}.card.p3::before{background:var(--crc)}
.card-name{font-size:10px;letter-spacing:2px;color:var(--muted);margin-bottom:10px;text-transform:uppercase}
.card-val{font-size:38px;font-weight:700;line-height:1;margin-bottom:4px;font-family:var(--mono)}
.card.p1 .card-val{color:var(--parity)}.card.p2 .card-val{color:var(--chk)}.card.p3 .card-val{color:var(--crc)}
.card-sub{font-size:11px;color:var(--muted)}
.card-badge{display:inline-block;margin-top:8px;font-size:10px;font-family:var(--mono);
  padding:2px 8px;border-radius:3px;background:rgba(255,255,255,.04);border:1px solid var(--border);color:var(--muted);}
.sk{background:var(--border);border-radius:3px;color:transparent;animation:sk 1.2s ease infinite alternate;}
@keyframes sk{0%{opacity:.4}100%{opacity:.8}}
.plots-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0}
.plot-full{grid-column:1/-1}
.plot-panel{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:20px;position:relative;}
.plot-panel::before{content:'';position:absolute;top:0;left:20px;right:20px;height:1px;
  background:linear-gradient(90deg,transparent,rgba(0,200,255,.3),transparent);}
.plot-title{font-size:11px;letter-spacing:2px;color:var(--c1);text-transform:uppercase;
  margin-bottom:14px;display:flex;align-items:center;gap:8px;font-family:var(--mono);}
.plot-title::before{content:'';width:5px;height:5px;border-radius:50%;
  background:var(--c1);box-shadow:0 0 8px var(--c1);flex-shrink:0;}
.plot-img{width:100%;border-radius:4px;display:block}
.plot-placeholder{height:240px;display:flex;align-items:center;justify-content:center;
  color:var(--muted);font-family:var(--mono);font-size:12px;letter-spacing:2px;
  border:1px dashed var(--border);border-radius:4px;flex-direction:column;gap:10px;}
.plot-placeholder svg{opacity:.3}
.transmit-panel{background:var(--card);border:1px solid var(--border2);border-radius:10px;padding:24px;margin:24px 0;}
.transmit-panel .plot-title{color:var(--c3)}.transmit-panel .plot-title::before{background:var(--c3);box-shadow:0 0 8px var(--c3);}
.tx-controls{display:grid;grid-template-columns:1fr 1fr auto;gap:14px;align-items:end;margin-bottom:20px}
.result-row{display:grid;grid-template-columns:145px 90px 120px 1fr 130px;
  gap:14px;align-items:center;padding:14px 16px;border-radius:6px;margin-bottom:10px;
  border:1px solid var(--border);background:rgba(6,14,24,.6);transition:background .2s;}
.result-row:hover{background:rgba(10,20,36,.8)}
.res-name{font-weight:700;font-size:14px;font-family:var(--sans)}
.res-metric{text-align:center}
.res-metric .lbl{font-size:9px;color:var(--muted);letter-spacing:1.5px;display:block;margin-bottom:3px;text-transform:uppercase}
.res-metric .val{font-family:var(--mono);font-size:13px}
.bits-track{height:5px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden}
.bits-fill{height:100%;border-radius:3px;transition:width .6s ease}
.bits-lbl{font-size:9px;color:var(--muted);margin-top:3px;font-family:var(--mono)}
.status{padding:5px 0;border-radius:4px;font-size:11px;font-weight:700;letter-spacing:2px;text-align:center;font-family:var(--mono);}
.s-ok  {background:rgba(48,255,128,.1);border:1px solid rgba(48,255,128,.35);color:var(--c3)}
.s-miss{background:rgba(255,64,96,.1); border:1px solid rgba(255,64,96,.35); color:var(--c2)}
.s-none{background:rgba(74,102,128,.1);border:1px solid var(--border);       color:var(--muted)}
.recv-box{font-family:var(--mono);font-size:12px;padding:10px 14px;border-radius:4px;
  background:rgba(0,0,0,.3);border:1px solid var(--border);color:var(--text);word-break:break-all;margin-top:10px;}
.recv-box .lbl{font-size:9px;color:var(--muted);letter-spacing:2px;display:block;margin-bottom:5px}
.table-panel{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:20px;margin:24px 0;overflow:auto;}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{padding:10px 14px;text-align:left;font-size:9px;letter-spacing:2px;text-transform:uppercase;
  color:var(--muted);border-bottom:1px solid var(--border2);}
tbody td{padding:13px 14px;border-bottom:1px solid rgba(22,32,48,.6);vertical-align:middle}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(0,200,255,.03)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}
.tag{display:inline-block;font-size:9px;padding:3px 8px;border-radius:3px;font-family:var(--mono);letter-spacing:1px;}
.tag-best{background:rgba(48,255,128,.1);border:1px solid rgba(48,255,128,.3);color:var(--c3)}
.tag-good{background:rgba(78,205,196,.1);border:1px solid rgba(78,205,196,.3);color:var(--chk)}
.tag-weak{background:rgba(255,107,107,.1);border:1px solid rgba(255,107,107,.3);color:var(--parity)}
.meta-row{display:flex;gap:20px;flex-wrap:wrap;font-family:var(--mono);font-size:10px;color:var(--muted);
  letter-spacing:1.5px;padding:8px 0;border-top:1px solid var(--border);margin-top:12px;}
.meta-row span::before{content:'▸ ';color:var(--c1)}
footer{text-align:center;padding:20px 0 0;font-family:var(--mono);font-size:10px;
  color:var(--muted);letter-spacing:2px;border-top:1px solid var(--border);margin-top:20px;}
@media(max-width:760px){
  .cards-row,.plots-grid{grid-template-columns:1fr}.plot-full{grid-column:auto}
  .tx-controls{grid-template-columns:1fr}.result-row{grid-template-columns:1fr 1fr;gap:10px}
  .bits-track,.bits-lbl{display:none}}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div class="logo">NET-ERR-ANALYZER v2.0</div>
    <div><span class="status-dot"></span><span class="status-txt">PYTHON ENGINE CONNECTED</span></div>
  </div>
  <header>
    <div class="header-tag">DATA COMMUNICATIONS · PROJECT OPTION 2</div>
    <h1>Network Error Detection<br>Analyzer</h1>
    <p class="subtitle">Real-time Python simulation &nbsp;·&nbsp; Parity Check &nbsp;·&nbsp; Checksum &nbsp;·&nbsp; CRC-16</p>
  </header>

  <div class="controls-panel">
    <div class="controls-title">SIMULATION PARAMETERS</div>
    <div class="controls-grid">
      <div class="ctrl-group">
        <div class="ctrl-label">Min Error Rate <span class="ctrl-val" id="vMin">1%</span></div>
        <input type="range" id="sMin" min="1" max="10" value="1"
               oninput="document.getElementById('vMin').textContent=this.value+'%'">
      </div>
      <div class="ctrl-group">
        <div class="ctrl-label">Max Error Rate <span class="ctrl-val" id="vMax">20%</span></div>
        <input type="range" id="sMax" min="10" max="40" value="20"
               oninput="document.getElementById('vMax').textContent=this.value+'%'">
      </div>
      <div class="ctrl-group">
        <div class="ctrl-label">Steps <span class="ctrl-val" id="vSteps">20</span></div>
        <input type="range" id="sSteps" min="5" max="30" value="20"
               oninput="document.getElementById('vSteps').textContent=this.value">
      </div>
      <div class="ctrl-group">
        <div class="ctrl-label">Trials / Rate <span class="ctrl-val" id="vTrials">600</span></div>
        <input type="range" id="sTrials" min="100" max="2000" step="100" value="600"
               oninput="document.getElementById('vTrials').textContent=this.value">
      </div>
      <div class="ctrl-group" style="justify-content:flex-end">
        <button class="btn btn-primary" id="btnRun" onclick="runSimulation()">▶ RUN SIMULATION</button>
      </div>
    </div>
    <div class="progress-bar" id="progressBar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="loading-msg" id="loadingMsg"></div>
  </div>

  <div class="cards-row">
    <div class="card p1">
      <div class="card-name">Parity Check</div>
      <div class="card-val sk" id="c1val">---</div>
      <div class="card-sub sk" id="c1sub">run simulation</div>
      <div class="card-badge">+1 bit overhead</div>
    </div>
    <div class="card p2">
      <div class="card-name">Checksum</div>
      <div class="card-val sk" id="c2val">---</div>
      <div class="card-sub sk" id="c2sub">run simulation</div>
      <div class="card-badge">+16 bits overhead</div>
    </div>
    <div class="card p3">
      <div class="card-name">CRC-16</div>
      <div class="card-val sk" id="c3val">---</div>
      <div class="card-sub sk" id="c3sub">run simulation</div>
      <div class="card-badge">+16 bits overhead</div>
    </div>
  </div>

  <div class="plots-grid">
    <div class="plot-panel">
      <div class="plot-title">Detection Rate vs Error Rate</div>
      <div id="ph1" class="plot-placeholder"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Run simulation to generate</div>
      <img id="img1" class="plot-img" style="display:none" alt="">
    </div>
    <div class="plot-panel">
      <div class="plot-title">Undetected Error Rate</div>
      <div id="ph2" class="plot-placeholder"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Run simulation to generate</div>
      <img id="img2" class="plot-img" style="display:none" alt="">
    </div>
    <div class="plot-panel plot-full">
      <div class="plot-title">Technique Comparison — Bar Chart</div>
      <div id="ph3" class="plot-placeholder"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="12" width="4" height="9"/><rect x="10" y="7" width="4" height="14"/><rect x="17" y="4" width="4" height="17"/></svg>Run simulation to generate</div>
      <img id="img3" class="plot-img" style="display:none" alt="">
    </div>
    <div class="plot-panel plot-full">
      <div class="plot-title">Detection Rate Heatmap</div>
      <div id="ph4" class="plot-placeholder"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>Run simulation to generate</div>
      <img id="img4" class="plot-img" style="display:none" alt="">
    </div>
  </div>
  <div class="meta-row" id="metaRow" style="display:none">
    <span id="mTrials"></span><span id="mSteps"></span>
    <span id="mElapsed"></span><span id="mTimestamp"></span>
  </div>

  <div class="transmit-panel">
    <div class="plot-title">LIVE TRANSMISSION SIMULATOR</div>
    <div class="tx-controls">
      <div class="ctrl-group">
        <div class="ctrl-label">Message</div>
        <input type="text" id="txMsg" value="Hello, Network!" maxlength="48">
      </div>
      <div class="ctrl-group">
        <div class="ctrl-label">Bit Error Rate <span class="ctrl-val" id="vErr">5%</span></div>
        <input type="range" id="sErr" min="0" max="30" value="5"
               oninput="document.getElementById('vErr').textContent=this.value+'%'">
      </div>
      <div class="ctrl-group" style="justify-content:flex-end">
        <button class="btn btn-primary" onclick="runTransmit()">⚡ TRANSMIT</button>
      </div>
    </div>
    <div id="txResults"></div>
  </div>

  <div class="table-panel">
    <div class="plot-title" style="margin-bottom:16px">TECHNIQUE COMPARISON</div>
    <table>
      <thead><tr><th>Technique</th><th>Overhead</th><th>Detects</th><th>Misses</th><th>Used In</th><th>Rating</th></tr></thead>
      <tbody>
        <tr>
          <td><span class="dot" style="background:var(--parity)"></span><strong>Parity Check</strong></td>
          <td style="font-family:var(--mono)">+1 bit</td>
          <td>Odd number of bit errors</td>
          <td>Even number of errors (~50% miss)</td>
          <td>UART, serial links</td>
          <td><span class="tag tag-weak">WEAK</span></td>
        </tr>
        <tr>
          <td><span class="dot" style="background:var(--chk)"></span><strong>Checksum</strong></td>
          <td style="font-family:var(--mono)">+16 bits</td>
          <td>Most random single/burst errors</td>
          <td>Complementary byte-swap errors</td>
          <td>TCP, UDP, IPv4, ICMP</td>
          <td><span class="tag tag-good">GOOD</span></td>
        </tr>
        <tr>
          <td><span class="dot" style="background:var(--crc)"></span><strong>CRC-16</strong></td>
          <td style="font-family:var(--mono)">+16 bits</td>
          <td>All burst errors ≤16 bits, 99.9%+ random</td>
          <td>Extremely rare polynomial-specific patterns</td>
          <td>Ethernet, USB, Bluetooth, ZIP</td>
          <td><span class="tag tag-best">BEST</span></td>
        </tr>
      </tbody>
    </table>
  </div>
  <footer>NETWORK ERROR DETECTION ANALYZER · PROJECT OPTION 2 · DATA COMMUNICATIONS</footer>
</div>
<script>
const COLORS={'Parity Check':'#ff6b6b','Checksum':'#4ecdc4','CRC-16':'#45b7d1'};

async function runSimulation(){
  const btn=document.getElementById('btnRun');
  btn.disabled=true; btn.textContent='⏳ RUNNING...';
  const bar=document.getElementById('progressBar');
  const fill=document.getElementById('progressFill');
  const msg=document.getElementById('loadingMsg');
  bar.style.display='block';
  let pct=0;
  const tick=setInterval(()=>{
    pct=Math.min(pct+Math.random()*4,90);
    fill.style.width=pct+'%';
    const done=Math.floor(pct/100*parseInt(document.getElementById('sSteps').value));
    msg.textContent=`Running Python simulation… ${done} / ${document.getElementById('sSteps').value} error rates processed`;
  },200);
  try{
    const res=await fetch('/api/simulate',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        min_rate:parseInt(document.getElementById('sMin').value),
        max_rate:parseInt(document.getElementById('sMax').value),
        steps:parseInt(document.getElementById('sSteps').value),
        trials:parseInt(document.getElementById('sTrials').value)
      })});
    const data=await res.json();
    clearInterval(tick); fill.style.width='100%';
    msg.textContent=`✓ Simulation complete in ${data.elapsed}s`;
    setTimeout(()=>{bar.style.display='none';msg.textContent='';},2500);
    updateCards(data.summary); updatePlots(data.plots); updateMeta(data);
  }catch(e){
    clearInterval(tick); msg.textContent='✗ Error: '+e.message; bar.style.display='none';
  }
  btn.disabled=false; btn.textContent='▶ RUN SIMULATION';
}

function updateCards(summary){
  const keys=['Parity Check','Checksum','CRC-16']; const ids=['c1','c2','c3'];
  keys.forEach((k,i)=>{
    const s=summary[k];
    const ev=document.getElementById(ids[i]+'val');
    const es=document.getElementById(ids[i]+'sub');
    ev.classList.remove('sk'); es.classList.remove('sk');
    ev.textContent=s.avg_detection+'%';
    es.textContent=`min ${s.min_detection}% · max ${s.max_detection}%`;
  });
}

function updatePlots(plots){
  [['detection','img1','ph1'],['undetected','img2','ph2'],
   ['bar','img3','ph3'],['heatmap','img4','ph4']].forEach(([k,imgId,phId])=>{
    const img=document.getElementById(imgId); const ph=document.getElementById(phId);
    img.src='data:image/png;base64,'+plots[k];
    img.style.display='block'; ph.style.display='none';
  });
}

function updateMeta(data){
  document.getElementById('metaRow').style.display='flex';
  document.getElementById('mTrials').textContent='trials: '+data.trials+' per rate';
  document.getElementById('mSteps').textContent='error rates: '+data.results['Parity Check'].error_rates.length;
  document.getElementById('mElapsed').textContent='elapsed: '+data.elapsed+'s';
  document.getElementById('mTimestamp').textContent='generated: '+new Date().toLocaleTimeString();
}

async function runTransmit(){
  const msg=document.getElementById('txMsg').value||'Hello!';
  const rate=parseInt(document.getElementById('sErr').value);
  const container=document.getElementById('txResults');
  container.innerHTML='<div style="font-family:var(--mono);font-size:11px;color:var(--muted);padding:12px 0;letter-spacing:2px">⏳ Transmitting through Python engine...</div>';
  try{
    const res=await fetch('/api/transmit',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg,error_rate:rate})});
    const data=await res.json();
    renderResults(data.detail);
  }catch(e){
    container.innerHTML=`<div style="color:var(--c2);font-family:var(--mono);font-size:12px">Error: ${e.message}</div>`;
  }
}

function renderResults(detail){
  const container=document.getElementById('txResults');
  let html='';
  for(const [name,info] of Object.entries(detail)){
    const color=COLORS[name]||'#aaa';
    const hasErr=info.errors_injected>0;
    let sc,st;
    if(!hasErr){sc='s-none';st='NO ERRORS';}
    else if(info.error_detected){sc='s-ok';st='✓ DETECTED';}
    else{sc='s-miss';st='✗ MISSED';}
    const errPct=Math.min((info.errors_injected/info.encoded_bits)*100,100).toFixed(1);
    const ohPct=((info.overhead_bits/info.original_bits)*100).toFixed(0);
    let recvHtml='';
    for(let i=0;i<Math.max(info.original_msg.length,info.received_msg.length);i++){
      const o=info.original_msg[i]||'';
      const r=info.received_msg[i]||'';
      const safe=r==='<'?'&lt;':r==='>'?'&gt;':r||'?';
      if(o!==r) recvHtml+=`<span style="color:var(--c2);background:rgba(255,64,96,.15);border-radius:2px">${safe}</span>`;
      else recvHtml+=safe;
    }
    html+=`
    <div class="result-row">
      <div class="res-name" style="color:${color}">${name}</div>
      <div class="res-metric">
        <span class="lbl">Bit Errors</span>
        <span class="val" style="color:${hasErr?'var(--c2)':'var(--c3)'}">${info.errors_injected}</span>
      </div>
      <div class="res-metric">
        <span class="lbl">Overhead</span>
        <span class="val" style="color:var(--muted)">+${info.overhead_bits}b (${ohPct}%)</span>
      </div>
      <div>
        <div class="bits-track">
          <div class="bits-fill" style="width:${errPct}%;background:${color}55;border-right:2px solid ${color}"></div>
        </div>
        <div class="bits-lbl">${info.original_bits} data bits → ${info.encoded_bits} encoded · ${info.errors_injected} corrupted (${errPct}%)</div>
      </div>
      <div class="status ${sc}">${st}</div>
    </div>
    <div class="recv-box">
      <span class="lbl">RECEIVED MESSAGE (${name})</span>${recvHtml}
    </div>`;
  }
  document.getElementById('txResults').innerHTML=html;
}

window.addEventListener('load',()=>{ runTransmit(); });
</script>
</body>
</html>'''

# ── write files ────────────────────────────────────────────────────────────
files = {
    os.path.join(ROOT, 'error_detection.py'):   ED.strip(),
    os.path.join(ROOT, 'server.py'):             SRV.strip(),
    os.path.join(STATIC, 'index.html'):          HTML.strip(),
}

print('\n' + '='*52)
print('  Network Error Detection Analyzer — Setup')
print('='*52)

for path, content in files.items():
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  [✓] Created: {path}')

# verify flask is available
try:
    import flask
    print(f'\n  [✓] Flask {flask.__version__} found')
except ImportError:
    print('\n  [!] Flask not found — installing...')
    os.system(f'{sys.executable} -m pip install flask matplotlib numpy --break-system-packages -q')
    print('  [✓] Dependencies installed')

print(f'''
  Setup complete!
  ──────────────
  Run the server:
    cd {ROOT}
    python server.py

  Then open → http://localhost:5000
{'='*52}
''')
