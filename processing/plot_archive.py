"""Keep plot artifacts in one flat directory, and replace HTML embeds with links."""
import hashlib
import json
import os
import shutil
from pathlib import Path
from urllib.parse import unquote
from bs4 import BeautifulSoup

def archive(root, group=None):
    root=Path(root).resolve();dest=root/'plots';dest.mkdir(exist_ok=True)
    moved={}
    directories=[root/group] if group else [root,root/'size_plots',root/'occupancy_plots',root/'occupancy_plots_commercial_excluded',root/'neighborhood_occupancy_plots',root/'direct_listing_calls']
    for directory in directories:
        for source in list(directory.glob('*')):
            if source.suffix.lower() not in ('.svg','.png'):continue
            source=source.resolve()
            assert source.is_relative_to(root)
            name=(directory.name+'__' if directory!=root else '')+source.name
            target=(dest/name).resolve();assert target.is_relative_to(dest)
            if target.exists():
                if target.read_bytes()==source.read_bytes():source.unlink()
                else:
                    suffix=hashlib.sha256(source.read_bytes()).hexdigest()[:10]
                    previous=dest/(target.stem+'__previous_'+hashlib.sha256(target.read_bytes()).hexdigest()[:10]+target.suffix)
                    if not previous.exists():shutil.copy2(target,previous)
                    shutil.move(str(source),str(target))
            else:shutil.move(str(source),str(target))
            moved[source]=target
    # Update static references and remove images from every analysis HTML page.
    for page in root.rglob('*.html'):
        if '.git' in page.parts or 'vendor' in page.parts or 'plots' in page.relative_to(root).parts:continue
        original=page.read_text(encoding='utf-8');soup=BeautifulSoup(original,'html.parser');changed=False
        for tag,attribute in [(t,'href') for t in soup.find_all(href=True)]+[(t,'src') for t in soup.find_all(src=True)]:
            value=tag.get(attribute,'')
            if not value or '://' in value or value.startswith(('data:','#')):continue
            source=(page.parent/unquote(value.split('#')[0])).resolve()
            if source in moved:
                tag[attribute]=Path(os.path.relpath(moved[source],page.parent)).as_posix();changed=True
        for image in list(soup.find_all('img')):
            src=image.get('src','')
            if src.endswith(('.png','.svg')):
                link=soup.new_tag('a',href=src);link.string='Open plot: '+(image.get('alt') or Path(src).name)
                image.replace_with(link);changed=True
        if changed:page.write_text(str(soup),encoding='utf-8')
    manifest_path=root/'publication_manifest.json'
    if manifest_path.exists() and moved:
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        for item in manifest:
            path=(root/item['path']).resolve()
            if path in moved:item['path']=moved[path].relative_to(root).as_posix()
        manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return moved
