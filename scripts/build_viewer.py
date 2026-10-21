#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 metadata/library.json 生成自包含的浏览页面 index.html（可直接本地打开）。"""
import json
import os

OUT = "/workspace/radiology-image-library"

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>医学影像学图像库</title>
<style>
  :root {
    --bg: #0f1419; --panel: #1a2129; --panel2: #222c37; --border: #2e3b48;
    --text: #e6edf3; --muted: #8b98a5; --accent: #4da3ff; --accent2: #2ea87a;
    --warn: #e5734f;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: "PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif; }
  header { padding: 22px 28px 14px; border-bottom: 1px solid var(--border); background: var(--panel); position: sticky; top: 0; z-index: 20; }
  h1 { font-size: 20px; font-weight: 600; }
  .sub { color: var(--muted); font-size: 12.5px; margin-top: 5px; line-height: 1.6; }
  .stats { display: flex; gap: 18px; margin-top: 12px; flex-wrap: wrap; }
  .stat { background: var(--panel2); border: 1px solid var(--border); border-radius: 8px; padding: 7px 14px; font-size: 12.5px; }
  .stat b { color: var(--accent); font-size: 15px; }
  .filters { display: flex; gap: 10px; padding: 14px 28px; flex-wrap: wrap; align-items: center; border-bottom: 1px solid var(--border); background: var(--bg); position: sticky; top: 118px; z-index: 19; }
  select, input[type=search] {
    background: var(--panel2); color: var(--text); border: 1px solid var(--border);
    border-radius: 7px; padding: 7px 10px; font-size: 13px; outline: none;
  }
  input[type=search] { min-width: 260px; }
  .count { color: var(--muted); font-size: 13px; margin-left: auto; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; padding: 20px 28px 60px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; cursor: pointer; transition: transform .12s, border-color .12s; }
  .card:hover { transform: translateY(-3px); border-color: var(--accent); }
  .thumb { width: 100%; aspect-ratio: 1; object-fit: contain; background: #000; display: block; }
  .cinfo { padding: 9px 11px 11px; }
  .cid { font-size: 11px; color: var(--muted); margin-bottom: 5px; font-family: monospace; }
  .tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .tag { font-size: 11px; padding: 2px 8px; border-radius: 20px; border: 1px solid var(--border); color: var(--muted); }
  .tag.mod { color: var(--accent); border-color: rgba(77,163,255,.45); }
  .tag.dis { color: var(--warn); border-color: rgba(229,115,79,.5); }
  .tag.ok  { color: var(--accent2); border-color: rgba(46,168,122,.5); }
  .overlay { position: fixed; inset: 0; background: rgba(0,0,0,.72); display: none; z-index: 50; align-items: flex-start; justify-content: center; overflow-y: auto; padding: 30px 16px; }
  .overlay.open { display: flex; }
  .detail { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; max-width: 900px; width: 100%; padding: 22px 24px; }
  .detail .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .detail h2 { font-size: 17px; }
  .close { background: none; border: none; color: var(--muted); font-size: 26px; cursor: pointer; line-height: 1; }
  .close:hover { color: var(--text); }
  .dbody { display: grid; grid-template-columns: minmax(240px, 42%) 1fr; gap: 20px; margin-top: 16px; }
  @media (max-width: 720px) { .dbody { grid-template-columns: 1fr; } }
  .dimg { width: 100%; border-radius: 8px; background: #000; object-fit: contain; max-height: 480px; }
  .field { margin-bottom: 12px; }
  .field .k { font-size: 12px; color: var(--accent); margin-bottom: 4px; font-weight: 600; }
  .field .v { font-size: 13.5px; line-height: 1.75; }
  .pill { display: inline-block; background: var(--panel2); border: 1px solid var(--border); border-radius: 20px; padding: 2px 10px; margin: 2px 4px 2px 0; font-size: 12.5px; }
  .kp { background: var(--panel2); border-left: 3px solid var(--accent); border-radius: 6px; padding: 8px 11px; margin-bottom: 7px; font-size: 13px; line-height: 1.7; }
  .src { color: var(--muted); font-size: 12px; margin-top: 10px; line-height: 1.7; }
  .src a { color: var(--accent); text-decoration: none; }
  footer { color: var(--muted); text-align: center; font-size: 12px; padding: 0 0 40px; }
</style>
</head>
<body>
<header>
  <h1>医学影像学图像库</h1>
  <div class="sub">每张影像均标注：相关症状 · 解剖位置 · 知识点 ｜ 数据源：SLAKE、MedMNIST（CC BY 4.0，仅供学习研究，不用于临床诊断）</div>
  <div class="stats" id="stats"></div>
</header>
<div class="filters">
  <select id="f-mod"><option value="">全部模态</option></select>
  <select id="f-part"><option value="">全部部位</option></select>
  <select id="f-dis"><option value="">全部疾病/所见</option></select>
  <select id="f-abn">
    <option value="">正常+异常</option><option value="abn">仅异常</option><option value="norm">仅正常对照</option>
  </select>
  <input type="search" id="f-q" placeholder="搜索：疾病 / 症状 / 知识点 / 编号…">
  <span class="count" id="count"></span>
</div>
<div class="grid" id="grid"></div>
<footer>医学影像学图像库 · 由开源数据集 SLAKE 与 MedMNIST 构建</footer>
<div class="overlay" id="overlay"><div class="detail" id="detail"></div></div>
<script>
const LIB = __LIBRARY_JSON__;
const IMGS = LIB.images;
const $ = id => document.getElementById(id);

// stats
const st = LIB.stats;
$('stats').innerHTML =
  `<div class="stat">影像总数 <b>${st.total_images}</b></div>` +
  `<div class="stat">异常所见 <b>${st.abnormal}</b></div>` +
  Object.entries(st.by_modality).map(([k,v])=>`<div class="stat">${k} <b>${v}</b></div>`).join('') +
  `<div class="stat">疾病/所见类别 <b>${Object.keys(st.by_disease).length}</b></div>`;

// filter options
const mods=[...new Set(IMGS.map(i=>i.modality_zh))].sort();
const parts=[...new Set(IMGS.map(i=>i.body_part))].sort();
const diss=[...new Set(IMGS.flatMap(i=>i.diseases.map(d=>d.zh)))].sort();
mods.forEach(m=>$('f-mod').add(new Option(m,m)));
parts.forEach(p=>$('f-part').add(new Option(p,p)));
diss.forEach(d=>$('f-dis').add(new Option(d,d)));

function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

function match(i){
  const fm=$('f-mod').value, fp=$('f-part').value, fd=$('f-dis').value, fa=$('f-abn').value;
  const q=$('f-q').value.trim().toLowerCase();
  if(fm && i.modality_zh!==fm) return false;
  if(fp && i.body_part!==fp) return false;
  if(fd && !i.diseases.some(d=>d.zh===fd)) return false;
  if(fa==='abn' && !i.is_abnormal) return false;
  if(fa==='norm' && i.is_abnormal) return false;
  if(q){
    const hay=[i.image_id,i.body_part,i.modality_zh,
      ...i.diseases.map(d=>d.zh+d.en), ...i.symptoms, ...i.knowledge_points,
      ...i.organs.map(o=>(o.zh||'')+(o.en||''))].join(' ').toLowerCase();
    if(!hay.includes(q)) return false;
  }
  return true;
}

function render(){
  const list=IMGS.filter(match);
  $('count').textContent=`显示 ${list.length} / ${IMGS.length} 张`;
  $('grid').innerHTML=list.map(i=>`
    <div class="card" onclick="openDetail('${i.image_id}')">
      <img class="thumb" loading="lazy" src="${i.file}" alt="${i.image_id}">
      <div class="cinfo">
        <div class="cid">${i.image_id}</div>
        <div class="tags">
          <span class="tag mod">${i.modality}</span>
          <span class="tag">${i.body_part}</span>
          ${i.diseases.map(d=>`<span class="tag dis">${d.zh}</span>`).join('')}
          ${i.is_abnormal?'':'<span class="tag ok">正常对照</span>'}
        </div>
      </div>
    </div>`).join('');
}

function openDetail(id){
  const i=IMGS.find(x=>x.image_id===id); if(!i) return;
  $('detail').innerHTML=`
    <div class="top"><h2>${i.image_id}</h2>
      <button class="close" onclick="closeDetail()">&times;</button></div>
    <div class="dbody">
      <div><img class="dimg" src="${i.file}"></div>
      <div>
        <div class="field"><div class="k">检查方式</div><div class="v">${i.modality_zh}${i.plane?' · '+i.plane:''}</div></div>
        <div class="field"><div class="k">解剖位置</div><div class="v">${i.body_part}
          ${i.organs.length?'<br>'+i.organs.map(o=>`<span class="pill">${o.zh||o.en}</span>`).join(''):''}</div></div>
        <div class="field"><div class="k">疾病 / 影像所见</div><div class="v">
          ${i.diseases.length?i.diseases.map(d=>`<span class="pill">${d.zh}（${d.en}）</span>`).join(''):'<span class="pill">未见明确异常（正常对照）</span>'}</div></div>
        <div class="field"><div class="k">相关症状</div><div class="v">
          ${i.symptoms.map(s=>`<span class="pill">${esc(s)}</span>`).join('')}</div></div>
        <div class="field"><div class="k">知识点</div>
          ${i.knowledge_points.map(k=>`<div class="kp">${esc(k)}</div>`).join('')}</div>
        <div class="src">来源：${esc(i.source_dataset)}（${i.license}）·
          <a href="${i.source_url}" target="_blank">原始数据集</a> · 图像编号 ${esc(i.source_id)}</div>
      </div>
    </div>`;
  $('overlay').classList.add('open');
}
function closeDetail(){ $('overlay').classList.remove('open'); }
$('overlay').addEventListener('click',e=>{ if(e.target===$('overlay')) closeDetail(); });
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeDetail(); });
['f-mod','f-part','f-dis','f-abn'].forEach(id=>$(id).addEventListener('change',render));
$('f-q').addEventListener('input',render);
render();
</script>
</body>
</html>
"""


def main():
    with open(os.path.join(OUT, "metadata", "library.json"), encoding="utf-8") as f:
        lib = json.load(f)
    html = TEMPLATE.replace("__LIBRARY_JSON__", json.dumps(lib, ensure_ascii=False))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html generated:", os.path.getsize(os.path.join(OUT, "index.html")), "bytes")


if __name__ == "__main__":
    main()
