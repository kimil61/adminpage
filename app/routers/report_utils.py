# app/report_utils.py
import io, base64
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def radar_chart_base64(ratios: dict[str, int]) -> str:
    """{'Wood':25,'Fire':30,'Earth':20,'Metal':15,'Water':10} → <img src='data:…'>"""
    labels = list(ratios.keys())
    values = list(ratios.values())
    # 원형으로 닫힘
    values += values[:1]
    angles = np.linspace(0, 2*np.pi, len(values))

    fig, ax = plt.subplots(subplot_kw={'polar': True})
    ax.fill(angles, values, alpha=.25)
    ax.plot(angles, values, linewidth=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontweight='bold')
    ax.set_yticklabels([])
    ax.grid(True)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)

def month_heat_table(status: dict[str, list[str]]) -> str:
    """
    {'Love':['G','R',…], 'Money':['-','G',…], 'Career':[…]} (G=Good, Y=Caution, R=Risk)
    → 컬러 배경 셀 HTML
    """
    df = pd.DataFrame(status, index=['J','F','M','A','M','J','J','A','S','O','N','D']).T
    color_map = {'G':'#DCFCE7', 'Y':'#FEFCE8', 'R':'#FEE2E2', '-':'#FFFFFF'}
    styled = df.style.applymap(lambda v: f"background:{color_map.get(v,'#FFF')};")
    return styled.to_html(classes="mini-cal", border=0)

def keyword_card(color:str, numbers:list[int], stone:str) -> str:
    nums = ", ".join(map(str,numbers))
    return f"""
    <div class="card">
        <h3>행운 키워드</h3>
        <ul>
            <li>🎨 색상 : <b style="color:{color.lower()};">{color}</b></li>
            <li>🔢 숫자 : <b>{nums}</b></li>
            <li>💎 스톤 : <b>{stone}</b></li>
        </ul>
    </div>"""

    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()