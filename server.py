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