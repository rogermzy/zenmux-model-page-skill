"""Generate small synthetic ZenMux-shaped fixture pages (values are made up, shapes are real)."""
import json, os, sys
OUT = sys.argv[1]
os.makedirs(OUT + "/www/acme", exist_ok=True)

def comp(code, name, typ, val): return {"code": code, "name": name, "type": typ, "value": val}
CU = lambda v: comp("chargeUnit", "计价单位", "Select", v)
def bm(a, b): return comp("bizMinute", "业务分钟数（阶梯定价）", "NumberRange", json.dumps({"includeLowerLimit": True, "includeUpperLimit": False, "lowerLimit": a, "upperLimit": b}, separators=(",", ":")))
def item(code, zh, recs): return {"feeItemCode": code, "feeItemName": f"{zh}({code})", "selectedConstraint": ["chargeUnit"], "feeRecords": [{"feeRate": r, "components": cs} for r, cs in recs]}
NOISE = lambda: ',"cacheHite":[{"api":"chat.completions","biz_date":"20261031","value":50.5}],"Latency":[{"biz_hour":"2026103109","value":null},{"biz_hour":"2026103110","value":1234}],"Throughput":[{"biz_hour":"2026103109","value":null}]'

def prov(name, slug, ctx, maxo, disc, pv, apis, visible=1):
    return ('{"provider":%s,"provider_slug":"%s","providerIcon":"https://example.test/i.svg","visible":%d,"supports_streaming":true,'
            '"context_length":%d,"max_completion_tokens":%d,"pricing_discount":"%s","pricing_variable":%s,"suitable_api":"%s",'
            '"api_protocols":{"chat.completions":{"supported_parameters":["model","messages"],"supports_reasoning":1}}%s}'
            % (json.dumps(name), slug, visible, ctx, maxo, disc, json.dumps(pv, ensure_ascii=False), apis, NOISE()))

def page(model, provs, trows, visible, path):
    """model: dict (json), provs: list of provider JSON strings, trows: {id: text}"""
    flight = "0:[\"$\",\"div\"]\n"
    for rid, txt in trows.items():
        flight += "%s:T%x,%s\n" % (rid, len(txt.encode("utf-8")), txt)
    flight += '1:{"initialLocale":"en","initialModel":%s,"initialProviders":[%s],"initialRelatedModels":[{"slug":"acme/other"}]}\n' % (
        json.dumps(model, ensure_ascii=False, separators=(",", ":")), ",".join(provs))
    pushes, i = [], 0
    while i < len(flight):  # arbitrary chunking, like Next.js
        pushes.append(flight[i:i + 337]); i += 337
    scripts = "".join('<script>self.__next_f.push([1,%s])</script>' % json.dumps(c, ensure_ascii=False) for c in pushes)
    body = "<html><head><title>%s - ZenMux</title></head><body>%s<script>var x=1;</script>%s</body></html>" % (model["slug"], visible, scripts)
    open(path, "w", encoding="utf-8").write(body)

VIS_TEXT = ('<main><h1>%s</h1><h2>Providers</h2><div>Alpha Cloud</div><div>alpha</div>'
            '<div>-$0.2-0.4$0.1-0.2/ M tokens$0.8$0.4/ M tokensRead:0.02-0.040.01-0.02/ M tokensWrite:-/ M tokens1M</div>'
            '<div>Beta Host</div><div>beta</div><div>-$1/ M tokens$2/ M tokens128K</div></main>')

# 1. text model, discount 0.5, tiered $ref provider (CJK names) + inline-JSON provider
tiered = [item("prompt", "输入提示词的处理费用", [(0.2, [CU("millionTokens"), bm(0, 840)]), (0.4, [CU("millionTokens"), bm(840, 1440)])]),
          item("completion", "模型生成输出内容的费用", [(0.8, [CU("millionTokens")])]),
          item("input_cache_read", "缓存读取操作费用", [(0.02, [CU("millionTokens"), bm(0, 840)]), (0.04, [CU("millionTokens"), bm(840, 1440)])]),
          item("web_search", "网络搜索功能调用费用", [(0.01, [CU("counts")])])]
beta = [item("prompt", "输入提示词的处理费用", [(1, [CU("millionTokens")])]), item("completion", "模型生成输出内容的费用", [(2, [CU("millionTokens")]), (0, [CU("millionTokens"), comp("promptKToken", "prompt k", "NumberRange", json.dumps({"lowerLimit": "272", "upperLimit": "1000000", "includeLowerLimit": True, "includeUpperLimit": True}, separators=(",", ":")))])])]
model = {"name": "Acme: Tiered Text 1.0", "slug": "acme/tiered-text", "description": "A made-up text model.", "context_length": 1000000,
         "publish_time": "2026-10-01", "author": "acme", "authorName": "Acme", "input_modalities": "image,text", "output_modalities": "text",
         "visible": 1, "frontend_config": "", "aliases": ["tiered-text", "acme-tt"], "faqs": [{"question": "q", "answer": "a"}], "pricing_discount": "0.5"}
