import requests, xml.etree.ElementTree as ET
from requests.auth import HTTPDigestAuth
from .config import NVRS

CODEC_MAP={"H264":"H.264","H265":"H.265","H.264":"H.264","H.265":"H.265"}
RES={"4K":(3840,2160),"4MP":(2560,1440),"1080P":(1920,1080),"720P":(1280,720),"2MP":(1920,1080),"3MP":(2048,1536)}

def _nvr(value):
    needle=str(value).strip().casefold()
    return next((n for n in NVRS if str(n.get('name')).casefold()==needle or str(n.get('id'))==needle),None)

def _get(nvr, endpoint):
    r=requests.get(f"http://{nvr['ip']}:{nvr['port']}{endpoint}",auth=HTTPDigestAuth(nvr['username'],nvr['password']),timeout=15,headers={"Accept":"application/xml"}); r.raise_for_status(); return r.text

def _put(nvr, endpoint, body):
    r=requests.put(f"http://{nvr['ip']}:{nvr['port']}{endpoint}",auth=HTTPDigestAuth(nvr['username'],nvr['password']),timeout=20,data=body.encode(),headers={"Content-Type":"application/xml; charset=UTF-8","Accept":"application/xml"}); r.raise_for_status(); return r.text

def build_encoding_xml(current, changes):
    root=ET.fromstring(current)
    def setv(tag,val):
        node=root.find('.//{*}'+tag)
        if node is None:
            node=ET.SubElement(root,tag)
        node.text=str(val)
    if changes.get('codec'): setv('videoCodecType', CODEC_MAP.get(str(changes['codec']).upper(),str(changes['codec'])))
    if changes.get('resolution'):
        w,h=RES.get(str(changes['resolution']).upper(), (None,None))
        if w:
            setv('videoResolutionWidth',w)
            setv('videoResolutionHeight',h)
            # Some firmware exposes a combined resolution field as well.
            node=root.find('.//{*}videoResolution')
            if node is not None:
                node.text=f"{w}*{h}"
    if changes.get('fps') is not None: setv('maxFrameRate',int(changes['fps'])*100)
    if changes.get('bitrate') is not None: setv('constantBitRate',int(changes['bitrate']))
    if changes.get('iframe') is not None: setv('GovLength',int(changes['iframe']))
    return ET.tostring(root,encoding='unicode')

def _verify_resolution(nvr, endpoint, expected):
    try:
        body = _get(nvr, endpoint)
        root = ET.fromstring(body)
        w = root.find('.//{*}videoResolutionWidth')
        h = root.find('.//{*}videoResolutionHeight')
        if w is None or h is None:
            return False, "Resolution fields not returned by NVR"
        got = (int(float(w.text or 0)), int(float(h.text or 0)))
        want = RES.get(str(expected).upper())
        return got == want, f"readback={got[0]}x{got[1]} expected={want[0]}x{want[1]}"
    except Exception as exc:
        return False, f"readback error: {exc}"

def apply_bulk(cameras, changes, streams=(1,2), dry_run=False):
    results=[]
    for c in cameras:
        nvr=_nvr(c.get('nvr'))
        if not nvr: results.append({"success":False,"error":"NVR not found","camera":c}); continue
        for stream in streams:
            endpoint=f"/ISAPI/Streaming/channels/{int(c['id']):d}{int(stream):02d}"
            try:
                current=_get(nvr,endpoint)
                body=build_encoding_xml(current,changes)
                if not dry_run: _put(nvr,endpoint,body)
                ok, verify = _verify_resolution(nvr, endpoint, changes.get("resolution")) if (not dry_run and changes.get("resolution")) else (True, "dry-run")
                results.append({"success":bool(ok),"nvr":nvr['name'],"channel":int(c['id']),"stream":stream,"endpoint":endpoint,"dry_run":dry_run,"verification":verify})
            except Exception as e:
                results.append({"success":False,"nvr":nvr['name'],"channel":int(c['id']),"stream":stream,"error":str(e)})
    return results
