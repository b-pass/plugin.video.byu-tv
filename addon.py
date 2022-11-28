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

HANDLE = -1
API_BASE = 'https://api.byub.org/'
BASIC_HEADERS = {
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0',
    'Accept':'application/json, text/plain, */*',
    #'Referer':'https://www.byutv.org/',
    #'Origin':'https://www.byutv.org',
    #"Sec-Fetch-Dest":"empty",
    #"Sec-Fetch-Mode":"cors",
    #"Sec-Fetch-Site":"cross-site",
}
API_HEADERS = dict(BASIC_HEADERS)
API_HEADERS.update({
    'x-byub-client':'byutv-web-dk94tsvophi',
    'x-byub-clientversion':'5.29.41',
    'x-byub-location': 'us',
    'Host':'api.byub.org',
    'Accept':'application/json, text/plain, */*',
})

def log(txt, *args, level=xbmc.LOGINFO):
    if not args:
        xbmc.log('byu-tv : ' + str(txt), level=level)
    else:
        xbmc.log('byu-tv : ' + txt.format(*args), level=level)

def get_json(url, **params):
    if 'x-byub-session' not in API_HEADERS:
        data = None
        try:
            data = xbmcvfs.File('special://profile/addon_data/plugin.video.byu-tv/data.json','rb').read()
        except:
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
                except:
                    pass
                try:
                    data['did'] = s.cookies['did']
                except:
                    pass
            xbmcvfs.File('special://profile/addon_data/plugin.video.byu-tv/data.json','wb').write(json.dumps(data))
        if 'sid' in data:
            API_HEADERS['x-byub-session'] = data['sid']
        if 'did' in data:
            API_HEADERS['x-byub-device'] = data['did']
        #log(str(API_HEADERS))
    resp = requests.get(API_BASE + url, params=params, headers=API_HEADERS)
    if resp.status_code != 200:
        log('GET {} failed: code {}', url, resp.status_code)
        return {}
    else:
        return resp.json()

def do_login():
    info = {
        'email':xbmcplugin.getSetting(HANDLE, 'email'),
        'password':xbmcplugin.getSetting(HANDLE, 'password')
    }
    resp = requests.post('https://accounts-api.byub.org/v1/public/login', json=info, headers=API_HEADERS)
    # TODO save tokens
    auth = resp.json()
    API_HEADERS['Authorization'] = auth['access_token']
    auth['expiration'] += time.time() - 60
    xbmcplugin.setSetting(HANDLE, 'auth', json.dumps(auth))

def list_categories():
    items = []
    # pageid 56c21af3-61cc-4b15-b21c-ec68762fcfeb = magic number for main category listing
    resp = get_json('views/v1/public/pages/shows')
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
            url = '{0}?action=category&id={1}'.format(PLUGIN_BASE, id)
            items.append((url, item, True))
    log('Listed {} categories', len(items))
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.endOfDirectory(HANDLE)

def list_category(listid):
    items = []
    start = 0
    MAX = 50
    while True:
        resp = get_json('views/v1/public/lists/content-list/'+listid, nextCursor=start, limit=MAX)
        for show in resp.get('items', []):
            if show.get('sourceType', '') != 'content':
                continue
            
            content = show.get('content', {})
            if content.get('type', None) != 'show':
                continue

            id = show.get('target', {}).get('value', None)
            if not id:
                id = show.get('target', {}).get('pageId', None)
            if not id:
                id = show.get('sourceId', None)
            if not id:
                continue
            
            item = xbmcgui.ListItem(label=show['title'])
            if show.get('subtitle', ''):
                item.setLabel2(show['subtitle'])
            art = getArt(show.get('images', []), type='content-branded')
            item.setArt(art)
            item.setInfo('video', {
                'title':show['title'],
                'tvshowtitle':show['title'],
                'set':show['title'],
                'setoverview':show.get('description', ''),
                'plot':show.get('description', ''),
                'plotoutline':show.get('subtitle', ''),
                'mediatype':'tvshow'
            })
            url = '{0}?action=show&id={1}&fanart={2}'.format(PLUGIN_BASE, id, quote_plus(art.get('fanart', '')))
            items.append((url, item, True))
        n = len(resp.get('items', []))
        if n < MAX:
            break
        start += n
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    xbmcplugin.endOfDirectory(HANDLE)

def getArt(img, type='badge'):
    art = {}
    for i in img:
        if i.get('type', type) != type:
            continue
        if 'baseUrl' not in i:
            continue
        url = i['baseUrl'] + '/'
        if 'imageId' in i:
            url += i['imageId']
        elif 'id' in i:
            url += i['id']
        else:
            continue
        x = i.get('aspectRatio', '').split(':')
        if len(x) == 2:
            aspect = float(x[1]) / float(x[0])
        else:
            aspect = 1
        url += '/512x' + str(int(aspect * 512)) + '.jpg'
        return {'fanart':url, 'landscape':url, 'icon':url, 'thumb':url}
    
    if img and 'branded' not in type:
        i = getArt(img, type+"-branded")
        if i: return i
    
    if img and 'alternate' not in type:
        i = getArt(img, type+"-alternate")
        if i: return i
    
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

