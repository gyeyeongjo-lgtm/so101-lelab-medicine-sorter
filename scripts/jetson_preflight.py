"""Read-only file/metadata preflight. Never opens devices or queries a GPU driver."""
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json,os,platform,re,shutil
from pathlib import Path
from check_vla_cameras import load_config
from vla_data import ROOT,write_new


def collect(probe=False):
    cameras=load_config(ROOT/'configs/vla_cameras.yaml')
    result={'status':'READ_ONLY_FILE_PROBE' if probe else 'LOCAL_DRY_RUN','camera_schema':'PASS',
        'physical_camera_configured':all(c['device'] for c in cameras['cameras'].values()),
        'device_open':0,'gpu_driver_queries':0,'os':None,'jetpack_l4t':None,'cuda_build':None,
        'torch':None,'lerobot':None,'memory':None,'disk_free_bytes':None,'by_id':None,'serial_owners':None}
    if not probe:return result
    result['os']=platform.platform()
    path=Path('/etc/nv_tegra_release');result['jetpack_l4t']=path.read_text()[:512] if path.is_file() else 'UNAVAILABLE'
    for name in ('torch','lerobot'):
        try:result[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:result[name]='NOT_INSTALLED'
    try:
        text=Path(importlib.metadata.distribution('torch').locate_file('torch/version.py')).read_text()
        match=re.search(r'^cuda(?:\s*:\s*\w+)?\s*=\s*[\'"]([^\'"\n]+)',text,re.M)
        result['cuda_build']=match.group(1) if match else 'UNAVAILABLE'
    except (OSError,importlib.metadata.PackageNotFoundError):pass
    mem=Path('/proc/meminfo');result['memory']={line.split(':')[0]:line.split(':')[1].strip() for line in mem.read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))} if mem.is_file() else None
    result['disk_free_bytes']=shutil.disk_usage(ROOT).free
    result['by_id']={base:[{'name':p.name,'target':os.readlink(p)} for p in Path(base).iterdir() if p.is_symlink()] if Path(base).is_dir() else [] for base in ('/dev/serial/by-id','/dev/v4l/by-id')}
    owners={};denied=0
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            for fd in (proc/'fd').iterdir():
                try:target=os.readlink(fd)
                except OSError:continue
                if target.startswith(('/dev/ttyACM','/dev/ttyUSB')):owners.setdefault(target,set()).add(int(proc.name))
        except (PermissionError,FileNotFoundError):denied+=1
    result['serial_owners']={k:sorted(v) for k,v in owners.items()};result['proc_scan_inaccessible']=denied
    result['ownership_note']='Advisory /proc snapshot, not exclusive ownership proof or authorization'
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group();m.add_argument('--dry-run',action='store_true');m.add_argument('--probe',action='store_true')
    p.add_argument('--out',type=Path);a=p.parse_args(argv);result=collect(a.probe)
    if a.out or a.probe:
        out=a.out or ROOT/'reports'/('jetson_preflight_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'.json')
        out.parent.mkdir(parents=True,exist_ok=True);write_new(out,result)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
