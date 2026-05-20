"""
TikTok 选品竞争度雷达 — Web 面板
FastAPI + 内嵌 HTML，无需前端构建工具
"""
import os
import json
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd
import uvicorn

from loader import load_csv, load_directory, load_trend_csv, load_trend_directory
from scorer import score_category
from models import CategoryAnalysis, OceanLevel
from trend import analyze_trend

DATA_DIR = Path(__file__).parent / "sample_data"

app = FastAPI(title="TikTok 选品竞争度雷达")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🎯 TikTok 选品雷达</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0d0d0d;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}
  header{background:#111;border-bottom:1px solid #222;padding:18px 32px;display:flex;align-items:center;gap:12px}
  header h1{font-size:1.4rem;font-weight:700;letter-spacing:-0.02em}
  header p{color:#666;font-size:.85rem}
  .main{max-width:1400px;margin:0 auto;padding:28px 24px}
  .upload-bar{background:#161616;border:1px dashed #333;border-radius:12px;padding:20px 24px;margin-bottom:28px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
  .upload-bar input[type=file]{color:#aaa;font-size:.88rem}
  .upload-bar input[type=text]{background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:8px 12px;color:#e0e0e0;font-size:.88rem;width:180px}
  .btn{background:#6c63ff;color:#fff;border:none;border-radius:8px;padding:9px 20px;cursor:pointer;font-size:.88rem;transition:background .2s}
  .btn:hover{background:#5751e0}
  .btn-sample{background:#1e1e1e;border:1px solid #333;color:#aaa}
  .btn-sample:hover{background:#252525;color:#e0e0e0}
  .summary-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:28px}
  .card{background:#161616;border:1px solid #222;border-radius:12px;padding:18px}
  .card-label{font-size:.72rem;color:#666;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
  .card-value{font-size:1.8rem;font-weight:700}
  .card-sub{font-size:.78rem;color:#555;margin-top:4px}
  .table-wrap{overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:.85rem}
  th{background:#161616;padding:9px 12px;text-align:left;color:#666;font-weight:600;border-bottom:1px solid #222;white-space:nowrap;cursor:pointer;user-select:none}
  th:hover{color:#fff}
  td{padding:10px 12px;border-bottom:1px solid #1a1a1a;vertical-align:middle}
  tr:hover td{background:#141414}
  .badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.76rem;font-weight:600}
  .badge-blue{background:#0a2a4a;color:#4fc3f7}
  .badge-shallow{background:#1a2a1a;color:#81c784}
  .badge-red{background:#2a1a1a;color:#ef9a9a}
  .badge-bloody{background:#3a0a0a;color:#e57373}
  .phase-badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.76rem;font-weight:600}
  .phase-rising{background:#0a2a0a;color:#66bb6a}
  .phase-peak{background:#0a2a4a;color:#4fc3f7}
  .phase-declining{background:#2a2a0a;color:#fdd835}
  .phase-dormant{background:#2a0a0a;color:#ef5350}
  .growth-pos{color:#66bb6a}
  .growth-neg{color:#ef5350}
  .growth-zero{color:#666}
  .bar-bg{background:#1e1e1e;border-radius:4px;height:6px;width:80px;display:inline-block;vertical-align:middle}
  .bar-fill{height:6px;border-radius:4px;display:block;transition:width .4s}
  .section-title{font-size:1rem;font-weight:600;color:#ccc;margin-bottom:14px}
  #status{color:#aaa;font-size:.85rem;padding:8px 0}
  .detail-panel{background:#0f1a0f;border:1px solid #1a3a1a;border-radius:10px;padding:16px;margin-top:6px;font-size:.83rem;color:#aaa;line-height:1.6;display:none}
  .detail-panel.open{display:block}
  .top-creator-item{padding:4px 0;border-bottom:1px solid #1e1e1e;display:flex;justify-content:space-between}
  .sparkline{display:inline-block;vertical-align:middle}
  .trend-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px}
  .trend-box{background:#111;border:1px solid #222;border-radius:8px;padding:12px}
  .trend-box-label{font-size:.72rem;color:#666;margin-bottom:4px}
  .trend-box-value{font-size:1.3rem;font-weight:700}
  .refund-badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.7rem;font-weight:600}
  .refund-badge-normal{background:#0a1a0a;color:#66bb6a}
  .refund-badge-warning{background:#2a1a0a;color:#ffb74d}
  .refund-badge-danger{background:#3a0a0a;color:#ef5350}
  .refund-penalty-icon{display:inline-block;width:14px;height:14px;line-height:14px;text-align:center;border-radius:50%;font-size:.7rem;margin-right:4px}
  .refund-penalty-yes{background:#3a0a0a;color:#ef5350}
  .refund-penalty-no{background:#0a1a0a;color:#66bb6a}
</style>
</head>
<body>
<header>
  <div>
    <h1>🎯 TikTok 选品竞争度雷达</h1>
    <p>TOP 50 达人数据建模 · 5维饱和度评分 + 日/月增长趋势 · 识别蓝海资产</p>
  </div>
</header>
<div class="main">
  <div class="upload-bar">
    <form id="uploadForm" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <input type="file" id="csvFile" accept=".csv" multiple>
      <input type="text" id="catName" placeholder="类目名（单文件时用）">
      <button class="btn" type="submit">📊 分析</button>
      <button class="btn btn-sample" type="button" onclick="loadSample()">🎲 加载 Demo 数据</button>
    </form>
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-left:auto">
      <select id="dataSource" style="background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:8px 12px;color:#e0e0e0;font-size:.85rem">
        <option value="csv">CSV 文件</option>
        <option value="fastmoss">FastMoss API</option>
        <option value="kalodata">Kalodata API</option>
      </select>
      <select id="fetchCategory" style="background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:8px 12px;color:#e0e0e0;font-size:.85rem;min-width:160px">
        <option value="">请先配置 API Key</option>
      </select>
      <button class="btn" type="button" onclick="loadCategories()" style="padding:8px 12px;font-size:.82rem">🔄 加载类目</button>
      <button class="btn" type="button" onclick="fetchFromAPI()">📊 分析</button>
      <button class="btn btn-sample" type="button" onclick="openConfigModal()">⚙ 配置</button>
    </div>
    <div style="display:flex;gap:8px;align-items:center;margin-left:auto;flex-wrap:wrap;margin-top:8px">
      <span style="color:#666;font-size:.82rem">💰 均价筛选</span>
      <input type="number" id="minPrice" placeholder="最低$" step="0.01" min="0"
             style="background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:7px 10px;color:#e0e0e0;font-size:.85rem;width:90px">
      <span style="color:#444">—</span>
      <input type="number" id="maxPrice" placeholder="最高$" step="0.01" min="0"
             style="background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:7px 10px;color:#e0e0e0;font-size:.85rem;width:90px">
      <button class="btn" style="padding:7px 14px;font-size:.82rem" onclick="applyPriceFilter()">筛选</button>
      <button class="btn btn-sample" style="padding:7px 14px;font-size:.82rem" onclick="clearPriceFilter()">清除</button>
    </div>
    <div id="status" style="width:100%;margin-top:8px">← 上传 CSV、加载 Demo 数据，或选择数据源后点击「实时抓取」</div>
  </div>

  <div id="summaryCards" class="summary-cards" style="display:none"></div>
  <div id="tableSection" style="display:none">
    <div class="section-title">类目竞争度排行（点击行展开详情）</div>
    <div class="table-wrap">
      <table id="resultTable">
        <thead>
          <tr>
            <th onclick="sortBy('category')">类目</th>
            <th onclick="sortBy('blue_ocean_score')">蓝海分 ▾</th>
            <th onclick="sortBy('ocean_level')">等级</th>
            <th onclick="sortBy('trend_phase')">趋势</th>
            <th onclick="sortBy('daily_growth_rate')">周环比</th>
            <th onclick="sortBy('monthly_growth_rate')">月环比</th>
            <th>60天走势</th>
            <th onclick="sortBy('saturation_score')">饱和度</th>
            <th onclick="sortBy('avg_refund_rate')">退款率</th>
            <th>惩罚</th>
            <th>集中度</th>
            <th>密度</th>
            <th>衰减</th>
            <th>内卷</th>
            <th>门槛</th>
            <th>均价</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </div>
</div>

<div id="configModal" class="modal-overlay" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:1000;display:flex;align-items:center;justify-content:center">
  <div class="modal-content" style="background:#1a1a1a;border:1px solid #333;border-radius:12px;padding:24px;max-width:500px;width:90%;max-height:80vh;overflow-y:auto">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <h3 style="color:#e0e0e0;margin:0">⚙ 数据源配置</h3>
      <button onclick="closeConfigModal()" style="background:none;border:none;color:#666;font-size:24px;cursor:pointer;padding:0;width:30px;height:30px;display:flex;align-items:center;justify-content:center">×</button>
    </div>
    <div style="margin-bottom:16px">
      <label style="display:block;color:#aaa;font-size:.85rem;margin-bottom:6px">当前数据源</label>
      <select id="configDataSource" style="width:100%;background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:10px 12px;color:#e0e0e0;font-size:.9rem">
        <option value="csv">CSV 文件（本地）</option>
        <option value="fastmoss">FastMoss API</option>
        <option value="kalodata">Kalodata API</option>
      </select>
    </div>
    <div id="apiConfigSection" style="display:none">
      <div style="background:#1a1a0a;border:1px solid #332;border-radius:8px;padding:12px;margin-bottom:16px">
        <div style="color:#ffb74d;font-size:.8rem;font-weight:600;margin-bottom:6px">💰 API 成本说明</div>
        <div style="color:#999;font-size:.75rem;line-height:1.5">
          <div>• 达人相关接口: ¥0.14/次</div>
          <div>• 商品/店铺相关接口: ¥0.07/次</div>
          <div>• 50个达人分析约需 ¥0.70~1.40</div>
        </div>
      </div>
      <div style="margin-bottom:16px">
        <label style="display:block;color:#aaa;font-size:.85rem;margin-bottom:6px">API Key (client_secret)</label>
        <input type="password" id="apiKey" placeholder="从 FastMoss 控制台获取"
               style="width:100%;background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:10px 12px;color:#e0e0e0;font-size:.9rem">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
        <div>
          <label style="display:block;color:#aaa;font-size:.85rem;margin-bottom:6px">区域</label>
          <select id="apiRegion" style="width:100%;background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:10px 12px;color:#e0e0e0;font-size:.9rem">
            <option value="US">美国 (US)</option>
            <option value="GB">英国 (GB)</option>
            <option value="JP">日本 (JP)</option>
            <option value="KR">韩国 (KR)</option>
            <option value="SG">新加坡 (SG)</option>
            <option value="AU">澳大利亚 (AU)</option>
            <option value="CA">加拿大 (CA)</option>
            <option value="DE">德国 (DE)</option>
            <option value="FR">法国 (FR)</option>
            <option value="ES">西班牙 (ES)</option>
            <option value="IT">意大利 (IT)</option>
            <option value="BR">巴西 (BR)</option>
            <option value="MX">墨西哥 (MX)</option>
            <option value="SA">沙特 (SA)</option>
            <option value="AE">阿联酋 (AE)</option>
            <option value="PH">菲律宾 (PH)</option>
            <option value="TH">泰国 (TH)</option>
            <option value="VN">越南 (VN)</option>
            <option value="ID">印度尼西亚 (ID)</option>
            <option value="MY">马来西亚 (MY)</option>
          </select>
        </div>
        <div>
          <label style="display:block;color:#aaa;font-size:.85rem;margin-bottom:6px">每日成本限额 (¥)</label>
          <input type="number" id="dailyCostLimit" value="5.0" min="0" step="1"
                 style="width:100%;background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:10px 12px;color:#e0e0e0;font-size:.9rem">
        </div>
      </div>
      <div style="margin-bottom:16px">
        <label style="display:block;color:#aaa;font-size:.85rem;margin-bottom:6px">API Endpoint（可选，默认生产环境）</label>
        <input type="text" id="apiEndpoint" placeholder="https://openapi.fastmoss.com"
               style="width:100%;background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:10px 12px;color:#e0e0e0;font-size:.9rem">
      </div>
      <div style="margin-bottom:16px">
        <label style="display:block;color:#aaa;font-size:.85rem;margin-bottom:6px">缓存时间（秒）</label>
        <input type="number" id="cacheTtl" value="3600" min="0" step="60"
               style="width:100%;background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:10px 12px;color:#e0e0e0;font-size:.9rem">
      </div>
    </div>
    <div style="border-top:1px solid #333;padding-top:16px;margin-top:8px">
      <h4 style="color:#aaa;font-size:.85rem;margin-bottom:12px">退款率惩罚配置</h4>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <label style="display:block;color:#aaa;font-size:.78rem;margin-bottom:4px">惩罚阈值（%）</label>
          <input type="number" id="refundThreshold" value="20" min="0" max="100" step="0.1"
                 style="width:100%;background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:8px 10px;color:#e0e0e0;font-size:.85rem">
        </div>
        <div>
          <label style="display:block;color:#aaa;font-size:.78rem;margin-bottom:4px">惩罚分数</label>
          <input type="number" id="refundPenalty" value="10" min="0" max="100" step="0.5"
                 style="width:100%;background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:8px 10px;color:#e0e0e0;font-size:.85rem">
        </div>
      </div>
      <div style="margin-top:12px">
        <label style="display:flex;align-items:center;gap:8px;color:#aaa;font-size:.85rem;cursor:pointer">
          <input type="checkbox" id="refundEnabled" checked style="width:16px;height:16px">
          启用退款率惩罚
        </label>
      </div>
    </div>
    <div style="display:flex;gap:12px;margin-top:20px">
      <button onclick="saveConfig()" class="btn" style="flex:1">💾 保存配置</button>
      <button onclick="closeConfigModal()" class="btn btn-sample" style="flex:1">取消</button>
    </div>
  </div>
</div>

<script>
let allResults = [];
let filteredResults = [];
let sortKey = 'blue_ocean_score';
let sortAsc = false;

function getFilteredResults(){
  const minP = parseFloat(document.getElementById('minPrice').value);
  const maxP = parseFloat(document.getElementById('maxPrice').value);
  let data = [...allResults];
  if(!isNaN(minP)) data = data.filter(r => r.avg_price >= minP);
  if(!isNaN(maxP)) data = data.filter(r => r.avg_price <= maxP);
  return data;
}

function applyPriceFilter(){
  filteredResults = getFilteredResults();
  const diff = allResults.length - filteredResults.length;
  renderSummary(filteredResults);
  renderTable(filteredResults);
  const minP = document.getElementById('minPrice').value;
  const maxP = document.getElementById('maxPrice').value;
  let msg = `💰 筛选: `;
  if(minP && maxP) msg += `$${minP} — $${maxP}`;
  else if(minP) msg += `≥ $${minP}`;
  else if(maxP) msg += `≤ $${maxP}`;
  else msg = '未设筛选条件';
  if(diff > 0) msg += ` (过滤 ${diff} 个类目)`;
  document.getElementById('status').textContent = msg + ` · 显示 ${filteredResults.length} 个类目`;
}

function clearPriceFilter(){
  document.getElementById('minPrice').value = '';
  document.getElementById('maxPrice').value = '';
  filteredResults = [...allResults];
  renderSummary(filteredResults);
  renderTable(filteredResults);
  document.getElementById('status').textContent = `✅ 已清除筛选，显示全部 ${allResults.length} 个类目`;
}

function badgeClass(level){
  if(level==='蓝海') return 'badge badge-blue';
  if(level==='浅水') return 'badge badge-shallow';
  if(level==='红海') return 'badge badge-red';
  return 'badge badge-bloody';
}
function phaseClass(p){
  if(p==='上升期') return 'phase-badge phase-rising';
  if(p==='巅峰期') return 'phase-badge phase-peak';
  if(p==='衰退期') return 'phase-badge phase-declining';
  if(p==='沉寂期') return 'phase-badge phase-dormant';
  return 'phase-badge';
}
function phaseIcon(p){
  return {上升期:'📈',巅峰期:'📊',衰退期:'📉',沉寂期:'💤'}[p]||'—';
}
function barColor(score){
  if(score>=60) return '#4fc3f7';
  if(score>=40) return '#81c784';
  if(score>=20) return '#ef9a9a';
  return '#e53935';
}
function satColor(score){
  if(score<=40) return '#4caf50';
  if(score<=60) return '#ff9800';
  return '#f44336';
}
function growthHtml(v){
  if(v==null) return '<span class="growth-zero">—</span>';
  const cls = v>0?'growth-pos':v<0?'growth-neg':'growth-zero';
  return `<span class="${cls}">${v>0?'+':''}${v.toFixed(1)}%</span>`;
}

function renderRefundRate(rate){
  if(rate == null || rate === 0) return '<span class="growth-zero">—</span>';
  let cls = 'refund-badge-normal';
  if(rate >= 20) cls = 'refund-badge-danger';
  else if(rate >= 15) cls = 'refund-badge-warning';
  return `<span class="refund-badge ${cls}">${rate}%</span>`;
}

function renderPenaltyStatus(applied, penalty){
  if(applied){
    return `<span class="refund-penalty-icon refund-penalty-yes">⚠</span><span style="color:#ef5350">+${penalty}</span>`;
  } else {
    return '<span class="refund-penalty-icon refund-penalty-no">✓</span>';
  }
}

// SVG sparkline
function sparkline(data, w=100, h=28){
  if(!data||!data.length) return '<span style="color:#333">—</span>';
  const max=Math.max(...data),min=Math.min(...data),range=max-min||1;
  const pts=data.map((v,i)=>{
    const x=(i/(data.length-1))*w;
    const y=h-((v-min)/range)*h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  // gradient: green if upward, red if downward
  const trend=data[data.length-1]-data[0];
  const c=trend>=0?'#66bb6a':'#ef5350';
  return `<svg class="sparkline" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <polyline fill="none" stroke="${c}" stroke-width="1.5" points="${pts}"/>
  </svg>`;
}

function renderTable(data){
  const sorted=[...data].sort((a,b)=>{
    let va=a[sortKey],vb=b[sortKey];
    if(typeof va==='string') return sortAsc?va.localeCompare(vb):vb.localeCompare(va);
    va=va??-999; vb=vb??-999;
    return sortAsc?va-vb:vb-va;
  });
  const tbody=document.getElementById('tableBody');
  tbody.innerHTML='';
  sorted.forEach((r,i)=>{
    const tr=document.createElement('tr');
    tr.style.cursor='pointer';
    const spark=r.trend_series?sparkline(r.trend_series):'<span style="color:#333">—</span>';
    tr.innerHTML=`
      <td><strong>${r.category}</strong></td>
      <td><span style="font-weight:700;color:${barColor(r.blue_ocean_score)}">${r.blue_ocean_score}</span>
        <div class="bar-bg"><div class="bar-fill" style="width:${r.blue_ocean_score}%;background:${barColor(r.blue_ocean_score)}"></div></div></td>
      <td><span class="${badgeClass(r.ocean_level)}">${r.ocean_level}</span></td>
      <td>${r.trend_phase?`<span class="${phaseClass(r.trend_phase)}">${phaseIcon(r.trend_phase)} ${r.trend_phase}</span>`:'<span style="color:#333">—</span>'}</td>
      <td>${growthHtml(r.daily_growth_rate)}</td>
      <td>${growthHtml(r.monthly_growth_rate)}</td>
      <td>${spark}</td>
      <td style="color:${satColor(r.saturation_score)}">${r.saturation_score}</td>
      <td>${renderRefundRate(r.avg_refund_rate)}</td>
      <td>${renderPenaltyStatus(r.refund_rate_penalty_applied, r.refund_rate_penalty)}</td>
      <td>${r.concentration_score}</td>
      <td>${r.content_density_score}</td>
      <td>${r.engagement_decay_score}</td>
      <td>${r.price_competition_score}</td>
      <td>${r.barrier_score}</td>
      <td>$${r.avg_price}</td>
    `;
    // 展开详情行
    const detailTr=document.createElement('tr');
    const topHtml=r.top_creators.map(c=>
      `<div class="top-creator-item"><span>@${c.username}</span><span style="color:#aaa">GMV $${c.gmv_monthly.toLocaleString()}</span></div>`
    ).join('');

    let trendDetailHtml='';
    if(r.trend_phase){
      trendDetailHtml=`
        <div class="trend-grid">
          <div class="trend-box">
            <div class="trend-box-label">趋势得分</div>
            <div class="trend-box-value" style="color:${r.trend_score>=50?'#66bb6a':'#ef5350'}">${r.trend_score}</div>
          </div>
          <div class="trend-box">
            <div class="trend-box-label">动量</div>
            <div class="trend-box-value" style="color:${r.trend_momentum>=0?'#66bb6a':'#ef5350'}">${r.trend_momentum>0?'+':''}${r.trend_momentum}</div>
          </div>
          <div class="trend-box">
            <div class="trend-box-label">峰值</div>
            <div class="trend-box-value" style="font-size:1rem">${r.trend_peak_date||'—'} (${r.trend_peak_volume||0}条)</div>
          </div>
          <div class="trend-box">
            <div class="trend-box-label">近7天日均</div>
            <div class="trend-box-value">${r.trend_daily_avg||'—'}</div>
          </div>
        </div>`;
    }

    let refundDetailHtml = '';
    if(r.avg_refund_rate > 0){
      let refundStatus = r.refund_rate_penalty_applied 
        ? '<span style="color:#ef5350">⚠️ 已触发惩罚</span>' 
        : '<span style="color:#66bb6a">✓ 未触发惩罚</span>';
      let refundInfo = r.refund_rate_penalty_applied 
        ? `（阈值20%，饱和度+${r.refund_rate_penalty}分）` 
        : '';
      refundDetailHtml = `
        <div style="margin-top:12px;padding:10px;background:#1a1a1a;border-radius:8px">
          <div style="color:#aaa;margin-bottom:6px;font-weight:600">💸 退款率分析</div>
          <div>平均退款率：<strong style="color:${r.avg_refund_rate>=20?'#ef5350':r.avg_refund_rate>=15?'#ffb74d':'#66bb6a'}">${r.avg_refund_rate}%</strong> ${refundStatus} ${refundInfo}</div>
        </div>`;
    }

    detailTr.innerHTML=`<td colspan="17">
      <div class="detail-panel" id="detail-${i}">
        <strong>💡 ${r.recommendation}</strong><br>
        入门门槛：粉丝中位数 ${r.entry_barrier_followers.toLocaleString()} | 均价：$${r.avg_price} | 价格变异系数：${r.price_cv}
        ${trendDetailHtml}
        ${refundDetailHtml}
        <div style="margin-top:12px">
          <div style="color:#666;margin-bottom:4px;font-size:.75rem">TOP 5 达人（月 GMV）</div>
          ${topHtml}
        </div>
      </div>
    </td>`;
    tr.addEventListener('click',()=>document.getElementById(`detail-${i}`).classList.toggle('open'));
    tbody.appendChild(tr);
    tbody.appendChild(detailTr);
  });
}

function renderSummary(data){
  const blueCount=data.filter(r=>r.ocean_level==='蓝海').length;
  const topBlue=[...data].sort((a,b)=>b.blue_ocean_score-a.blue_ocean_score)[0];
  const avgSat=(data.reduce((s,r)=>s+r.saturation_score,0)/data.length).toFixed(1);
  const risingCount=data.filter(r=>r.trend_phase==='上升期').length;
  const decliningCount=data.filter(r=>r.trend_phase==='衰退期'||r.trend_phase==='沉寂期').length;
  const highRefundCount=data.filter(r=>r.refund_rate_penalty_applied).length;
  const highRefundItems=data.filter(r=>r.refund_rate_penalty_applied).map(r=>r.category).join(', ');
  const cards=document.getElementById('summaryCards');
  cards.style.display='grid';
  cards.innerHTML=`
    <div class="card"><div class="card-label">类目数量</div><div class="card-value" style="color:#4fc3f7">${data.length}</div><div class="card-sub">已分析类目</div></div>
    <div class="card"><div class="card-label">蓝海机会</div><div class="card-value" style="color:#4caf50">${blueCount}</div><div class="card-sub">蓝海等级类目</div></div>
    <div class="card"><div class="card-label">平均饱和度</div><div class="card-value" style="color:${satColor(parseFloat(avgSat))}">${avgSat}</div><div class="card-sub">100 = 完全饱和</div></div>
    <div class="card"><div class="card-label">📈 上升期</div><div class="card-value" style="color:#66bb6a">${risingCount}</div><div class="card-sub">市场扩张中</div></div>
    <div class="card"><div class="card-label">📉 衰退/沉寂</div><div class="card-value" style="color:#ef5350">${decliningCount}</div><div class="card-sub">市场收缩中</div></div>
    <div class="card"><div class="card-label">⚠️ 退款率超标</div><div class="card-value" style="color:${highRefundCount>0?'#ef5350':'#66bb6a'}">${highRefundCount}</div><div class="card-sub">${highRefundCount>0?highRefundItems:'无超标类目'}</div></div>
    ${topBlue?`<div class="card"><div class="card-label">最佳蓝海</div><div class="card-value" style="color:#4fc3f7;font-size:1.2rem">${topBlue.category}</div><div class="card-sub">蓝海分 ${topBlue.blue_ocean_score}${topBlue.trend_phase?' · '+topBlue.trend_phase:''}</div></div>`:''}
  `;
}

function sortBy(key){
  if(sortKey===key) sortAsc=!sortAsc; else {sortKey=key;sortAsc=false;}
  renderTable(filteredResults);
}

document.getElementById('uploadForm').addEventListener('submit',async(e)=>{
  e.preventDefault();
  const files=document.getElementById('csvFile').files;
  const catName=document.getElementById('catName').value;
  if(!files.length){alert('请选择 CSV 文件');return;}
  document.getElementById('status').textContent='分析中...';
  const fd=new FormData();
  for(const f of files) fd.append('files',f);
  fd.append('category_name',catName);
  const res=await fetch('/analyze',{method:'POST',body:fd});
  const data=await res.json();
  if(data.error){alert(data.error);return;}
  allResults=data;
  filteredResults=getFilteredResults();
  renderSummary(filteredResults);
  renderTable(filteredResults);
  document.getElementById('tableSection').style.display='block';
  document.getElementById('status').textContent=`✅ 分析完成，${filteredResults.length} 个类目`;
});

async function loadSample(){
  document.getElementById('status').textContent='加载 Demo 数据...';
  const res=await fetch('/sample');
  const data=await res.json();
  if(data.error){alert(data.error);return;}
  allResults=data;
  filteredResults=getFilteredResults();
  renderSummary(filteredResults);
  renderTable(filteredResults);
  document.getElementById('tableSection').style.display='block';
  document.getElementById('status').textContent=`✅ Demo 数据加载完成，${filteredResults.length} 个类目（含60天趋势）`;
}

async function loadCategories(){
  const source=document.getElementById('dataSource').value;
  const select=document.getElementById('fetchCategory');
  
  if(source==='csv'){
    select.innerHTML='<option value="">选择 CSV 数据源时无需类目</option>';
    return;
  }
  
  select.innerHTML='<option value="">加载中...</option>';
  document.getElementById('status').textContent='正在加载类目列表...';
  
  try{
    const res=await fetch(`/api/categories?source=${source}`);
    const data=await res.json();
    
    if(data.error){
      if(data.needs_config){
        select.innerHTML='<option value="">请先配置 API Key</option>';
        alert('请先在配置中设置 API Key');
      }else{
        select.innerHTML='<option value="">加载失败</option>';
        alert('加载类目列表失败: '+data.error);
      }
      document.getElementById('status').textContent='加载类目列表失败: '+data.error;
      return;
    }
    
    const categories=data.categories||[];
    if(categories.length===0){
      select.innerHTML='<option value="">暂无可选类目</option>';
      document.getElementById('status').textContent='暂无可选类目，请检查 API 配置';
      return;
    }
    
    let html='<option value="">请选择类目</option>';
    categories.forEach(cat=>{
      html+=`<option value="${cat}">${cat}</option>`;
    });
    select.innerHTML=html;
    document.getElementById('status').textContent=`✅ 已加载 ${categories.length} 个类目（${data.region||'当前区域'}）`;
  }catch(e){
    select.innerHTML='<option value="">加载失败</option>';
    document.getElementById('status').textContent='加载类目列表失败: '+e.message;
    alert('加载类目列表失败: '+e.message);
  }
}

async function fetchFromAPI(){
  const source=document.getElementById('dataSource').value;
  const category=document.getElementById('fetchCategory').value.trim();
  
  if(source==='csv'){
    alert('CSV 数据源不支持实时抓取，请选择 FastMoss 或 Kalodata API');
    return;
  }
  
  if(!category){
    alert('请先选择类目（点击「加载类目」按钮）');
    return;
  }
  
  document.getElementById('status').textContent=`正在从 ${source} 分析「${category}」类目...`;
  
  try{
    const res=await fetch('/api/fetch',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        source: source,
        category: category,
        limit: 50
      })
    });
    const data=await res.json();
    
    if(data.error){
      alert('抓取失败: '+data.error);
      document.getElementById('status').textContent='抓取失败: '+data.error;
      return;
    }
    
    if(data.not_implemented){
      alert(`${source} API 适配器尚未实现，请先配置 API Key 并实现具体的抓取逻辑`);
      document.getElementById('status').textContent=`${source} API 适配器尚未实现`;
      return;
    }
    
    allResults=data;
    filteredResults=getFilteredResults();
    renderSummary(filteredResults);
    renderTable(filteredResults);
    document.getElementById('tableSection').style.display='block';
    document.getElementById('status').textContent=`✅ 从 ${source} 抓取「${category}」完成，共 ${data.length} 个类目`;
  }catch(e){
    alert('请求失败: '+e.message);
    document.getElementById('status').textContent='请求失败: '+e.message;
  }
}

function openConfigModal(){
  const modal=document.getElementById('configModal');
  modal.style.display='flex';
  
  const currentSource=document.getElementById('dataSource').value;
  document.getElementById('configDataSource').value=currentSource;
  toggleApiConfigSection();
  
  loadCurrentConfig();
}

function closeConfigModal(){
  document.getElementById('configModal').style.display='none';
}

function toggleApiConfigSection(){
  const source=document.getElementById('configDataSource').value;
  const section=document.getElementById('apiConfigSection');
  if(source==='csv'){
    section.style.display='none';
  }else{
    section.style.display='block';
  }
}

async function loadCurrentConfig(){
  try{
    const res=await fetch('/api/config');
    const config=await res.json();
    
    if(config.data_source){
      document.getElementById('configDataSource').value=config.data_source.provider||'csv';
      document.getElementById('apiKey').value=config.data_source.api_key||'';
      document.getElementById('apiEndpoint').value=config.data_source.api_endpoint||'';
      document.getElementById('cacheTtl').value=config.data_source.cache_ttl_seconds||3600;
      
      if(config.data_source.region){
        document.getElementById('apiRegion').value=config.data_source.region;
      }
      if(config.data_source.daily_cost_limit){
        document.getElementById('dailyCostLimit').value=config.data_source.daily_cost_limit;
      }
    }
    
    if(config.refund_rate){
      document.getElementById('refundThreshold').value=config.refund_rate.threshold||20;
      document.getElementById('refundPenalty').value=config.refund_rate.penalty_score||10;
      document.getElementById('refundEnabled').checked=config.refund_rate.enabled!==false;
    }
    
    toggleApiConfigSection();
  }catch(e){
    console.log('无法加载配置:',e);
  }
}

async function saveConfig(){
  const config={
    data_source:{
      provider: document.getElementById('configDataSource').value,
      api_key: document.getElementById('apiKey').value,
      api_endpoint: document.getElementById('apiEndpoint').value,
      cache_ttl_seconds: parseInt(document.getElementById('cacheTtl').value)||3600,
      region: document.getElementById('apiRegion').value,
      daily_cost_limit: parseFloat(document.getElementById('dailyCostLimit').value)||5.0,
    },
    refund_rate:{
      threshold: parseFloat(document.getElementById('refundThreshold').value)||20,
      penalty_score: parseFloat(document.getElementById('refundPenalty').value)||10,
      enabled: document.getElementById('refundEnabled').checked,
    }
  };
  
  try{
    const res=await fetch('/api/config',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(config)
    });
    const result=await res.json();
    
    if(result.success){
      document.getElementById('dataSource').value=config.data_source.provider;
      closeConfigModal();
      document.getElementById('status').textContent='✅ 配置已保存';
    }else{
      alert('保存失败: '+result.error);
    }
  }catch(e){
    alert('保存失败: '+e.message);
  }
}

document.getElementById('configDataSource').addEventListener('change',toggleApiConfigSection);

document.getElementById('configModal').addEventListener('click',function(e){
  if(e.target===this) closeConfigModal();
});
</script>
</body>
</html>"""


def serialize_result(r: CategoryAnalysis, trend_series: list = None) -> dict:
    d = {
        "category": r.category,
        "creator_count": r.creator_count,
        "blue_ocean_score": r.blue_ocean_score,
        "saturation_score": r.saturation_score,
        "ocean_level": r.ocean_level.value,
        "concentration_score": r.concentration_score,
        "content_density_score": r.content_density_score,
        "engagement_decay_score": r.engagement_decay_score,
        "price_competition_score": r.price_competition_score,
        "barrier_score": r.barrier_score,
        "avg_price": r.avg_price,
        "price_cv": r.price_cv,
        "entry_barrier_followers": r.entry_barrier_followers,
        "recommendation": r.recommendation,
        "top_creators": [
            {"username": c.username, "gmv_monthly": c.gmv_monthly, "followers": c.followers}
            for c in r.top_creators
        ],
        # 趋势字段
        "trend_phase": r.trend_phase,
        "trend_score": r.trend_score,
        "daily_growth_rate": r.daily_growth_rate,
        "monthly_growth_rate": r.monthly_growth_rate,
        "trend_momentum": r.trend_momentum,
        "trend_peak_date": r.trend_peak_date,
        "trend_peak_volume": r.trend_peak_volume,
        "trend_daily_avg": r.trend_daily_avg,
        "trend_series": trend_series,   # 日级时序数组，前端画 sparkline
        # 退款率字段
        "avg_refund_rate": r.avg_refund_rate,
        "refund_rate_penalty_applied": r.refund_rate_penalty_applied,
        "refund_rate_penalty": r.refund_rate_penalty,
    }
    return d


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_TEMPLATE


@app.get("/sample")
async def load_sample():
    try:
        datasets = load_directory(str(DATA_DIR))
        trend_data = load_trend_directory(str(DATA_DIR))
        if not datasets:
            return JSONResponse({"error": "sample_data/ 目录无 CSV 文件，请先运行 gen_sample.py"})
        results = []
        for cat, df in datasets.items():
            t_df = trend_data.get(cat)
            r = score_category(df, cat, trend_df=t_df)
            series = t_df["video_count"].tolist() if t_df is not None else None
            results.append(serialize_result(r, trend_series=series))
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)})


@app.post("/analyze")
async def analyze(files: List[UploadFile] = File(...), category_name: str = Form("")):
    try:
        results = []
        # 分离达人 CSV 和趋势 CSV
        creator_files = []
        trend_files = {}
        for upload in files:
            name = upload.filename
            if name.endswith("_trend.csv"):
                cat = name.replace("_trend.csv", "")
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                    tmp.write(await upload.read())
                    trend_files[cat] = tmp.name
            else:
                creator_files.append(upload)

        for upload in creator_files:
            import tempfile
            suffix = Path(upload.filename).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(await upload.read())
                tmp_path = tmp.name
            try:
                df = load_csv(tmp_path)
                cat = category_name if (category_name and len(creator_files) == 1) else Path(upload.filename).stem

                t_df = None
                series = None
                if cat in trend_files:
                    from loader import load_trend_csv as _ltc
                    t_df = _ltc(trend_files[cat])
                    series = t_df["video_count"].tolist()
                    os.unlink(trend_files[cat])

                r = score_category(df, cat, trend_df=t_df)
                results.append(serialize_result(r, trend_series=series))
            finally:
                os.unlink(tmp_path)
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)})


@app.get("/api/config")
async def get_config():
    try:
        from config import get_config
        config = get_config()
        return {
            "data_source": {
                "provider": config.data_source.provider,
                "api_key": config.data_source.api_key,
                "api_endpoint": config.data_source.api_endpoint,
                "cache_ttl_seconds": config.data_source.cache_ttl_seconds,
                "rate_limit_per_minute": config.data_source.rate_limit_per_minute,
                "region": config.data_source.region,
                "daily_cost_limit": config.data_source.daily_cost_limit,
            },
            "refund_rate": {
                "threshold": config.refund_rate.threshold,
                "penalty_score": config.refund_rate.penalty_score,
                "enabled": config.refund_rate.enabled,
            },
            "scoring": {
                "weights": config.scoring.weights,
                "content_density_saturation": config.scoring.content_density_saturation,
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)})


@app.post("/api/config")
async def save_config(request: dict):
    try:
        from config import AppConfig, RefundRateConfig, DataSourceConfig, ScoringConfig
        
        config = AppConfig()
        
        if "data_source" in request:
            ds = request["data_source"]
            config.data_source = DataSourceConfig(
                provider=ds.get("provider", "csv"),
                api_key=ds.get("api_key"),
                api_endpoint=ds.get("api_endpoint"),
                cache_ttl_seconds=ds.get("cache_ttl_seconds", 3600),
                rate_limit_per_minute=ds.get("rate_limit_per_minute", 60),
                region=ds.get("region", "US"),
                daily_cost_limit=ds.get("daily_cost_limit", 5.0),
            )
        
        if "refund_rate" in request:
            rr = request["refund_rate"]
            config.refund_rate = RefundRateConfig(
                threshold=rr.get("threshold", 20.0),
                penalty_score=rr.get("penalty_score", 10.0),
                enabled=rr.get("enabled", True),
            )
        
        if "scoring" in request:
            sc = request["scoring"]
            config.scoring = ScoringConfig(
                weights=sc.get("weights", {}),
                content_density_saturation=sc.get("content_density_saturation", 2000),
            )
        
        config.save()
        
        return {"success": True}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)})


@app.get("/api/categories")
async def get_categories(source: str = "fastmoss"):
    """
    获取可用类目列表
    用于前端下拉选择
    """
    try:
        from config import get_config
        config = get_config()
        
        if source == "fastmoss":
            if not config.data_source.api_key:
                return JSONResponse({
                    "error": "请先在配置中设置 FastMoss API Key",
                    "needs_config": True
                })
            
            from data_source import FastMossDataSource
            
            ds = FastMossDataSource(
                client_secret=config.data_source.api_key,
                base_url=config.data_source.api_endpoint,
                cache_ttl_seconds=config.data_source.cache_ttl_seconds,
                daily_cost_limit=config.data_source.daily_cost_limit,
                country=config.data_source.region,
                debug=True,
            )
            
            if not ds.connect():
                return JSONResponse({"error": "无法连接到 FastMoss API"})
            
            try:
                categories = ds.list_categories()
                return {
                    "categories": categories,
                    "region": config.data_source.region
                }
            finally:
                ds.disconnect()
        
        elif source == "kalodata":
            return JSONResponse({
                "error": "Kalodata API 适配器尚未实现"
            })
        
        return JSONResponse({"error": f"不支持的数据源: {source}"})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)})


@app.post("/api/fetch")
async def fetch_data(request: dict):
    try:
        source = request.get("source")
        category = request.get("category")
        limit = request.get("limit", 50)
        
        print(f"[API /fetch] 收到请求: source={source}, category={category}, limit={limit}")
        
        if source == "csv":
            return JSONResponse({"error": "CSV 数据源不支持实时抓取"})
        
        from config import get_config
        config = get_config()
        
        print(f"[API /fetch] 配置: provider={config.data_source.provider}, api_key={bool(config.data_source.api_key)}, country={config.data_source.region}")
        
        if not config.data_source.api_key:
            print(f"[API /fetch] 错误: 未设置 API Key")
            return JSONResponse({
                "error": f"请先在配置中设置 {source} 的 API Key",
                "needs_config": True
            })
        
        if source == "fastmoss":
            from data_source import FastMossDataSource
            from loader import load_trend_directory
            from scorer import score_category
            
            print(f"[API /fetch] 创建 FastMossDataSource...")
            
            ds = FastMossDataSource(
                client_secret=config.data_source.api_key,
                base_url=config.data_source.api_endpoint,
                cache_ttl_seconds=config.data_source.cache_ttl_seconds,
                daily_cost_limit=config.data_source.daily_cost_limit,
                country=config.data_source.region,
                debug=True,
            )
            
            print(f"[API /fetch] 连接到 FastMoss API...")
            if not ds.connect():
                return JSONResponse({"error": "无法连接到 FastMoss API"})
            
            try:
                print(f"[API /fetch] 获取达人数据...")
                creators = ds.fetch_creators(
                    category=category or "",
                    limit=limit,
                )
                
                print(f"[API /fetch] 获取到 {len(creators)} 个达人")
                
                if not creators:
                    return JSONResponse({
                        "error": f"未能获取到「{category}」的达人数据",
                        "category": category
                    })
                
                df = ds.fetch_creators_as_df(category or "", limit=limit)
                
                print(f"[API /fetch] 计算饱和度评分...")
                r = score_category(df, category or "实时类目")
                
                cost_summary = ds.get_cost_summary()
                print(f"[API /fetch] 成本统计: {cost_summary}")
                
                result = serialize_result(r)
                result["cost_summary"] = cost_summary
                result["creator_count"] = len(creators)
                
                return [result]
                
            finally:
                ds.disconnect()
        
        elif source == "kalodata":
            return JSONResponse({
                "not_implemented": True,
                "error": "Kalodata API 适配器尚未实现",
                "hint": "需要在 data_source.py 中实现 KalodataDataSource 类"
            })
        
        return JSONResponse({"error": f"不支持的数据源: {source}"})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765, reload=False)
