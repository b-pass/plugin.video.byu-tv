#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import re
import requests
import time
import json
from urllib.parse import parse_qsl, quote_plus

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import xbmcvfs

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:156.0) Gecko/20100101 Firefox/156.0'
HANDLE = -1
API_BASE = 'https://api.byub.org/'
BASIC_HEADERS = {
    'User-Agent':UA,
    'Accept':'*/*',
    'Referer':'https://www.byutv.org/',
    'Origin':'https://www.byutv.org',
    'Accept-Language' : str(xbmc.getLanguage(xbmc.ISO_639_1)).lower(),
    #"Sec-Fetch-Dest":"empty",
    #"Sec-Fetch-Mode":"cors",
    #"Sec-Fetch-Site":"cross-site",
}
API_HEADERS = dict(BASIC_HEADERS)
API_HEADERS.update({
    'x-byub-client':'byutv-web-dk94tsvophi',
    'x-byub-clientversion':'5.69.0',
    'x-byub-location': 'us',
    'x-byub-offset':'240',
    'Host':'api.byub.org',
    'x-byub-isauthenticated':'false',
})

def log(txt, level=xbmc.LOGINFO):
    xbmc.log('byu-tv : ' + str(txt), level=level)
    
def get_json(url, **params):
    if 'x-byub-session' not in API_HEADERS:
        data = None
        try:
            data = xbmcvfs.File('special://profile/addon_data/plugin.video.byu-tv/data.json','rb').read()
        except Exception:
            pass
        data = json.loads(data) if data else {}
        e = data.get('expires', 0)
        if e+60 < time.time():
            with requests.Session() as s:
                c = {}
                if 'did' in data:
                    c['did'] = data['did']
                if 'sid' in data:
                    c['sid'] = data['sid']
                
                s.get('https://www.byutv.org', headers=BASIC_HEADERS, cookies=c)
                data['expires'] = time.time()+3600
                try:
                    data['sid'] = s.cookies['sid']
                except Exception:
                    pass
                try:
                    data['did'] = s.cookies['did']
                except Exception:
                    pass
            xbmcvfs.File('special://profile/addon_data/plugin.video.byu-tv/data.json','wb').write(json.dumps(data))
        if 'sid' in data:
            API_HEADERS['x-byub-session'] = data['sid']
        if 'did' in data:
            API_HEADERS['x-byub-device'] = data['did']
        #log(str(API_HEADERS))
    resp = requests.get(API_BASE + url, params=params, headers=API_HEADERS)
    if resp.status_code != 200:
        log(f'GET {url} failed: code {resp.status_code}: {resp.text}')
        return {}
    else:
        return resp.json()

def list_categories():
    items = []
    resp = get_json('views/v2/public/pages/shows')
    for s in resp.get('sections', []):
        if s.get('type', '') != 'list-section':
            continue
        for cat in s.get('lists', []):
            id = cat.get('id', '')
            if not id:
                continue
            name = cat.get('title', '???')
            item = xbmcgui.ListItem(label=name)
            item.setInfo('video', {'title':name, 'set':name})
            url = f'{PLUGIN_BASE}?action=category&id={id}'
            items.append((url, item, True))
    log(f'Listed {len(items)} categories')
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.endOfDirectory(HANDLE)

def safe_get(o, *args, default=None):
    for a in args:
        try:
            o = o[a]
        except Exception:
            return default
    return o