def list_show(showid, fanart=''):
    items = []
    eps = []
    n = 0
    resp = get_json('views/v1/public/pages/' + showid)
    esect = find_section("Episodes", resp.get('sections', []))
    for season in esect.get('lists', []):
        if season.get('type', '') != 'content-list':
            continue
        
        #if season.get('type', '') != 'ShowSeason':
        #    if season.get('contentType', '') == 'Episode':
        #        eps.append(season.get('id', ''))
        #    continue
        
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
        except:
            pass

        item = xbmcgui.ListItem(label=name)
        item.setInfo('video', {
            'title':name, 
            'set':name, 
            'setoverview':name, 
            'season':snum, 
            'mediatype':'season'
        })
        
        if fanart:
            item.setArt({'fanart':fanart, 'landscape':fanart})
        
        url = f'{PLUGIN_BASE}?action=season&n={snum:03d}&id={id}'
        items.append((url, item, True))
    
    if items:
        items = sorted(items, key=lambda t: t[0])
        xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    
    # show has un-season'd episodes, list them too
    for e in eps:
        if e:
            ei = list_season(e, 0, listonly=True, fanart=fanart)
            xbmcplugin.addDirectoryItems(HANDLE, ei, len(ei))

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    #xbmcplugin.setContent(HANDLE, 'season')
    xbmcplugin.endOfDirectory(HANDLE)

def list_season(sid, snum, fanart='', listonly=False):
    n = 0
    items = []

    resp = get_json('views/v1/public/lists/content-list/' + sid, limit=100)
    for ep in resp.get('items', []):
        if ep.get('sourceType', '').lower() != 'content':
            continue
    
        n += 1
        
        media = ep.get('media', {})
        if not media:
            continue

        id = media.get('id', None)
        if not id:
            id = ep.get('target', {}).get('value', None)
            if not id:
                id = ep.get('id', '')
            if not id:
                continue
        
        info = {
            'tvshowtitle':ep['title'],
            'plot':ep.get('description', '')
        }

        #if 'subtitle' in ep:
        #    info['title'] = ep['subtitle']
        #else:
        info['title'] = ep['title']
        
        item = xbmcgui.ListItem(info['title'])

        art = getArt(ep.get('images', []), type='content')
        if fanart:
            art['fanart'] = fanart
            art['landscape'] = fanart
        item.setArt(art)
        
        if media.get('stop', ''):
            dur = 0
            p = media.get('stop', '').split(':')
            while p:
                dur = dur*60 + float(p[0])
                del p[0]
            if dur:
                info['duration'] = int(dur)
        if snum:
            info['mediatype'] = 'episode'
            info['season'] = snum
            info['episode'] = n
        else:
            info['mediatype'] = 'video'
        
        if media.get('requireLogin', False) and not xbmcplugin.getSetting(HANDLE, 'email'):
            item.setProperty('Overlay', 'locked')
            #item.setProperty('IsPlayable', 'true')
            url = '{0}?action=locked&id={1}'.format(PLUGIN_BASE, id)
        else:
            item.setProperty('IsPlayable', 'true')
            url = '{0}?action=play&id={1}'.format(PLUGIN_BASE, id)
        
        item.setInfo('video', info)
        items.append((url, item, False))
    
    if listonly:
        return items
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    xbmcplugin.setContent(HANDLE, 'episode')
    xbmcplugin.endOfDirectory(HANDLE)

def play_video(vid):
    vr = get_json('media/v1/public/media/'+vid+'/')
    m = {}
    url = None
    for a in vr.get('assets', []):
        if a.get('assetType', '').lower().startswith('dash'):
            m = a
            break
    if not m:
        log('No DASH section found in media/v1')
        m = vr
    
    url = m.get('url', '')
    #url = m.get('preplayUrl', '')
    #if url:
    #    pp = requests.get(url, headers=BASIC_HEADERS)
    #    if pp.status_code == 200:
    #        url = pp.json().get('playURL', '')
    #    else:
    #        url = ''
    #if not url:
    #    url = m.get('url', '')
    
    if url:
        url = url.replace('.m3u8', '.mpd')
        mpdresp = requests.get(url, headers=BASIC_HEADERS)
        m = re.search(r'"([^"]*/wv\?[^"]*)"', mpdresp.text)
        lic = m.group(1).replace('&amp;', '&')
        lic += '||R{SSM}|'

        item = xbmcgui.ListItem(path=url, offscreen=True)
        item.setProperty('inputstream','inputstream.adaptive')
        item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
        item.setProperty('inputstream.adaptive.license_key', lic)
        item.setMimeType('application/dash+xml')
        item.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(HANDLE, True, item)
    else:
        log('No video URL? vid={}, resp={}', vid, vr, level=xbmc.LOGERROR)
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
        except:
            pass
        if flat:
            list_show_flat(args.get('id'))
        else:
            list_show(args.get('id'), args.get('fanart', ''))
    elif action == 'season':
        list_season(args.get('id'), int(args.get('n', 0)), fanart=args.get('fanart', ''))
    elif action == 'play':
        play_video(args.get('id'))
    elif action == 'locked':
        locked(args.get('id'))
    else:
        log('Unknown action in params: {}', args, level=xbmc.LOGERROR)
