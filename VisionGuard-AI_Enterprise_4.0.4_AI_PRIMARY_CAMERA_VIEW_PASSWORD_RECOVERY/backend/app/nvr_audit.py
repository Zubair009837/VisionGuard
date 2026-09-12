import requests
from requests.auth import HTTPDigestAuth
from .config import NVRS

def audit_all():
    out=[]
    for n in NVRS:
        item={"nvr":n["name"],"ip":n["ip"],"status":"UNKNOWN","checks":{}}
        base=f"http://{n['ip']}:{n['port']}"; auth=HTTPDigestAuth(n['username'],n['password'])
        for key,ep in [("device","/ISAPI/System/deviceInfo"),("status","/ISAPI/System/status"),("time","/ISAPI/System/time"),("storage","/ISAPI/ContentMgmt/Storage"),("channels","/ISAPI/ContentMgmt/InputProxy/channels")]:
            try:
                r=requests.get(base+ep,auth=auth,timeout=10); item['checks'][key]={"http":r.status_code,"ok":r.ok,"body":r.text[:50000]}; item['status']='ONLINE' if r.ok else 'DEGRADED'
            except Exception as e: item['checks'][key]={"ok":False,"error":str(e)}; item['status']='OFFLINE'
        out.append(item)
    return out