def list_category(listid):
    items = []
    cursor = ''
    MAX = 50
    while True:
        resp = get_json('views/v2/public/lists/content-list/'+listid, nextCursor=cursor, limit=MAX)
        
        for show in resp.get('items', []):
            if show.get('sourceType', '') not in ['content','show', 'oneoff', 'episode']:
                continue

            content = safe_get(show, 'display', 'hover')
            if not content:
                continue

            id = safe_get(content, 'targets', 0, 'value')
            if not id:
                continue

            title = safe_get(content, 'title', 0, 'value')
            subtitle = safe_get(content, 'subtitle', 0, 'value')
            desc = safe_get(content, 'description', 0, 'value')

            item = xbmcgui.ListItem(label=title)
            if subtitle:
                item.setLabel2(subtitle)
            art = getArt(show.get('display', {}))
            if art:
                item.setArt(art)
            item.setInfo('video', {
                'title':title,
                'tvshowtitle':title,
                'set':title,
                'setoverview':desc,
                'plot':desc,
                'plotoutline':subtitle or desc,
                'mediatype':'tvshow'
            })

            if show['sourceType'] == 'oneoff':
                url = f'{PLUGIN_BASE}?action=play&id={id}'
                item.setProperty('IsPlayable', 'true')
                items.append((url, item, False))
            else:
                url = f'{PLUGIN_BASE}?action=show&id={id}&fanart=' + quote_plus(art.get('fanart', ''))
                items.append((url, item, True))

        p = safe_get(resp, 'pageInfo')
        if p and p.get('hasNextPage', False):
            cursor = p.get('endCursor', '')
        else:
            break
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    xbmcplugin.endOfDirectory(HANDLE)

def getArt(show):
  try:
    art = {}
    for c in ('standard', 'hover', 'portrait'):
        i = safe_get(show, c, 'images', 'primary')
        if i is None:
            continue
        if 'baseUrl' not in i or 'type' not in i:
            continue
        url = i['baseUrl'] + '/'
        if 'imageId' in i:
            url += i['imageId']
        elif 'id' in i:
            url += i['id']
        else:
            continue
        #aspect = 1
        #try:
        #  x = i.get('aspectRatio', '').split(':')
        #  if len(x) == 2:
        #    aspect = float(x[1]) / float(x[0])
        #except Exception: pass
        url += '/512xauto.jpg'
        art[i['type']] = url
    
    mapping = [
        ('badge','icon'),
        ('content-badge','icon'),
        ('content','landscape'),
        ('content-alternate','landscape'),
        ('content','thumb'),
        ('content-alternate','thumb'),
        ('content','fanart'),
        ('content-alternate','fanart'),
        ('content-branded','fanart'),
        ('content-alternate-branded','fanart'),
        ('content-branded','banner'),
        ('content-alternate-branded','banner'),
        ('content-portrait-branded','poster'),
        ('content-portrait','poster'),
        ('logo','logo'),
        ('logo','clearlogo'),
        ('logo','icon'),
        ('badge','poster'),
        ('badge','logo'),
        ('content-badge','logo'),
    ]
    
    val = {}
    
    for (s,d) in mapping:
        if d in val:
            continue
        if s in art:
            val[d] = art[s]

    return val
  except Exception as e:
    log('Art failure:' + str(e))
    import traceback
    traceback.print_exc()
    return {}

def find_section(name, sections):
    for s in sections:
        if s.get('label', '').lower() == name.lower():
            return s
    
    for s in sections:
        if 'sections' in s:
            x = find_section(name, s['sections'])
            if x:
                return x
    
    return {}

def list_show(showid, fanart='', flat=False):
    items = []
    eps = []
    n = 0
    art = None
    resp = get_json('views/v2/public/pages/' + showid)
    art = getArt(resp)
    if not art:
        art = {'fanart':fanart, 'landscape':fanart} if fanart else {}
    esect = find_section("Episodes", resp.get('sections', []))
    for season in esect.get('lists', []):
        if season.get('type', '') != 'content-list':
            ctype = season.get('content', {}).get('type','').lower()
            if ctype == 'episode' or ctype == 'oneoff':
                (item,url) = playable(season)
                if item and url:
                    eps.append((url, item, False))
            continue
        
        id = season.get('id', '')
        if not id:
            continue
        
        name = season.get('title', '')
        if not name:
            name = season.get('name', '')

        n += 1
        snum = n
        try:
            if name.startswith('Season'):
                snum = int(name[6:].strip())
        except Exception:
            pass
        
        if flat:
            items += list_season(id, snum, listonly=True)
            continue

        item = xbmcgui.ListItem(label=name)
        info = {
            'title':name, 
            'set':name, 
            'setoverview':name, 
            'season':snum, 
            'mediatype':'season',
        }
        
        if 'title' in resp:
            info['tvshowtitle'] = resp.get('title', '')
        
        if 'subtitle' in resp:
            info['plot'] = resp.get('subtitle', '')
        
        if art:
            item.setArt(art)
        
        item.setInfo('video', info)
        url = f'{PLUGIN_BASE}?action=season&n={snum:03d}&id={id}'
        items.append((url, item, True))
    
    if items:
        items = sorted(items, key=lambda t: t[0])
        
    # show has un-season'd episodes, list them too
    if eps:
        eps = sorted(eps, key=lambda t: t[0])
        items += eps

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.setContent(HANDLE, 'seasons' if not flat else 'episodes')
    xbmcplugin.endOfDirectory(HANDLE)

