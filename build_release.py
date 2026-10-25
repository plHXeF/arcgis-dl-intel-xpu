"""Build allowlisted release ZIP; exclude private config, data, environments and logs."""
from pathlib import Path
import argparse,hashlib,json,zipfile
HERE=Path(__file__).resolve().parent
FILES=['README.md','LICENSE','.gitignore','config.json','launch.cmd','patch_manager.py','profiles.py','constraints-xpu.txt',
       'configure.cmd','check.cmd','setup.cmd','start.cmd','smoke.cmd','rollback.cmd','build_release.py','verify_bundle.py','RELEASE_NOTES.md',
       'payload/__init__.py','payload/bootstrap.py','payload/adapter.py']
def build(output):
    manifest={}
    for name in FILES:
        data=(HERE/name).read_bytes()
        manifest[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:archive.writestr('arcgis-dl-intel-xpu/'+name,(HERE/name).read_bytes())
        archive.writestr('arcgis-dl-intel-xpu/MANIFEST.json',json.dumps(manifest,indent=2))
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n',encoding='ascii')
    print(json.dumps({'zip':str(output),'bytes':output.stat().st_size,'files':len(FILES)+1,'sha256':digest},indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default=str(HERE/'dist'/'arcgis-dl-intel-xpu-0.1.zip'))
    build(parser.parse_args().out)
