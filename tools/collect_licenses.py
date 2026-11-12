"""Retain dependency license files and declared versions in a Windows release."""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]

def collect(destination=None):
    destination=Path(destination or ROOT/'dist'/'MovieBox'/'licenses')
    destination.mkdir(parents=True,exist_ok=True)
    for path in (ROOT/'licenses').glob('*.txt'):
        shutil.copy2(path,destination/path.name)
    manifest=[]
    for name in ('PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','qrcode','pyinstaller','altgraph','packaging','pefile','pywin32-ctypes'):
        try:distribution=metadata.distribution(name)
        except metadata.PackageNotFoundError:continue
        record={'name':name,'version':distribution.version,'declared_license':distribution.metadata.get('License'),'license_files':[]}
        for relative in distribution.files or []:
            if 'license' not in str(relative).lower() and Path(str(relative)).name.lower() not in ('copying','copying.txt'):continue
            source=distribution.locate_file(relative)
            if not source.is_file():continue
            target=destination/name/Path(str(relative)).name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source,target)
            record['license_files'].append(target.relative_to(destination).as_posix())
        manifest.append(record)
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.is_file():shutil.copy2(python_license,destination/'Python-LICENSE.txt')
    (destination/'dependency-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

if __name__=='__main__':
    print('Dependency notices collected:',len(collect()))