def playable(ep, n=0, snum=0, fanart=''):
    disp = safe_get(ep, 'display', 'standard')
    if not disp:
        disp = safe_get(ep, 'display', 'portrait')
    if not disp:
        disp = safe_get(ep, 'display', 'hover')
    if not disp:
        return (None,None)

    id = safe_get(disp, 'targets', 0, 'value')
    if not id:
        return (None, None)

    title = safe_get(disp, 'title', 0, 'value')
    subtitle = safe_get(disp, 'primaryInfo', 0, 'value')
    desc = safe_get(disp, 'description', 0, 'value', default='')
    info = {
        'title':title,
        'tvshowtitle':title,
        'set':title,
        'setoverview':desc,
        'plot':desc,
        'plotoutline':subtitle or desc,
        'mediatype':'tvshow',
    }

    dur = safe_get(disp, 'secondaryInfo', 0, 'value')
    if isinstance(dur, str) and dur.endswith('m'):
        d = 0
        try:
            if 'h' in dur:
                p = dur.split('h')
                if len(p) > 1:
                    d = int(p[0])
                    dur = p[1]
            d += int(dur[:-1])
        except Exception:
            pass
        if d:
            info['duration'] = int(d)
    
    if snum and n:
        info['mediatype'] = 'episode'
        info['season'] = snum
        info['episode'] = n
    else:
        info['mediatype'] = 'video'

    item = xbmcgui.ListItem(title)
    item.setInfo('video', info)
    item.setArt(getArt(ep.get('display', {})))

    #if media.get('requireLogin', False) and not xbmcplugin.getSetting(HANDLE, 'email'):
    #    item.setProperty('Overlay', 'locked')
    #    #item.setProperty('IsPlayable', 'true')
    #    url = f'{PLUGIN_BASE}?action=locked&id={id}'
    #else:
    item.setProperty('IsPlayable', 'true')
    url = f'{PLUGIN_BASE}?action=play&id={id}'

    return (item, url)
    
def list_season(sid, snum, fanart='', listonly=False):
    n = 0
    items = []

    resp = get_json('views/v2/public/lists/content-list/' + sid, limit=100)
    for ep in resp.get('items', []):
        if ep.get('sourceType', '').lower() not in ['content', 'episode', 'show', 'oneoff']:
            continue
        
        n += 1
        
        (item, url) = playable(ep, n, snum, fanart)
        if item and url:
            items.append((url, item, False))
    
    if listonly:
        return items
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    xbmcplugin.setContent(HANDLE, 'episodes')
    xbmcplugin.endOfDirectory(HANDLE)
    return None