page(model, [prov("Alpha Cloud", "alpha", 1000000, 384000, "0.5", "$2f", "chat.completions,responses"),
             prov("Beta Host", "beta", 128000, 0, "1", json.dumps(beta, ensure_ascii=False, separators=(",", ":")), "chat.completions", visible=2)],
     {"2f": json.dumps(tiered, ensure_ascii=False, separators=(",", ":"))}, VIS_TEXT % "Acme: Tiered Text 1.0 Active50% OFF", OUT + "/www/acme/tiered-text")

# 2. video model, per-second and per-token fee items with resolution / videoInput conditions
vid = [item("video", "视频生成费用", [(0.084, [CU("seconds"), comp("resolution", "分辨率", "Select", "720p")]), (0.112, [CU("seconds"), comp("resolution", "分辨率", "Select", "1080p")])]),
       item("audio_and_video", "音频和视频生成费用", [(0.126, [CU("seconds"), comp("resolution", "分辨率", "Select", "720p")])])]
model = {"name": "Acme: Clip 2", "slug": "acme/clip-2", "description": "A made-up video model.", "context_length": 100000, "publish_time": "2026-09-09",
         "author": "acme", "authorName": "Acme", "input_modalities": "text,image", "output_modalities": "video", "visible": 1, "frontend_config": "",
         "aliases": [], "faqs": [], "pricing_discount": "1"}
page(model, [prov("Acme Video", "acme-video", 20000, 0, "1", "$30", "videos")], {"30": json.dumps(vid, ensure_ascii=False, separators=(",", ":"))},
     "<main><h1>Acme: Clip 2</h1><div>Acme Video</div></main>", OUT + "/www/acme/clip-2")

# 2b. transcription model (no page template): only the page data tells the type in --no-api mode
lis = [item("audio_in", "音频输入费用", [(0.006, [CU("seconds")])])]
model_l = {"name": "Acme: Listen 1", "slug": "acme/listen-1", "description": "A made-up transcription model.", "context_length": 0, "publish_time": "2026-08-08",
         "author": "acme", "authorName": "Acme", "input_modalities": "audio", "output_modalities": "transcription", "visible": 1, "frontend_config": "",
         "aliases": [], "faqs": [], "pricing_discount": "1"}
page(model_l, [prov("Acme Audio", "acme-audio", 0, 0, "1", "$31", "audio")], {"31": json.dumps(lis, ensure_ascii=False, separators=(",", ":"))},
     "<main><h1>Acme: Listen 1</h1><div>Acme Audio</div></main>", OUT + "/www/acme/listen-1")

# 2c. sitemap like https://zenmux.ai/sitemap-models.xml: model pages (two path segments), /provider/ pages and a list page
locs = ["models", "acme/tiered-text", "acme/clip-2", "acme/listen-1", "acme/twin", "other/twin", "acme/pic-1", "acme/clip-2.5", "provider/acme", "provider/other"]
open(OUT + "/www/sitemap-models.xml", "w", encoding="utf-8").write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join("  <url>\n    <loc>https://zenmux.ai/%s</loc>\n    <lastmod>2026-10-27</lastmod>\n    <priority>0.8</priority>\n  </url>\n" % l for l in locs)
    + "</urlset>\n")

# 3. broken: no flight data at all / providers marker missing
open(OUT + "/www/acme/no-flight", "w", encoding="utf-8").write("<html><body><h1>Just a page</h1></body></html>")
page(model, [], {}, "<main>x</main>", OUT + "/www/acme/tmp")
t = open(OUT + "/www/acme/tmp", encoding="utf-8").read().replace("initialProviders", "initialProvidersRenamed")
open(OUT + "/www/acme/renamed-markers", "w", encoding="utf-8").write(t); os.remove(OUT + "/www/acme/tmp")

# 4. models API fixture
def m(i, name, outs, ctx=1000000, pr=None):
    d = {"id": i, "object": "model", "display_name": name, "created": 1, "owned_by": i.split("/")[0], "input_modalities": ["text"], "output_modalities": outs,
         "capabilities": {"reasoning": False}, "context_length": ctx, "publish_time": "2026-10-01"}
    if pr is not None: d["pricings"] = pr
    return d
api = {"object": "list", "data": [
    m("acme/tiered-text", "Acme: Tiered Text 1.0", ["text"], pr={"prompt": [{"value": 0.1, "unit": "perMTokens", "currency": "USD"}, {"value": 0.2, "unit": "perMTokens", "currency": "USD"}]}),
    m("acme/clip-2", "Acme: Clip 2", ["video"], 100000, {"video": [{"value": 0.084, "unit": "perSecond", "currency": "USD"}]}),
    m("acme/listen-1", "Acme: Listen 1", ["transcription"]),
    m("acme/embed-1", "Acme: Embed 1", ["embeddings"]),
    m("acme/mystery", "Acme: Mystery", []),
    m("acme/twin", "Acme: Twin", ["text"]), m("other/twin", "Other: Twin", ["text"]),
    m("acme/pic-1", "Acme: Pic 1", ["text", "image"]),
]}
json.dump(api, open(OUT + "/models-api.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.makedirs(OUT + "/www/api/v1", exist_ok=True)   # the same list, served as the live API (extensionless file)
json.dump(api, open(OUT + "/www/api/v1/models", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok")