def play_video(vid):
    content = get_json('views/v2/public/content/'+vid)
    if not content:
        log('Unable to fetch content info for '+vid)
        return

    media_id = content.get('mediaId', '')
    if not media_id:
        log(f'Unable to find media_id for {vid} in {content}')
        return

    vr = get_json(f'media/v1/public/media/{media_id}?')
    m = {}
    url = None
    for a in vr.get('assets', []):
        if a.get('assetType', '').lower().startswith('dash'):
            m = a
            break
    if not m:
        log('No DASH section found in media')
        m = vr
    
    #url = m.get('url', '')
    url = m.get('preplayUrl', '')
    if url:
        pp = requests.get(url, headers=BASIC_HEADERS)
        url = pp.json().get('playURL', '') if pp.status_code == 200 else ''
    url = m.get('url', url)
    
    if url:
        url = url.replace('.m3u8', '.mpd')
        log(f'fetch mpd {url}')
        mpdresp = requests.get(url, headers=BASIC_HEADERS)
        log(f'got mpd {url} - len {len(mpdresp.text)}')
        m = re.search(r'"([^"]*/wv\?[^"]*)"', mpdresp.text)
        lic = '|||'
        if m:
            lic = m.group(1).replace('&amp;', '&')
            # the web client doesn't use the loadbalanced host provided in the MPD, it goes directly to content.uplynk.com instead
            #m = re.search(r'^(.*?://)?([a-zA-Z0-9_.-]+?)(\.uplynk\.com/wv.*)$', lic)
            #if m:
            #    lic = (m.group(1) or '') + 'content' + m.group(3)
            lic += '|Referer=https://www.byutv.org/&Origin=https://www.byutv.org&User-Agent='+UA+'|R{SSM}|'
        else:
            log(f'No wv license in {url}', level=xbmc.LOGERROR)

        ish_ok = False
        ishplugin = 'inputstream.adaptive'
        try:
            import inputstreamhelper
            ish = inputstreamhelper.Helper('mpd', 'com.widevine.alpha')
            ish_ok = ish.check_inputstream()
            if ish_ok:
                ishplugin = ish.inputstream_addon
        except Exception as e:
            log(f'Failed to check inputstreamhelper: {e}')
        
        if not ish_ok:
            skip = False
            try:
                skip = xbmcplugin.getSetting(HANDLE,'forcePlay').upper()[0] == 'T'
            except Exception:
                pass
            if not skip:
              skip = xbmcgui.Dialog().yesno('Widevine DRM required',
                    'WideVine CDM not detected.\nThis video is protected by DRM. You must use the InputStreamHelper kodi plugin to install WideVine.',
                    nolabel='Cancel',
                    yeslabel='Continue',
                    autoclose=30000,
                    defaultbutton=xbmcgui.DLG_YESNO_NO_BTN)
            if not skip:
                log('Play failed because if missing Widevine')
                xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem(path='', offscreen=True))
                return

        log(f'Resolved to {url}')
        item = xbmcgui.ListItem(path=url, offscreen=True)
        item.setProperty('inputstream', ishplugin)
        item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        if len(lic) > 3:
          item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
          item.setProperty('inputstream.adaptive.license_key', lic)
        #item.setProperty('inputstream.adaptive.license_key', 'https://content.uplynk.com/wv|Content-Type=application/octet-stream&Referer=https://www.byutv.org/&Origin=https://www.byutv.org&User-Agent='+UA+'|R{SSM}|')
        #item.setProperty('inputstream.adaptive.license_key', 'http://localhost:8000/wv|Content-Type=application/octet-stream&Referer=https://www.byutv.org/&Origin=https://www.byutv.org&User-Agent='+UA+'|R{SSM}|')
        item.setProperty('inputstream.adaptive.stream_headers', 'User-Agent='+UA+'&Referer=https://www.byutv.org/&Origin=https://www.byutv.org')
        item.setMimeType('application/dash+xml')
        item.setContentLookup(False)
        item.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(HANDLE, True, item)
    else:
        log(f'No video URL? vid={vid}, resp={vr}', level=xbmc.LOGERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem(path='', offscreen=True))

def locked(vid):
    xbmcgui.Dialog().ok('Login Required', 'You must register/login to BYUtv to view this.\nEnter your login information in the addon settings.')

if __name__ == '__main__':
    PLUGIN_BASE = sys.argv[0]
    HANDLE = int(sys.argv[1])

    if len(sys.argv) > 2 and len(sys.argv[2]) > 1:
        args = dict(parse_qsl(sys.argv[2][1:]))
    else:
        args = {}
    action = args.get('action', None)
    if not action:
        list_categories()
    elif action == 'category':
        list_category(args.get('id'))
    elif action == 'show':
        flat = False
        try:
            flat = xbmcplugin.getSetting(HANDLE, 'noSeasons').upper()[:1] == 'T'
        except Exception:
            pass
        list_show(args.get('id'), args.get('fanart', ''), flat=flat)
    elif action == 'season':
        list_season(args.get('id'), int(args.get('n', 0)), fanart=args.get('fanart', ''))
    elif action == 'play':
        play_video(args.get('id'))
    elif action == 'locked':
        locked(args.get('id'))
    else:
        log(f'Unknown action in params: {args}', level=xbmc.LOGERROR)
